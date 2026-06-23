import json
from functools import wraps

from django.http import JsonResponse


def json_body(request):
    if not request.body:
        return {}
    return json.loads(request.body.decode("utf-8"))


def method_not_allowed(methods):
    return JsonResponse({"error": f"Use one of: {', '.join(methods)}"}, status=405)


def api_login_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        return view_func(request, *args, **kwargs)

    return wrapped
