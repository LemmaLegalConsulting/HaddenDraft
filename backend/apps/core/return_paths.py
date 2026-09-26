"""Where sign-in may send an advocate back to.

A direct link opened while signed out has to survive the Office 365 round trip,
so the requested page travels with the OAuth state. Anything that ends up in a
redirect is an open-redirect risk, so only an app-relative path into one of the
application's own task screens is accepted: no scheme, no host, nothing that
decodes into one, and never the API, admin, or auth callback.

The task list mirrors `frontend/src/routes/paths.js`; a path the frontend can
build but this list rejects just lands on the home screen, never somewhere else.
"""

import re
from urllib.parse import unquote

APP_TASK_ROOTS = frozenset(
    {
        "cases",
        "drafting",
        "template-fill",
        "advice-letters",
        "triage",
        "chat",
        "research",
        "argument-gym",
    }
)

MAX_RETURN_PATH_LENGTH = 512

# One path segment of a route: letters, digits, and the punctuation a case
# number or slug uses, plus percent-escapes. No "/" inside, no "\", no controls.
_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._~%-]+$")


def safe_return_path(value):
    """The value if it is a safe in-app route path, else ""."""
    if not isinstance(value, str) or not value or len(value) > MAX_RETURN_PATH_LENGTH:
        return ""
    if not value.startswith("/") or value.startswith("//"):
        return ""
    # Decode until stable so an encoded "//", "\" or ".." cannot slip through
    # one layer of checking and be decoded later by a browser or proxy.
    decoded = value
    for _ in range(3):
        once = unquote(decoded)
        if once == decoded:
            break
        decoded = once
    else:
        return ""
    if "\\" in decoded or "//" in decoded or any(ord(char) < 32 or ord(char) == 127 for char in decoded):
        return ""
    segments = value.strip("/").split("/")
    if not segments or segments[0] not in APP_TASK_ROOTS:
        return ""
    if any(not _SEGMENT_RE.match(segment) for segment in segments):
        return ""
    if any(segment in {".", ".."} for segment in decoded.strip("/").split("/")):
        return ""
    return value
