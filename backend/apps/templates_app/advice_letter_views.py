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
from apps.drafting.advice_letter_assembly import (
    advice_draft_sections,
    assemble_letter,
    compose_advice_letter_docx,
    letter_from_draft_sections,
)
from apps.drafting.components import record_sections
from apps.drafting.letters import LETTER_KINDS, RECIPIENT_ROLES, LetterRequest
from apps.drafting.models import DraftDocument, DraftingSession
from apps.drafting.serializers import draft_to_dict
from apps.drafting.source_bindings import bind_current_versions
from apps.matters.legalserver_delivery import delivery_to_dict, save_document
from apps.matters.models import MatterFact
from apps.matters.services import matter_for_user, user_can_access_matter
from apps.templates_app.advice_letter_library import (
    selectable_sections,
    wrapper_sections,
)
from apps.templates_app.models import AdviceLetterSection
from apps.templates_app.recommendations import recommend_advice_sections


ADVICE_METADATA_KEY = "_advice_letter"
ADVICE_FIELD_NAMES = (
    "recipientName",
    "recipientAddress",
    "subject",
    "letterDate",
    "filename",
    "letterKind",
    "recipientRole",
    "purpose",
    "delivery",
    "includeWrapper",
)


def _matter_for_request(body, user):
    return matter_for_user(user, body.get("matterId", ""))


def _letter_fields(body, fallback=None):
    """Read addressing values from either the legacy or draft-shaped payload."""
    values = dict(fallback or {})
    nested = body.get("letterFields")
    if isinstance(nested, dict):
        values.update({key: nested[key] for key in ADVICE_FIELD_NAMES if key in nested})
    values.update({key: body[key] for key in ADVICE_FIELD_NAMES if key in body})
    return values


def _advice_metadata(session):
    if not session:
        return {}
    return dict((session.template_data or {}).get(ADVICE_METADATA_KEY) or {})


def _metadata_for_body(session, body, slugs):
    previous = _advice_metadata(session)
    fields = _letter_fields(body, previous.get("letterFields"))
    include_wrapper = body.get(
        "includeWrapper",
        fields.get("includeWrapper", previous.get("includeWrapper", True)),
    )
    fields["includeWrapper"] = bool(include_wrapper)
    return {
        **previous,
        "sectionSlugs": list(slugs),
        "region": body.get("region", previous.get("region", "")),
        "letterType": body.get("letterType", previous.get("letterType", "brief_advice")),
        "goal": body.get("goal", previous.get("goal", "")),
        "conditions": body.get("conditions", previous.get("conditions") or {}),
        "templateData": body.get("templateData", previous.get("templateData") or {}),
        "includeWrapper": bool(include_wrapper),
        "letterFields": fields,
    }


def _payload_for_draft(draft, body=None):
    """Merge saved addressing/assembly choices with one export request."""
    body = body or {}
    session = draft.session
    metadata = _advice_metadata(session)
    fields = _letter_fields(body, metadata.get("letterFields"))
    payload = {
        "matterId": session.matter.external_id,
        "sectionSlugs": metadata.get("sectionSlugs") or [],
        "includeWrapper": metadata.get("includeWrapper", True),
        "authorProfile": session.author_profile or {},
        "templateData": metadata.get("templateData") or {},
        **fields,
    }
    for key in ("authorProfile", "templateData", "includeWrapper", "filenamePattern"):
        if key in body:
            payload[key] = body[key]
    if isinstance(body.get("letterFields"), dict):
        payload.update(_letter_fields(body))
    return payload


def _letter_payload(body, letter, matter):
    return {
        "suggestedFilename": _download_name(body, letter, matter),
        "paragraphs": letter.paragraphs,
        "body": letter.body,
        "sections": letter.sections,
        "warnings": letter.warnings,
        "readability": letter.readability,
    }


def _advice_instructions(goal, conditions):
    selected = [key.replace("_", " ") for key, value in (conditions or {}).items() if value]
    parts = []
    if goal:
        parts.append(f"Letter goal: {goal}")
    if selected:
        parts.append("Confirmed case conditions: " + ", ".join(selected))
    return "\n".join(parts)


