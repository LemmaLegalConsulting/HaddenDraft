"""Live library search through Graph; no import, model calls, or local ranking."""
from django.http import JsonResponse

from apps.core.http import api_login_required, method_not_allowed
from apps.sources.connectors.sharepoint import SharePointConnector, SharePointError
from apps.sources.sharepoint_http import graph_errors


@api_login_required
@graph_errors
def precedent_search(request):
    if request.method != "GET":
        return method_not_allowed(["GET"])
    query = (request.GET.get("q") or "").strip()
    if not query or len(query) > 500:
        return JsonResponse({"error": "Enter a search of 1–500 characters."}, status=400)
    try:
        limit = int(request.GET.get("limit", "25"))
    except ValueError:
        limit = 0
    if not 1 <= limit <= 50:
        return JsonResponse({"error": "Limit must be between 1 and 50."}, status=400)
    connector = SharePointConnector()
    client = connector._client_for_request(request)
    if not client.configured:
        raise SharePointError("SharePoint is not configured. Ask an administrator to configure the library connection.", code="not_configured")
    results = SharePointConnector(client).search(query, limit=limit)
    response = JsonResponse({
        "query": query,
        "results": [result.to_dict() for result in results],
        "limit": limit,
        "usedAi": False,
        "aiSummary": "No AI was used. Results are returned in Microsoft Graph order.",
        "coverage": f"Showing files from up to {limit} Graph matches in the configured library. Narrow your search for more specific results.",
    })
    response["Cache-Control"] = "private, no-store"
    return response
