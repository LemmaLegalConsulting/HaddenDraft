"""API for picking advice-letter sections and assembling a letter.

The workflow is short because the letter is short: list the sections that fit
this tenant, choose some, preview the assembled body, export it on letterhead.
There is no multi-step review pipeline here -- the whole point of brief advice is
that an advocate produces it in the twenty minutes before a hearing.

Every response carries the review state alongside the text. A section that still
needs an attorney's eye is offered, not hidden, so the caller has to be able to
show why.
"""

import io
import tempfile
from pathlib import Path

from django.http import HttpResponse, JsonResponse

from apps.core.http import api_login_required, json_body, method_not_allowed
from apps.drafting.advice_letter_assembly import assemble_letter, compose_advice_letter_docx
from apps.drafting.letters import LETTER_KINDS, RECIPIENT_ROLES, LetterRequest
from apps.matters.models import Matter
from apps.templates_app.advice_letter_library import (
    selectable_sections,
    wrapper_sections,
)
from apps.templates_app.models import AdviceLetterSection
from apps.templates_app.recommendations import recommend_advice_sections


def section_to_dict(section, *, include_body=True):
    data = {
        "id": section.id,
        "slug": section.slug,
        "title": section.title,
        "role": section.role,
        "topic": section.topic,
        "letterType": section.letter_type,
        "region": section.region,
        "status": section.status,
        "needsReview": section.needs_attorney_review,
        "reviewReason": section.review_summary,
        "wordCount": section.word_count,
        "summary": (section.selection_hints or {}).get("summary", ""),
        "readingGrade": (section.readability or {}).get("metrics", {}).get(
            "flesch_kincaid_grade"
        ),
        "notes": section.notes or [],
    }
    if include_body:
        data["body"] = section.body
    return data


@api_login_required
def advice_letter_sections(request):
    """List the sections available for a letter, newest review state included."""
    if request.method != "GET":
        return method_not_allowed(["GET"])
    region = request.GET.get("region", "")
    letter_type = request.GET.get("letterType", "brief_advice")
    reviewed_only = request.GET.get("reviewedOnly", "").lower() in {"1", "true", "yes"}

    sections = selectable_sections(
        region=region, letter_type=letter_type, reviewed_only=reviewed_only
    ).order_by("topic", "title")
    wrappers = wrapper_sections()
    return JsonResponse(
        {
            "sections": [section_to_dict(section) for section in sections],
            "wrapper": {
                role: section_to_dict(section) for role, section in wrappers.items()
            },
            "topics": sorted({section.topic for section in sections if section.topic}),
            "letterKinds": [{"value": value, "label": label} for value, label in LETTER_KINDS],
            "recipientRoles": [
                {"value": value, "label": label} for value, label in RECIPIENT_ROLES
            ],
            "awaitingReview": sum(1 for section in sections if section.needs_attorney_review),
        }
    )


@api_login_required
def advice_letter_addressing(request):
    """What the case already knows about who this letter is going to."""
    if request.method != "GET":
        return method_not_allowed(["GET"])
    from apps.matters.client_letter_context import client_letter_context, salutation_name

    matter = Matter.objects.filter(external_id=request.GET.get("matterId", "")).first()
    if not matter:
        return JsonResponse({"error": "Select a case first."}, status=404)
    case = client_letter_context(matter)
    case["recipientName"] = salutation_name(case.get("recipientName", ""))
    return JsonResponse({"addressing": case})


@api_login_required
def advice_letter_recommendations(request):
    """Rank sections for one tenant, with the reason for each."""
    if request.method != "POST":
        return method_not_allowed(["POST"])
    body = json_body(request)
    matter = Matter.objects.filter(external_id=body.get("matterId", "")).first()
    if not matter:
        return JsonResponse({"error": "Select a case first."}, status=404)

    region = body.get("region", "")
    sections = selectable_sections(
        region=region,
        letter_type=body.get("letterType", "brief_advice"),
        reviewed_only=bool(body.get("reviewedOnly")),
    )
    results = recommend_advice_sections(
        list(sections),
        matter,
        goal=body.get("goal", ""),
        conditions=body.get("conditions") or {},
        region=region,
        limit=int(body.get("limit", 6)),
    )
    return JsonResponse(
        {
            "recommendations": [
                {
                    "section": section_to_dict(entry["section"], include_body=False),
                    "score": entry["score"],
                    "reasons": entry["reasons"],
                    "unmetConditions": entry["unmetConditions"],
                    "summary": entry["summary"],
                    "needsReview": entry["needsReview"],
                    "reviewReason": entry["reviewReason"],
                }
                for entry in results
            ]
        }
    )


