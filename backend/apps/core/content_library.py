"""File-backed legal-content defaults.

This module is intentionally limited to local files.  Callers use logical
content paths so a future SharePoint-backed provider can implement the same
interface without leaking remote-storage details into drafting or triage code.
"""

from pathlib import Path

from django.conf import settings


def content_library_dir():
    return Path(settings.CONTENT_LIBRARY_DIR)


def organization_content_library_dir():
    return Path(settings.ORGANIZATION_CONTENT_LIBRARY_DIR)


def published_content_library_dir():
    return Path(settings.PUBLISHED_CONTENT_LIBRARY_DIR)


def content_library_roots():
    """Return private-to-public provider roots without exposing provider details to callers.

    Three roots, most specific first: the organization's own material, then
    public content published to the document store, then the defaults that ship
    in the image.

    The middle root exists for corpora that are generated rather than authored.
    The local-ordinance corpus is megabytes of machine-written manifests and
    chunks regenerated from an ingest script, which is data rather than source;
    it lives on the published storage area like case-law artifacts and is
    refreshed without rebuilding an image. It sits below the organization root so
    a site override still wins, and above the image so a refreshed corpus is not
    shadowed by whatever the build happened to carry.
    """
    roots = []
    for root in (organization_content_library_dir(), published_content_library_dir()):
        if root.exists() and root not in roots:
            roots.append(root)
    public_root = content_library_dir()
    if public_root not in roots:
        roots.append(public_root)
    return roots


def content_paths(*parts):
    return [root.joinpath(*parts) for root in content_library_roots()]


def content_path(*parts):
    candidates = content_paths(*parts)
    return next((path for path in candidates if path.exists()), content_library_dir().joinpath(*parts))
