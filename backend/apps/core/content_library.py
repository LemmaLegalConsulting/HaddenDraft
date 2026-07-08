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


def content_library_roots():
    """Return private-to-public provider roots without exposing provider details to callers."""
    private_root = organization_content_library_dir()
    roots = [private_root] if private_root.exists() else []
    public_root = content_library_dir()
    if public_root not in roots:
        roots.append(public_root)
    return roots


def content_paths(*parts):
    return [root.joinpath(*parts) for root in content_library_roots()]


def content_path(*parts):
    candidates = content_paths(*parts)
    return next((path for path in candidates if path.exists()), content_library_dir().joinpath(*parts))