def _editor_state_for_sections(sections, previous=None):
    """Seed newly selected blocks without replacing saved human formatting."""
    previous = previous if isinstance(previous, dict) else {}
    blocks = dict(previous.get("blocks") or {})
    for section in sections:
        key = section.get("key")
        if key and key not in blocks and section.get("sourceEditorState"):
            blocks[key] = section["sourceEditorState"]
    return {"format": "lexical_blocks", "blocks": blocks}


def _preserve_legacy_advice_blocks(desired, previous_sections):
    """Keep a pre-split advice block intact when an old draft is reopened.

    New advice drafts expose the opening issue statement as its own block. A
    draft created before that projection still has one block under the catalog
    slug; carrying that block forward is safer than silently replacing an
    advocate's edits with newly split source text.
    """
    previous_by_key = {
        section.get("key"): section
        for section in previous_sections or []
        if isinstance(section, dict) and section.get("key")
    }
    split_slugs = {
        section.get("adviceSectionSlug")
        for section in desired
        if section.get("adviceBlockRole") == "issue_statement"
    }
    legacy_slugs = {
        slug
        for slug in split_slugs
        if slug in previous_by_key
        and not any(
            section.get("key") in {f"issue-statement-{slug}", slug}
            and section.get("key") != slug
            for section in previous_sections or []
        )
    }
    if not legacy_slugs:
        return desired

    preserved = []
    emitted = set()
    for section in desired:
        slug = section.get("adviceSectionSlug")
        if slug not in legacy_slugs:
            preserved.append(section)
            continue
        if slug in emitted:
            continue
        previous = previous_by_key[slug]
        preserved.append(
            {
                **previous,
                "key": slug,
                "adviceSectionSlug": slug,
                "adviceSectionTitle": section.get("adviceSectionTitle") or section.get("label", ""),
            }
        )
        emitted.add(slug)
    return preserved


def _catalog_sections(slugs):
    by_slug = {
        section.slug: section
        for section in AdviceLetterSection.objects.filter(slug__in=slugs, is_active=True)
    }
    missing = [slug for slug in slugs if slug not in by_slug]
    if missing:
        return None, f"Unknown section(s): {', '.join(missing)}"
    return [by_slug[slug] for slug in slugs], ""


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

    matter = _matter_for_request({"matterId": request.GET.get("matterId", "")}, request.user)
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
    matter = _matter_for_request(body, request.user)
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
    matter = _matter_for_request(body, user) if body.get("matterId") else None
    if body.get("matterId") and not matter:
        return None, None, JsonResponse({"error": "Case not found or not available to this user."}, status=404)
    slugs = list(dict.fromkeys(body.get("sectionSlugs") or []))
    if not slugs:
        return None, None, JsonResponse({"error": "Choose at least one section."}, status=400)

    chosen, missing = _catalog_sections(slugs)
    if missing:
        return None, None, JsonResponse(
            {"error": missing}, status=404
        )

    # Order follows the advocate's selection, not the catalog.
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
    return JsonResponse({"letter": _letter_payload(body, letter, matter)})


def _valid_fact_ids(matter, values):
    """Keep selected fact provenance inside the case being drafted."""
    ids = []
    for value in values or []:
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            continue
    valid = set(MatterFact.objects.filter(matter=matter, id__in=ids).values_list("id", flat=True))
    return [fact_id for fact_id in ids if fact_id in valid]


