from django.http import JsonResponse

from apps.core.http import api_login_required, json_body, method_not_allowed
from apps.matters.models import Matter
from apps.sources.models import RetrievedDocument
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
        matter = Matter.objects.filter(external_id=body["matterId"]).first()

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
