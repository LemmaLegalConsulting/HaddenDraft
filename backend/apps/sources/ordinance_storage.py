"""Storage for ordinance documents an operator uploads through the admin.

One tenant of the shared document store, under the ``ordinances`` prefix of the
published area, following the same rule as case-law artifacts: nothing writes
through the filesystem directly, so moving the store from a mounted share to S3
stays a configuration change.
"""
from __future__ import annotations

import hashlib

from apps.core.storage import PUBLISHED, PrefixedDocumentStorage, get_document_storage

ORDINANCE_PREFIX = "ordinances"


def get_ordinance_storage():
    return PrefixedDocumentStorage(get_document_storage(PUBLISHED), ORDINANCE_PREFIX)


def store_upload(*, content, municipality_slug, target_key, filename, content_type=""):
    """Write an uploaded document and return what the row needs to record.

    Keyed by content hash so re-uploading the same file is idempotent and two
    authorities citing one packet share a single stored copy.
    """
    digest = hashlib.sha256(content).hexdigest()
    suffix = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    key = f"{municipality_slug}/{target_key}/{digest}{suffix}"
    get_ordinance_storage().put_bytes(
        content=content, key=key, content_type=content_type or "application/octet-stream",
    )
    return {
        "storage_key": key,
        "sha256": digest,
        "size_bytes": len(content),
        "content_type": content_type,
        "original_filename": filename,
    }
