"""Case-law artifact storage.

Thin wrapper over :mod:`apps.core.storage`. Case-law artifacts are one tenant of
the shared document store, living under the ``caselaw`` prefix of whichever area
is being addressed:

    raw/caselaw/...        sidecar bundles as downloaded, awaiting ingestion
    published/caselaw/...  the derived artifacts views.py serves

``CaseLawArtifact.storage_key`` rows record keys relative to the *area*, so a
stored key looks like ``caselaw/originals/<sha>.pdf``. That keeps rows valid
across a backend change: only the area handle in front of the key changes when
the store moves from a file share to S3.
"""
from __future__ import annotations

from django.conf import settings

from apps.core.storage import PUBLISHED, RAW, get_document_storage, sha256_file

__all__ = ["get_caselaw_storage", "get_caselaw_raw_storage", "caselaw_prefix", "sha256_file"]


def caselaw_prefix():
    return settings.CASELAW_STORAGE_PREFIX.strip("/")


def get_caselaw_storage():
    """The published artifacts the application reads and serves."""
    return get_document_storage(PUBLISHED)


def get_caselaw_raw_storage():
    """The raw sidecar bundles an operator uploads, scoped to the caselaw prefix.

    Returned already scoped, because nothing outside case-law ingestion has any
    business walking another tenant's raw uploads.
    """
    from apps.core.storage import PrefixedDocumentStorage

    return PrefixedDocumentStorage(get_document_storage(RAW), caselaw_prefix())
