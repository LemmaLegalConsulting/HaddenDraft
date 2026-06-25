from django.http import JsonResponse

from apps.core.http import api_login_required, json_body, method_not_allowed
from apps.drafting.models import DraftDocument, DraftingSession
from apps.drafting.serializers import draft_to_dict, session_to_dict
from apps.drafting.services import advance, create_draft, initialize_session, regenerate_draft_block
from apps.exporting.services import export_docx
from apps.matters.models import Matter
from apps.templates_app.models import DocumentTemplate
from apps.validation.services import validate_document as run_validation


@api_login_required
def sessions(request):
    if request.method == "GET":
        return JsonResponse({"sessions": [session_to_dict(session) for session in DraftingSession.objects.select_related("matter", "template")]})
    if request.method != "POST":
        return method_not_allowed(["GET", "POST"])

    body = json_body(request)
    matter = Matter.objects.get(external_id=body["matterId"])
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
    session = DraftingSession.objects.select_related("matter", "template").prefetch_related("matter__facts", "template__blocks").get(id=session_id)
    return JsonResponse({"session": session_to_dict(session)})


@api_login_required
def advance_session(request, session_id):
    if request.method != "POST":
        return method_not_allowed(["POST"])
    session = DraftingSession.objects.get(id=session_id)
    session = advance(session, json_body(request))
    initialize_session(session)
    return JsonResponse({"session": session_to_dict(session)})


@api_login_required
def generate_draft(request, session_id):
    if request.method != "POST":
        return method_not_allowed(["POST"])
    session = DraftingSession.objects.select_related("matter", "template").prefetch_related("template__blocks").get(id=session_id)
    draft = create_draft(session)
    return JsonResponse({"draft": draft_to_dict(draft)}, status=201)


@api_login_required
def draft_detail(request, draft_id):
    draft = DraftDocument.objects.get(id=draft_id)
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
    draft = DraftDocument.objects.select_related("session", "session__matter", "session__template").get(id=draft_id)
    draft = regenerate_draft_block(draft, block_key, json_body(request).get("instruction", ""))
    return JsonResponse({"draft": draft_to_dict(draft)})


@api_login_required
def validate_draft(request, draft_id):
    if request.method != "POST":
        return method_not_allowed(["POST"])
    draft = DraftDocument.objects.get(id=draft_id)
    draft.validation_flags = run_validation(draft)
    draft.save()
    return JsonResponse({"draft": draft_to_dict(draft)})


@api_login_required
def export_draft(request, draft_id):
    if request.method != "GET":
        return method_not_allowed(["GET"])
    draft = DraftDocument.objects.get(id=draft_id)
    return export_docx(draft)
