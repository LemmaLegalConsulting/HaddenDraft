import json
from functools import wraps

from django.http import JsonResponse


class JsonBodyError(ValueError):
    """Raised when a request body is not the JSON object an endpoint expects."""


def json_body(request):
    if not request.body:
        return {}
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise JsonBodyError("Request body must be valid JSON.") from exc
    if not isinstance(payload, dict):
        raise JsonBodyError("Request body must be a JSON object.")
    return payload


def method_not_allowed(methods):
    return JsonResponse({"error": f"Use one of: {', '.join(methods)}"}, status=405)


def json_body_errors_to_400(view_func):
    """Translate a malformed request body into a 400 instead of a 500."""

    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except JsonBodyError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

    return wrapped


def api_login_required(view_func):
    """Require an authenticated user and reject malformed JSON bodies with a 400."""
    guarded = json_body_errors_to_400(view_func)

    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        return guarded(request, *args, **kwargs)

    return wrapped
