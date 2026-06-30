import re

from django.http import JsonResponse

from apps.core.http import api_login_required, json_body, method_not_allowed
from apps.drafting.models import DraftDocument, DraftingSession
from apps.drafting.serializers import draft_to_dict, session_to_dict
from apps.drafting.services import (
    advance,
    create_draft,
    initialize_session,
    outline_for_session,
    recommend_fact_ids,
    recommend_support_candidates,
    regenerate_draft_block,
)
from apps.exporting.services import export_docx
from apps.matters.document_context import chunk_text, get_case_documents, get_document_text, search_chunks, summarize_text
from apps.matters.models import MatterFact
from apps.matters.serializers import fact_to_dict, matter_to_dict
from apps.matters.services import accessible_matters_for_user, matter_for_user, user_can_access_matter
from apps.templates_app.models import DocumentTemplate
from apps.validation.services import validate_document as run_validation


def _session_or_404(user, session_id, *, with_template=False):
    queryset = DraftingSession.objects.select_related("matter", "template")
    if with_template:
        queryset = queryset.prefetch_related("template__blocks")
    session = queryset.filter(id=session_id).first()
    if not session or not user_can_access_matter(user, session.matter):
        return None, JsonResponse({"error": "Drafting session not found"}, status=404)
    return session, None


def _draft_or_404(user, draft_id):
    draft = DraftDocument.objects.select_related("session", "session__matter", "session__template").filter(id=draft_id).first()
    if not draft or not user_can_access_matter(user, draft.session.matter):
        return None, JsonResponse({"error": "Draft not found"}, status=404)
    return draft, None


def _advance_or_400(session, payload):
    try:
        return advance(session, payload), None
    except ValueError as exc:
        return None, JsonResponse({"error": str(exc)}, status=400)


def _fact_slug(matter, title):
    base = re.sub(r"[^a-z0-9]+", "-", (title or "document fact").lower()).strip("-") or "document-fact"
    slug = base
    index = 2
    while MatterFact.objects.filter(matter=matter, slug=slug).exists():
        slug = f"{base}-{index}"
        index += 1
    return slug


def _fact_search_plan(session):
    terms = ["deadline", "notice", "hearing", "payment", "rent", "repair", "disability", "assistance", "bankruptcy", "debtor relief"]
    for block in session.template.blocks.all() if session.template else []:
        terms.append(block.label)
        terms.extend(slug.replace("-", " ") for slug in block.selection_rule.get("fact_slugs", []))
    if session.instructions:
        terms.append(session.instructions)
    if session.matter.summary:
        terms.append(session.matter.summary)
    planned = []
    for term in terms:
        clean = re.sub(r"\s+", " ", term or "").strip()
        if clean and clean.casefold() not in {item.casefold() for item in planned}:
            planned.append(clean)
    return planned[:10]


def _create_document_fact(matter, document, chunk, query):
    text = summarize_text(chunk.get("text", ""), max_sentences=3, max_chars=700)
    if not text:
        return None
    title = f"{document.get('title')}: {query[:50]}"[:120]
    source_label = f"{document.get('source') or 'Case document'}: {document.get('citation') or document.get('title')}"
    existing = MatterFact.objects.filter(matter=matter, text=text).first()
    if existing:
        return existing
    return MatterFact.objects.create(
        matter=matter,
        slug=_fact_slug(matter, title),
        title=title,
        text=text,
        source_label=source_label,
        confidence="ai_document_search",
        selected_by_default=False,
    )


def _recommend_document_fact_ids(session, limit=8):
    selected = []
    seen_text = set()
    queries = _fact_search_plan(session)
    for document in get_case_documents(session.matter):
        text = get_document_text(document)
        chunks = chunk_text(text)
        if not chunks:
            continue
        for query in queries:
            matches = search_chunks(chunks, query, limit=2)
            for chunk in matches:
                normalized = re.sub(r"\s+", " ", chunk.get("text", "")).strip().casefold()
                if not normalized or normalized in seen_text:
                    continue
                seen_text.add(normalized)
                fact = _create_document_fact(session.matter, document, chunk, query)
                if fact and fact.id not in selected:
                    selected.append(fact.id)
                if len(selected) >= limit:
                    return selected
    return selected


@api_login_required
def sessions(request):
    if request.method == "GET":
        accessible_ids = [matter.id for matter in accessible_matters_for_user(request.user)]
        sessions = DraftingSession.objects.select_related("matter", "template").filter(matter_id__in=accessible_ids)
        return JsonResponse({"sessions": [session_to_dict(session) for session in sessions]})
    if request.method != "POST":
        return method_not_allowed(["GET", "POST"])

    body = json_body(request)
    matter = matter_for_user(request.user, body.get("matterId", ""))
    if not matter:
        return JsonResponse({"error": "Case not found or not available to this user"}, status=404)
    template = None
    if body.get("templateId"):
        template = DocumentTemplate.objects.get(id=body["templateId"])
    elif body.get("mode") == "draft_from_scratch":
        template = DocumentTemplate.objects.get(slug="novel-motion-shell")

    session = DraftingSession.objects.create(
        mode=body.get("mode", "draft_from_template"),
        matter=matter,
        template=template,
        author_profile=body.get("authorProfile", {}),
        template_data=body.get("templateData", {}),
        instructions=body.get("instructions", ""),
    )
    initialize_session(session)
    return JsonResponse({"session": session_to_dict(session)}, status=201)


