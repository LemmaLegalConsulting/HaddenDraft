from django.conf import settings
from django.http import HttpResponse


class CorsMiddleware:
    """Cross-origin access for the origins named in ``CORS_ALLOWED_ORIGINS``.

    Two deployments need this. In development the Vite dev server is a
    different origin from ``runserver``. In production the single-page app is
    served from a warm static host so that the page paints while the API's
    container is still waking up, which puts it on a sibling subdomain of the
    API rather than the same one.

    Sibling subdomains matter for more than tidiness: a cookie is *same-site*
    across subdomains of one registrable domain, so the session survives with
    the ordinary ``SameSite=Lax`` and nothing has to be relaxed to ``None``.
    Hosting the app on an unrelated hostname would make the session a
    third-party cookie, which Safari and Firefox drop outright.
    """

    #: Response headers the browser will not reveal to a cross-origin caller
    #: unless they are named here. Everything in this list is read by the
    #: frontend, and every one of them fails *silently* if omitted -- the header
    #: arrives, ``headers.get()`` returns null, and the feature quietly does
    #: nothing rather than erroring.
    EXPOSED_HEADERS = (
        # downloadFile.js takes the filename from it; without it every exported
        # document saves under a generated fallback name.
        "Content-Disposition",
        # legalServerSave.js reports the outcome of a save from these four.
        "X-LegalServer-Delivery",
        "X-LegalServer-Delivery-Message",
        "X-LegalServer-AI-Audit",
        "X-LegalServer-AI-Audit-Message",
    )

    ALLOWED_HEADERS = "content-type,x-csrftoken"
    ALLOWED_METHODS = "GET,POST,PATCH,PUT,DELETE,OPTIONS"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin = request.headers.get("Origin", "")
        allowed_origins = set(getattr(settings, "CORS_ALLOWED_ORIGINS", []))
        origin_allowed = bool(origin and origin in allowed_origins)

        if request.method == "OPTIONS":
            # Answer the preflight here rather than letting it reach a view,
            # which would apply CSRF and authentication to a request that
            # carries neither.
            response = HttpResponse(status=204 if origin_allowed else 403)
        else:
            response = self.get_response(request)

        if origin_allowed:
            response["Access-Control-Allow-Origin"] = origin
            # The response varies by Origin, so a cache must not serve one
            # origin's response to another.
            response["Vary"] = "Origin"
            response["Access-Control-Allow-Credentials"] = "true"
            response["Access-Control-Allow-Headers"] = self.ALLOWED_HEADERS
            response["Access-Control-Allow-Methods"] = self.ALLOWED_METHODS
            response["Access-Control-Expose-Headers"] = ", ".join(self.EXPOSED_HEADERS)
            response["Access-Control-Max-Age"] = "600"
        return response


#: The name this middleware had when it only ran under DEBUG. Kept so an
#: environment still naming it in its own settings does not fail to boot.
DevCorsMiddleware = CorsMiddleware
