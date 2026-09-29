"""Translate Graph failures without hiding them as successful empty searches."""
from functools import wraps

from django.http import JsonResponse

from apps.sources.connectors.sharepoint import SharePointError


def graph_errors(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except SharePointError as exc:
            status = exc.status_code if exc.status_code in {401, 403, 404, 429} else 502
            if exc.code == "not_configured":
                status = 503
            response = JsonResponse({"error": str(exc), "code": exc.code, "retryAfter": exc.retry_after}, status=status)
            if exc.retry_after is not None:
                response["Retry-After"] = str(exc.retry_after)
            return response
    return wrapped
