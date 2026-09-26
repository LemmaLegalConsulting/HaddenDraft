"""Authenticated API for filling templates without AI."""
import hashlib
import uuid

from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.utils.text import slugify

from apps.core.http import api_login_required, json_body, method_not_allowed
from apps.core.storage import get_document_storage, RAW
from apps.drafting.models import DraftingSession, TemplateFillJob
from apps.drafting.template_fill import DOCX_TYPE, preview_session, save_answers, session_payload
from apps.drafting.template_fill_jobs import job_payload, launch
from apps.matters.legalserver_delivery import wants_delivery
from apps.matters.route_aliases import resolve_matter_route_key
from apps.matters.services import matter_for_user, user_can_access_matter
from apps.templates_app.fill_templates import MAX_DOCX_BYTES
from apps.templates_app.models import DocumentTemplate, FillTemplateUpload


def file_response(key, filename):
    with get_document_storage().open(key) as stream:
        content = stream.read()
    response = HttpResponse(content, content_type=DOCX_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{slugify(filename.removesuffix(".docx"))}.docx"'
    return response


@api_login_required
def catalog(request):
    if request.method != "GET":
        return method_not_allowed(["GET"])
    matter = matter_for_user(request.user, request.GET.get("matterId", ""))
    if not matter:
        return JsonResponse({"error": "Case not found"}, status=404)
    uploads = FillTemplateUpload.objects.filter(Q(matter=matter) | Q(is_published=True)).exclude(prepared_key="")
    templates = [{"id": t.pk, "title": t.title, "slug": t.slug, "type": "library"} for t in DocumentTemplate.objects.filter(is_active=True).exclude(kind="worksheet")]
    templates.extend({"id": t.pk, "title": t.title, "slug": t.slug, "type": "upload", "shared": t.is_published} for t in uploads)
    sessions = DraftingSession.objects.filter(matter=matter, mode="template_fill")
    return JsonResponse({"templates": templates, "sessions": [
        {"id": s.pk, "title": s.fill_state.get("title", "Preparing template"),
         "updatedAt": s.updated_at.isoformat(), "jobs": [job_payload(j) for j in s.fill_jobs.order_by("-id")[:1]]}
        for s in sessions[:50]]})


@api_login_required
def start(request):
    if request.method != "POST":
        return method_not_allowed(["POST"])
    body = request.POST if request.content_type == "multipart/form-data" else json_body(request)
    matter = matter_for_user(request.user, body.get("matterId", ""))
    if not matter:
        return JsonResponse({"error": "Case not found"}, status=404)
    template, upload = None, None
    file = request.FILES.get("file")
    if file:
        if not file.name.lower().endswith(".docx") or file.size > MAX_DOCX_BYTES:
            return JsonResponse({"error": "Upload a DOCX no larger than 15 MB."}, status=400)
        content = file.read()
        token = uuid.uuid4().hex
        raw_key = f"template-fill/uploads/{token}/original.docx"
        get_document_storage(RAW).put_bytes(key=raw_key, content=content, content_type=DOCX_TYPE)
        title = str(body.get("title") or file.name.removesuffix(".docx"))[:255]
        upload = FillTemplateUpload.objects.create(title=title, slug=f"{slugify(title)[:90] or 'template'}-{token}",
            matter=matter, created_by=request.user, raw_key=raw_key, checksum=hashlib.sha256(content).hexdigest())
    else:
        try:
            identifier = int(body.get("templateId", 0))
        except (ValueError, TypeError):
            return JsonResponse({"error": "Select a template."}, status=400)
        if body.get("templateType") == "upload":
            upload = FillTemplateUpload.objects.filter(Q(matter=matter) | Q(is_published=True), pk=identifier).exclude(prepared_key="").first()
        else:
            template = DocumentTemplate.objects.filter(pk=identifier, is_active=True).exclude(kind="worksheet").first()
        if not template and not upload:
            return JsonResponse({"error": "Template not found"}, status=404)
    author = body.get("authorProfile", {}) if not file else {}
    if not isinstance(author, dict):
        return JsonResponse({"error": "Author profile must be an object."}, status=400)
    if not author:
        from apps.core.models import AuthorProfile
        profile = AuthorProfile.objects.filter(user=request.user).first()
        if profile:
            from apps.core.views import profile_to_dict
            author = profile_to_dict(profile, request.user)
    with transaction.atomic():
        session = DraftingSession.objects.create(matter=matter, template=template, mode="template_fill", author_profile=author)
        job = TemplateFillJob.objects.create(session=session, kind="prepare", created_by=request.user,
                                              payload={"uploadId": upload.pk} if upload else {})
        launch(job)
    job.refresh_from_db()
    return JsonResponse({"job": job_payload(job)}, status=202)


@api_login_required
def session_detail(request, session_id):
    if request.method not in {"GET", "PATCH", "POST"}:
        return method_not_allowed(["GET", "PATCH", "POST"])
    with transaction.atomic():
        session = DraftingSession.objects.select_for_update().filter(pk=session_id, mode="template_fill").first()
        if not session or not user_can_access_matter(request.user, session.matter):
            return JsonResponse({"error": "Session not found"}, status=404)
        # Opened from a URL that names a case: the session must be on it, and
        # one on another case answers exactly as a missing one.
        case_key = request.GET.get("caseKey", "").strip()
        if case_key:
            named = resolve_matter_route_key(request.user, case_key)
            if not named or named.pk != session.matter_id:
                return JsonResponse({"error": "Session not found"}, status=404)
        if request.method == "GET":
            return JsonResponse({"session": session_payload(session), "jobs": [job_payload(j) for j in session.fill_jobs.order_by("-id")[:5]]})
        body = json_body(request)
        if request.method == "POST":
            active = session.fill_jobs.filter(kind="export", status__in=["pending", "running"]).first()
            if active and job_payload(active)["status"] in {"pending", "running"}:
                proposed = body.get("answers", {})
                snapshot = active.payload.get("state", {})
                if not isinstance(proposed, dict) or any(snapshot.get("answers", {}).get(key) != value for key, value in proposed.items()):
                    return JsonResponse({"error": "An export is already running. Save your new answers or wait before preparing another DOCX."}, status=409)
                return JsonResponse({"job": job_payload(active), "session": session_payload(session)}, status=202)
        try:
            save_answers(session, body.get("answers", {}), body.get("revision"))
        except ValueError as error:
            return JsonResponse({"error": str(error)}, status=400)
        if request.method == "PATCH":
            return JsonResponse({"session": session_payload(session)})
        job = TemplateFillJob.objects.create(session=session, kind="export", created_by=request.user,
            payload={"state": session.fill_state, "saveToLegalServer": wants_delivery(body, "documents")})
        launch(job)
    job.refresh_from_db()
    return JsonResponse({"job": job_payload(job), "session": session_payload(session)}, status=202)


@api_login_required
def session_preview(request, session_id):
    """A reading view of the document with the given (possibly unsaved)
    answers. Nothing is stored; rendering is fast enough to answer inline."""
    if request.method != "POST":
        return method_not_allowed(["POST"])
    session = DraftingSession.objects.filter(pk=session_id, mode="template_fill").first()
    if not session or not user_can_access_matter(request.user, session.matter):
        return JsonResponse({"error": "Session not found"}, status=404)
    try:
        return JsonResponse({"preview": preview_session(session, json_body(request).get("answers", {}))})
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)


@api_login_required
def job_detail(request, job_id, download=False):
    if request.method != "GET":
        return method_not_allowed(["GET"])
    job = TemplateFillJob.objects.select_related("session__matter").filter(pk=job_id).first()
    if not job or not user_can_access_matter(request.user, job.session.matter):
        return JsonResponse({"error": "Job not found"}, status=404)
    if download:
        if job.status != "complete" or not job.result.get("fileKey"):
            return JsonResponse({"error": "This download is not ready."}, status=409)
        return file_response(job.result["fileKey"], job.result["filename"])
    return JsonResponse({"job": job_payload(job)})


@api_login_required
def upload_file(request, upload_id):
    if request.method != "GET":
        return method_not_allowed(["GET"])
    upload = FillTemplateUpload.objects.filter(pk=upload_id).first()
    admin_review = request.user.has_perm("templates_app.change_filltemplateupload")
    if not upload or not upload.prepared_key or not (admin_review or upload.is_published or user_can_access_matter(request.user, upload.matter)):
        return JsonResponse({"error": "Template not found"}, status=404)
    return file_response(upload.prepared_key, upload.slug + ".docx")