@api_login_required
def session_detail(request, session_id):
    if request.method != "GET":
        return method_not_allowed(["GET"])
    session, error = _session_or_404(request.user, session_id)
    if error:
        return error
    session = DraftingSession.objects.select_related("matter", "template").prefetch_related("matter__facts", "template__blocks").get(id=session.id)
    return JsonResponse({"session": session_to_dict(session)})


@api_login_required
def advance_session(request, session_id):
    if request.method != "POST":
        return method_not_allowed(["POST"])
    session, error = _session_or_404(request.user, session_id)
    if error:
        return error
    session, error = _advance_or_400(session, json_body(request))
    if error:
        return error
    initialize_session(session)
    return JsonResponse({"session": session_to_dict(session)})


@api_login_required
def recommend_session_facts(request, session_id):
    if request.method != "POST":
        return method_not_allowed(["POST"])
    session, error = _session_or_404(request.user, session_id, with_template=True)
    if error:
        return error
    body = json_body(request)
    fact_ids = list(dict.fromkeys([*recommend_fact_ids(session), *_recommend_document_fact_ids(session)]))
    facts = MatterFact.objects.filter(id__in=fact_ids).order_by("id")
    if body.get("apply", True):
        session.selected_fact_ids = fact_ids
        session.save(update_fields=["selected_fact_ids", "updated_at"])
    matter = session.matter.__class__.objects.prefetch_related("facts").get(id=session.matter.id)
    return JsonResponse(
        {
            "factIds": fact_ids,
            "facts": [fact_to_dict(fact) for fact in facts],
            "case": matter_to_dict(matter, include_facts=True),
            "session": session_to_dict(session),
            "guidance": "Suggested facts are preselected from the template, case facts, and document text. Review them before continuing.",
        }
    )


@api_login_required
def recommend_session_support(request, session_id):
    if request.method != "POST":
        return method_not_allowed(["POST"])
    session, error = _session_or_404(request.user, session_id, with_template=True)
    if error:
        return error
    body = json_body(request)
    recommendations = recommend_support_candidates(session, user=request.user, request=request)
    selected = [candidate for candidate in recommendations["candidates"] if candidate.get("selectedByDefault")]
    if body.get("apply", True):
        session.selected_source_results = selected
        session.save(update_fields=["selected_source_results", "updated_at"])
    return JsonResponse(
        {
            **recommendations,
            "selectedResults": selected,
            "session": session_to_dict(session),
            "guidance": "Suggested support is ranked from the selected template, blocks, facts, jurisdiction, and instructions. Confirm what the draft may rely on.",
        }
    )


@api_login_required
def session_outline(request, session_id):
    if request.method not in {"GET", "POST"}:
        return method_not_allowed(["GET", "POST"])
    session, error = _session_or_404(request.user, session_id, with_template=True)
    if error:
        return error
    if request.method == "POST":
        body = json_body(request)
        if "selectedBlockKeys" in body:
            session.selected_block_keys = body["selectedBlockKeys"]
        author_profile = {**(session.author_profile or {}), "outlineApproved": True}
        session.author_profile = author_profile
        session, error = _advance_or_400(session, {"status": "outline_review"})
        if error:
            return error
    return JsonResponse(
        {
            "outline": outline_for_session(session),
            "session": session_to_dict(session),
            "guidance": "Approve the section plan before generating prose.",
        }
    )


@api_login_required
def generate_draft(request, session_id):
    if request.method != "POST":
        return method_not_allowed(["POST"])
    session, error = _session_or_404(request.user, session_id, with_template=True)
    if error:
        return error
    draft = create_draft(session)
    return JsonResponse({"draft": draft_to_dict(draft)}, status=201)


@api_login_required
def draft_detail(request, draft_id):
    draft, error = _draft_or_404(request.user, draft_id)
    if error:
        return error
    if request.method == "GET":
        return JsonResponse({"draft": draft_to_dict(draft)})
    if request.method == "PATCH":
        body = json_body(request)
        draft.sections = body.get("sections", draft.sections)
        draft.plain_text = body.get("plainText", draft.plain_text)
        draft.editor_state = body.get("editorState", draft.editor_state)
        draft.save()
        return JsonResponse({"draft": draft_to_dict(draft)})
    return method_not_allowed(["GET", "PATCH"])


@api_login_required
def regenerate_block(request, draft_id, block_key):
    if request.method != "POST":
        return method_not_allowed(["POST"])
    draft, error = _draft_or_404(request.user, draft_id)
    if error:
        return error
    draft = regenerate_draft_block(draft, block_key, json_body(request).get("instruction", ""))
    return JsonResponse({"draft": draft_to_dict(draft)})


@api_login_required
def validate_draft(request, draft_id):
    if request.method != "POST":
        return method_not_allowed(["POST"])
    draft, error = _draft_or_404(request.user, draft_id)
    if error:
        return error
    draft.validation_flags = run_validation(draft)
    draft.save()
    draft.session.status = "validation"
    draft.session.save(update_fields=["status", "updated_at"])
    return JsonResponse({"draft": draft_to_dict(draft)})


@api_login_required
def export_draft(request, draft_id):
    if request.method != "GET":
        return method_not_allowed(["GET"])
    draft, error = _draft_or_404(request.user, draft_id)
    if error:
        return error
    draft.session.status = "export"
    draft.session.save(update_fields=["status", "updated_at"])
    return export_docx(draft)
