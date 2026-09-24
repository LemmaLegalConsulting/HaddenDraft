import io
import os

from django.core.wsgi import get_wsgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()


def _warm(app):
    """Drive one synthetic request so the first real one is not the slow one.

    Importing Django does not build the URL resolver or the middleware chain;
    those are lazy, and the request that triggers them pays for them. On a
    cold-started replica that request is the platform's readiness probe, which
    is given about a second before it is cut off -- so the probe would time out,
    retry, and cut off the next attempt too, while the container sat there able
    to serve. Doing the work here, under gunicorn's --preload, means it happens
    once in the master and every forked worker inherits the result.

    Failure here is not worth refusing to start over: this is an optimization,
    and a replica that skipped it still serves correctly, only slower. So
    anything raised is swallowed deliberately -- if the app is genuinely broken
    the probe will find that out, which is its job.
    """
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/readyz",
        "SERVER_NAME": "127.0.0.1",
        "SERVER_PORT": "8000",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.input": io.BytesIO(b""),
        "wsgi.errors": io.StringIO(),
        "wsgi.url_scheme": "http",
        "wsgi.multithread": False,
        "wsgi.multiprocess": True,
        "wsgi.run_once": False,
    }
    try:
        body = app(environ, lambda status, headers: None)
        # Consume it: a WSGI response is an iterable, and the view has not
        # actually run until it is walked.
        for _ in body:
            pass
        if hasattr(body, "close"):
            body.close()
    except Exception:  # noqa: BLE001 - see the docstring
        pass


_warm(application)

# The warm-up is a real request, and a request can open a database connection
# -- the first one runs the prepared-template sync. Under --preload that happens
# in the master, and a connection left open there is inherited by every forked
# worker: several processes then share one Postgres socket and read each
# other's results, which surfaces as random 500s and as a signed-in advocate's
# session lookup coming back empty. Close it so each worker opens its own.
from django.db import connections  # noqa: E402

connections.close_all()
