from django.http import JsonResponse

from apps.core.http import api_login_required, json_body, method_not_allowed
from apps.matters.services import matter_for_user
from apps.sources.document_text import DocumentExtractionError, extract_text
from apps.sources.models import RetrievedDocument, UserResource
from apps.sources.registry import connector_registry


@api_login_required
def sources(_request):
    return JsonResponse({"sources": [connector.metadata() for connector in connector_registry.all()]})


@api_login_required
def research(request):
    if request.method != "POST":
        return method_not_allowed(["POST"])

    body = json_body(request)
    matter = None
    if body.get("matterId"):
        matter = matter_for_user(request.user, body["matterId"])
        if not matter:
            return JsonResponse({"error": "Case not found or not available to this user"}, status=404)

    results = connector_registry.search(
        body.get("query", ""),
        kinds=body.get("sourceKinds"),
        matter=matter,
        jurisdiction=body.get("jurisdiction", ""),
        limit_per_source=body.get("limitPerSource", 5),
        user=request.user,
        request=request,
    )
    for result in results:
        RetrievedDocument.objects.create(
            source_kind=result.source_kind,
            source_label=result.source_label,
            external_id=result.id,
            title=result.title,
            snippet=result.snippet,
            url=result.url,
            citation=result.citation,
            metadata=result.metadata,
        )
    return JsonResponse({"results": [result.to_dict() for result in results]})


def user_resource_to_dict(resource):
    return {
        "id": resource.id,
        "title": resource.title,
        "resourceType": resource.resource_type,
        "originalFilename": resource.original_filename,
        "snippet": " ".join(resource.text.split())[:240],
        "createdAt": resource.created_at.isoformat(),
        "updatedAt": resource.updated_at.isoformat(),
    }


@api_login_required
def user_resources(request):
    if request.method == "GET":
        resources = UserResource.objects.filter(user=request.user)
        return JsonResponse({"resources": [user_resource_to_dict(resource) for resource in resources]})
    if request.method != "POST":
        return method_not_allowed(["GET", "POST"])

    title = ""
    resource_type = "other"
    original_filename = ""
    extractor = ""
    text = ""
    try:
        if request.content_type and request.content_type.startswith("multipart/"):
            upload = request.FILES.get("file")
            if not upload:
                return JsonResponse({"error": "Upload a reference document"}, status=400)
            extracted = extract_text(upload.read(), filename=upload.name, content_type=upload.content_type or "")
            title = request.POST.get("title") or upload.name
            resource_type = request.POST.get("resourceType") or request.POST.get("resource_type") or "other"
            original_filename = upload.name
            extractor = extracted["extractor"]
            text = extracted["text"]
        else:
            body = json_body(request)
            title = body.get("title") or "Private reference"
            resource_type = body.get("resourceType") or body.get("resource_type") or "other"
            text = body.get("text") or ""
    except DocumentExtractionError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    if resource_type not in dict(UserResource.RESOURCE_TYPE_CHOICES):
        resource_type = "other"
    if not text.strip():
        return JsonResponse({"error": "Reference text could not be extracted"}, status=400)

    resource = UserResource.objects.create(
        user=request.user,
        title=title.strip() or original_filename or "Private reference",
        resource_type=resource_type,
        original_filename=original_filename,
        text=text,
        extractor=extractor,
    )
    return JsonResponse({"resource": user_resource_to_dict(resource)}, status=201)
