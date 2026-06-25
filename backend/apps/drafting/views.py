from django.http import JsonResponse

from apps.core.http import api_login_required, json_body, method_not_allowed
from apps.drafting.models import DraftDocument, DraftingSession
from apps.drafting.serializers import draft_to_dict, session_to_dict
from apps.drafting.services import advance, create_draft, initialize_session, regenerate_draft_block
from apps.exporting.services import export_docx
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
    session = advance(session, json_body(request))
    initialize_session(session)
    return JsonResponse({"session": session_to_dict(session)})


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
    return JsonResponse({"draft": draft_to_dict(draft)})


@api_login_required
def export_draft(request, draft_id):
    if request.method != "GET":
        return method_not_allowed(["GET"])
    draft, error = _draft_or_404(request.user, draft_id)
    if error:
        return error
    return export_docx(draft)