@api_login_required
def advice_letter_draft(request):
    """Create or update an advice letter backed by the shared draft editor."""
    if request.method != "POST":
        return method_not_allowed(["POST"])
    body = json_body(request)

    draft = None
    session = None
    if body.get("draftId"):
        try:
            draft_id = int(body["draftId"])
        except (TypeError, ValueError):
            return JsonResponse({"error": "Draft not found."}, status=404)
        draft = (
            DraftDocument.objects.select_related("session", "session__matter")
            .filter(id=draft_id)
            .first()
        )
        if not draft or not user_can_access_matter(request.user, draft.session.matter):
            return JsonResponse({"error": "Draft not found."}, status=404)
        session = draft.session
        if body.get("matterId") and body["matterId"] != session.matter.external_id:
            return JsonResponse({"error": "That draft belongs to another case."}, status=400)
        matter = session.matter
        saved_slugs = _advice_metadata(session).get("sectionSlugs") or []
        slugs = body["sectionSlugs"] if "sectionSlugs" in body else saved_slugs
    else:
        matter = _matter_for_request(body, request.user)
        if not matter:
            return JsonResponse({"error": "Case not found or not available to this user."}, status=404)
        slugs = body.get("sectionSlugs") or []

    slugs = list(dict.fromkeys(str(slug) for slug in slugs if str(slug).strip()))
    if not slugs:
        return JsonResponse({"error": "Choose at least one section."}, status=400)
    chosen, missing = _catalog_sections(slugs)
    if missing:
        return JsonResponse({"error": missing}, status=404)

    include_wrapper = body.get(
        "includeWrapper",
        _advice_metadata(session).get("includeWrapper", True),
    )
    wrappers = wrapper_sections()
    desired = advice_draft_sections(
        chosen,
        intro=wrappers.get("intro") if include_wrapper else None,
        closing=wrappers.get("closing") if include_wrapper else None,
        author_profile=body.get("authorProfile", session.author_profile if session else {}),
        matter=matter,
        template_data=body.get(
            "templateData",
            _advice_metadata(session).get("templateData") if session else {},
        ),
    )

    metadata = _metadata_for_body(session, body, slugs)
    metadata["includeWrapper"] = bool(include_wrapper)
    author_profile = body.get("authorProfile", session.author_profile if session else {}) or {}
    template_data = body.get(
        "templateData",
        metadata.get("templateData") or {},
    ) or {}
    goal = body.get("goal", metadata.get("goal", "")) or ""
    conditions = body.get("conditions", metadata.get("conditions") or {}) or {}
    if "selectedFactIds" in body:
        selected_fact_ids = _valid_fact_ids(matter, body.get("selectedFactIds"))
    elif session is not None:
        selected_fact_ids = session.selected_fact_ids or []
    else:
        selected_fact_ids = list(
            MatterFact.objects.filter(matter=matter, selected_by_default=True)
            .order_by("id")
            .values_list("id", flat=True)
        )
    selected_sources = body.get(
        "selectedSourceResults",
        session.selected_source_results if session else [],
    ) or []
    selected_sources = [source for source in selected_sources if isinstance(source, dict)]
    selected_curated = body.get(
        "selectedCuratedFacts",
        session.selected_curated_facts if session else [],
    ) or []
    selected_curated = [fact for fact in selected_curated if isinstance(fact, dict)]

    if session is None:
        session = DraftingSession.objects.create(
            mode="advice_letter",
            matter=matter,
            template=None,
            status="draft_review",
            selected_fact_ids=selected_fact_ids,
            selected_curated_facts=selected_curated,
            selected_source_results=selected_sources,
            selected_block_keys=slugs,
            author_profile=author_profile,
            template_data={ADVICE_METADATA_KEY: metadata},
            goal=goal,
            instructions=body.get("instructions") or _advice_instructions(goal, conditions),
        )
    else:
        session.mode = "advice_letter"
        session.status = "draft_review"
        session.selected_fact_ids = selected_fact_ids
        session.selected_curated_facts = selected_curated
        session.selected_source_results = selected_sources
        session.selected_block_keys = slugs
        session.author_profile = author_profile
        session.template_data = {ADVICE_METADATA_KEY: metadata}
        session.goal = goal
        session.instructions = body.get("instructions") or _advice_instructions(goal, conditions)
        session.save()

    previous_sections = []
    if draft is not None:
        candidate_sections = body.get("currentSections")
        previous_sections = candidate_sections if isinstance(candidate_sections, list) else draft.sections
    previous_by_key = {
        section.get("key"): section
        for section in previous_sections
        if isinstance(section, dict) and section.get("key")
    }
    desired = _preserve_legacy_advice_blocks(desired, previous_sections)
    sections = []
    for section in desired:
        previous = previous_by_key.get(section["key"])
        if previous is None:
            sections.append(section)
            continue
        # Preserve the editor's body, formatting, origin, and source list while
        # refreshing only the catalog identity used for later provenance.
        sections.append(
            {
                **previous,
                "key": section["key"],
                "label": section["label"],
                "adviceSectionSlug": section["adviceSectionSlug"],
            }
        )

    incoming_editor_state = body.get("currentEditorState")
    previous_editor_state = (
        incoming_editor_state
        if isinstance(incoming_editor_state, dict)
        else (draft.editor_state if draft is not None else {})
    )
    editor_state = _editor_state_for_sections(sections, previous_editor_state)

    if draft is None:
        draft = DraftDocument.objects.create(
            session=session,
            template=None,
            title="Client advice letter",
            sections=[],
            plain_text="",
            editor_state=editor_state,
        )
        record_sections(
            draft,
            sections,
            editor_state=editor_state,
        )
    elif draft.sections != sections or draft.editor_state != editor_state:
        record_sections(draft, sections, origin="human", editor_state=editor_state)
    bind_current_versions(draft)
    draft.refresh_from_db()

    payload = _payload_for_draft(draft)
    letter = letter_from_draft_sections(draft.sections, editor_state=draft.editor_state)
    fields = dict((metadata.get("letterFields") or {}))
    fields.setdefault("filename", _download_name(payload, letter, matter))
    return JsonResponse(
        {
            "draft": draft_to_dict(draft),
            "letter": _letter_payload(payload, letter, matter),
            "letterFields": fields,
        },
        status=201 if not body.get("draftId") else 200,
    )


