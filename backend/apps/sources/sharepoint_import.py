"""Explicit operator-approved Graph imports into the managed publication flow."""
from django.utils.dateparse import parse_datetime

from apps.sources.connectors.sharepoint import SharePointClient, SharePointError
from apps.sources.publication import import_version


def import_sharepoint_source(source, *, client=None, actor=None):
    client = client or SharePointClient()
    # An operator binds each approved source to one item in the configured
    # library. A search result or arbitrary URL cannot authorize corpus import.
    prefix = f"sharepoint:{client.drive_id}:"
    if not source.source_system_id.startswith(prefix):
        raise SharePointError("Bind this managed source to an approved item in the configured drive first.", code="unapproved_item")
    item_id = source.source_system_id[len(prefix):]
    document = client.get_document(item_id)
    metadata = document["metadata"]
    return import_version(
        source=source, content=document["content"], filename=metadata["name"],
        content_type=metadata["mimeType"], source_modified_at=parse_datetime(metadata["modifiedAt"]) if metadata["modifiedAt"] else None,
        source_etag=metadata["etag"], source_provenance={"provider": "sharepoint", **metadata},
        actor=actor, publish=False,
    )
