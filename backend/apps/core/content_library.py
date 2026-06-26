"""File-backed legal-content defaults.

This module is intentionally limited to local files.  Callers use logical
content paths so a future SharePoint-backed provider can implement the same
interface without leaking remote-storage details into drafting or triage code.
"""

from pathlib import Path

from django.conf import settings


def content_library_dir():
    return Path(settings.CONTENT_LIBRARY_DIR)


def content_path(*parts):
    return content_library_dir().joinpath(*parts)