@api_login_required
def advice_letter_draft_export(request, draft_id):
    """Export the current advice draft, including edits not in the catalog."""
    if request.method != "POST":
        return method_not_allowed(["POST"])
    draft = (
        DraftDocument.objects.select_related("session", "session__matter")
        .filter(id=draft_id)
        .first()
    )
    if not draft or not user_can_access_matter(request.user, draft.session.matter):
        return JsonResponse({"error": "Draft not found."}, status=404)

    body = json_body(request)
    payload = _payload_for_draft(draft, body)
    author = payload.get("authorProfile") or {}
    letter = letter_from_draft_sections(draft.sections, editor_state=draft.editor_state)
    draft.session.status = "export"
    draft.session.author_profile = author
    draft.session.save(update_fields=["status", "author_profile", "updated_at"])
    with tempfile.TemporaryDirectory() as work:
        output = Path(work) / "advice-letter.docx"
        compose_advice_letter_docx(
            letter,
            author_profile=author,
            request=_letter_request(payload, draft.session.matter),
            output_path=output,
        )
        file_payload = output.read_bytes()

    filename = _download_name(payload, letter, draft.session.matter)
    response = HttpResponse(
        io.BytesIO(file_payload),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@api_login_required
def advice_letter_draft_legalserver(request, draft_id):
    """Save this advice letter to the case file, replacing an earlier save.

    Downloading and filing are separate acts here. An advocate revises an
    advice letter several times in one sitting, and each revision filing itself
    as another copy would leave the case file holding five letters with no way
    to tell which one was sent.
    """
    if request.method != "POST":
        return method_not_allowed(["POST"])
    draft = (
        DraftDocument.objects.select_related("session", "session__matter")
        .filter(id=draft_id)
        .first()
    )
    if not draft or not user_can_access_matter(request.user, draft.session.matter):
        return JsonResponse({"error": "Draft not found."}, status=404)

    body = json_body(request)
    payload = _payload_for_draft(draft, body)
    author = payload.get("authorProfile") or {}
    letter = letter_from_draft_sections(draft.sections, editor_state=draft.editor_state)
    with tempfile.TemporaryDirectory() as work:
        output = Path(work) / "advice-letter.docx"
        compose_advice_letter_docx(
            letter,
            author_profile=author,
            request=_letter_request(payload, draft.session.matter),
            output_path=output,
        )
        file_payload = output.read_bytes()

    delivery = save_document(
        draft.session.matter,
        user=request.user,
        filename=_download_name(payload, letter, draft.session.matter),
        content=file_payload,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        title=draft.title or "Client advice letter",
        origin="advice_letter",
        scope_key=f"advice-letter:draft:{draft.id}",
    )
    return JsonResponse({"delivery": delivery_to_dict(delivery)}, status=201)


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

    filename = _download_name(body, letter, matter)
    response = HttpResponse(
        io.BytesIO(payload),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    # Downloading does not file the letter. This one-shot export has no draft
    # behind it, so there is no stable identity to update: a second export would
    # add a second copy to the case. Filing is the draft endpoint's explicit
    # save action, which replaces what it filed before.
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