def _letter_request(body, matter=None):
    """Fall back to the case for anything the advocate did not type."""
    case = {}
    if matter is not None:
        from apps.matters.client_letter_context import client_letter_context, salutation_name

        case = client_letter_context(matter)
        case["recipientName"] = salutation_name(case.get("recipientName", ""))
    return LetterRequest(
        letter_kind=body.get("letterKind", "advice"),
        recipient_name=body.get("recipientName") or case.get("recipientName", ""),
        recipient_role=body.get("recipientRole", "client"),
        recipient_address=body.get("recipientAddress") or case.get("recipientAddress", ""),
        purpose=body.get("purpose", ""),
        deadline=body.get("letterDate", ""),
        delivery=body.get("delivery") or [],
        subject=body.get("subject") or case.get("caseReference", ""),
    )


def _assemble(body, user):
    matter = Matter.objects.filter(external_id=body.get("matterId", "")).first()
    slugs = body.get("sectionSlugs") or []
    if not slugs:
        return None, None, JsonResponse({"error": "Choose at least one section."}, status=400)

    by_slug = {
        section.slug: section
        for section in AdviceLetterSection.objects.filter(slug__in=slugs, is_active=True)
    }
    missing = [slug for slug in slugs if slug not in by_slug]
    if missing:
        return None, None, JsonResponse(
            {"error": f"Unknown section(s): {', '.join(missing)}"}, status=404
        )

    # Order follows the advocate's selection, not the catalog.
    chosen = [by_slug[slug] for slug in slugs]
    wrappers = wrapper_sections()
    letter = assemble_letter(
        chosen,
        intro=wrappers.get("intro") if body.get("includeWrapper", True) else None,
        closing=wrappers.get("closing") if body.get("includeWrapper", True) else None,
        author_profile=body.get("authorProfile") or {},
        matter=matter,
        template_data=body.get("templateData") or {},
    )
    return letter, matter, None


@api_login_required
def advice_letter_preview(request):
    """Assemble the letter body so the advocate can read it before exporting."""
    if request.method != "POST":
        return method_not_allowed(["POST"])
    body = json_body(request)
    letter, matter, error = _assemble(body, request.user)
    if error:
        return error
    return JsonResponse(
        {
            "letter": {
                "suggestedFilename": _download_name(body, letter, matter),
                "paragraphs": letter.paragraphs,
                "body": letter.body,
                "sections": letter.sections,
                "warnings": letter.warnings,
                "readability": letter.readability,
            }
        }
    )


@api_login_required
def advice_letter_export(request):
    """Render the assembled letter onto the organization's letterhead."""
    if request.method != "POST":
        return method_not_allowed(["POST"])
    body = json_body(request)
    letter, matter, error = _assemble(body, request.user)
    if error:
        return error

    author = body.get("authorProfile") or {}
    with tempfile.TemporaryDirectory() as work:
        output = Path(work) / "advice-letter.docx"
        compose_advice_letter_docx(
            letter,
            author_profile=author,
            request=_letter_request(body, matter),
            output_path=output,
        )
        payload = output.read_bytes()

    response = HttpResponse(
        io.BytesIO(payload),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    response["Content-Disposition"] = f'attachment; filename="{_download_name(body, letter, matter)}"'
    return response


def _download_name(body, letter, matter):
    """Name the download so it is findable a month later.

    An explicit `filename` from the caller wins outright: the advocate looking
    at the letter knows better than a pattern what to call it.
    """
    from django.utils.text import slugify

    explicit = str(body.get("filename") or "").strip()
    if explicit:
        stem = slugify(explicit.rsplit(".docx", 1)[0]) or "advice-letter"
        return f"{stem}.docx"

    from apps.core.models import OrganizationSettings
    from apps.drafting.letter_filenames import letter_filename

    pattern = body.get("filenamePattern", "")
    limit = None
    if not pattern:
        try:
            settings_row = OrganizationSettings.objects.first()
        except Exception:  # noqa: BLE001 - naming must not break the download
            settings_row = None
        if settings_row:
            pattern = settings_row.letter_filename_pattern or ""
            limit = settings_row.letter_filename_section_limit or None

    case = {}
    if matter is not None:
        from apps.matters.client_letter_context import client_letter_context

        case = client_letter_context(matter)

    titles = [
        section["title"]
        for section in letter.sections
        if section.get("slug") not in {"letter-opening", "letter-closing"}
    ]
    parsed_date = _parse_letter_date(body.get("letterDate", ""))
    return letter_filename(
        pattern=pattern,
        client_name=body.get("recipientName") or case.get("recipientName", ""),
        section_titles=titles,
        letter_date=parsed_date,
        case_number=case.get("caseNumber", ""),
        section_limit=limit or 3,
    )


def _parse_letter_date(value):
    """Accept what the advocate typed; fall back to today rather than failing."""
    from datetime import date, datetime

    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except (ValueError, TypeError):
            continue
    return date.today()
