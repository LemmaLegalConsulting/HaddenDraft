from django.conf import settings
from django.http import HttpResponse


class DevCorsMiddleware:
    """Small development CORS shim for configured Vite dev-server origins."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin = request.headers.get("Origin", "")
        allowed_origins = set(getattr(settings, "CORS_ALLOWED_ORIGINS", []))
        origin_allowed = bool(origin and origin in allowed_origins)

        if request.method == "OPTIONS":
            response = HttpResponse(status=204 if origin_allowed else 403)
        else:
            response = self.get_response(request)

        if origin_allowed:
            response["Access-Control-Allow-Origin"] = origin
            response["Vary"] = "Origin"
            response["Access-Control-Allow-Credentials"] = "true"
            response["Access-Control-Allow-Headers"] = "content-type,x-csrftoken"
            response["Access-Control-Allow-Methods"] = "GET,POST,PATCH,PUT,DELETE,OPTIONS"
        return response
