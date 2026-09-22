"""Versioned publication pipeline for operator-maintained legal sources.

The database is the publication pointer and searchable index; object storage is
the immutable artifact ledger.  A source becomes visible only after all raw,
validated, and published artifacts have been written successfully.
"""
from __future__ import annotations

import hashlib
import io
import json
import mimetypes
import re
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from docx import Document
from pypdf import PdfReader

from apps.core.storage import PUBLISHED, RAW, VALIDATED, get_document_storage
from apps.sources.models import (
    ManagedSource, ManagedSourceChunk, ManagedSourceEvent, ManagedSourceVersion,
)

PARSER_VERSION = "managed-source-parser-v1"
CHUNKER_VERSION = "paragraph-chunker-v1"
MAX_CHUNK_CHARS = 6000


class PublicationError(ValueError):
    pass


def _extension(filename):
    suffix = Path(filename or "source.txt").suffix.lower()
    return suffix if re.fullmatch(r"\.[a-z0-9]{1,10}", suffix or "") else ".bin"


def _extract(content, filename, content_type):
    suffix = Path(filename or "").suffix.lower()
    pages = []
    if content_type == "application/pdf" or suffix == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(content))
            pages = [(page.extract_text() or "").strip() for page in reader.pages]
        except Exception as exc:
            raise PublicationError(f"The PDF could not be read: {exc}") from exc
        text = "\n\n".join(page for page in pages if page)
    elif suffix == ".docx" or content_type.endswith("wordprocessingml.document"):
        try:
            document = Document(io.BytesIO(content))
            text = "\n\n".join(p.text.strip() for p in document.paragraphs if p.text.strip())
        except Exception as exc:
            raise PublicationError(f"The DOCX could not be read: {exc}") from exc
    elif suffix in {".txt", ".md", ".text"} or content_type.startswith("text/"):
        text = content.decode("utf-8-sig", "replace")
    else:
        raise PublicationError("Upload a PDF, DOCX, Markdown, or UTF-8 plain-text file.")
    text = text.replace("\x00", "").strip()
    if not text:
        raise PublicationError("No readable text was found. Upload OCR/plain text for a scanned document.")
    return text, pages


def _chunks(text):
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if not paragraphs:
        return []
    chunks, current = [], []
    for paragraph in paragraphs:
        pieces = [paragraph[i:i + MAX_CHUNK_CHARS] for i in range(0, len(paragraph), MAX_CHUNK_CHARS)]
        for piece in pieces:
            size = sum(len(item) + 2 for item in current)
            if current and size + len(piece) > MAX_CHUNK_CHARS:
                chunks.append("\n\n".join(current))
                current = []
            current.append(piece)
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def _proposed_case_metadata(text):
    """Conservative proposals for human review; never claims model verification."""
    lines = [line.strip() for line in text.splitlines() if line.strip()][:80]
    joined = "\n".join(lines)
    title = next((line for line in lines[:15] if re.search(r"\bv\.?\s+", line, re.I)), "")
    citation_match = re.search(r"\b\d{4}-Ohio-\d+\b", joined)
    date_match = re.search(
        r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+\d{1,2},\s+\d{4}\b", joined, re.I,
    )
    court = next((line for line in lines[:30] if "court" in line.casefold()), "")
    result = {}
    if title:
        result["title"] = title[:500]
    if citation_match:
        result["citation"] = citation_match.group(0)
    if court:
        result["court"] = court[:255]
    if date_match:
        try:
            result["decision_date"] = datetime.strptime(date_match.group(0), "%B %d, %Y").date()
        except ValueError:
            pass
    return result


def _manifest(version, chunks):
    source = version.source
    return {
        "schema_version": 1,
        "source": {"id": source.pk, "slug": source.slug, "kind": source.kind, "title": source.title},
        "version": {
            "id": version.pk, "number": version.number, "label": version.label,
            "source_sha256": version.sha256, "source_modified_at": (
                version.source_modified_at.isoformat() if version.source_modified_at else None
            ),
            "source_etag": version.source_etag, "imported_at": version.imported_at.isoformat(),
            "parser_version": version.parser_version, "chunker_version": version.chunker_version,
        },
        "metadata": {
            "jurisdiction": source.jurisdiction, "court": source.court, "county": source.county,
            "municipality": source.municipality, "appellate_district": source.appellate_district,
            "decision_date": source.decision_date.isoformat() if source.decision_date else None,
            "citation": source.citation, "publication_status": source.publication_status,
            "source_locator": source.source_locator, "source_system_id": source.source_system_id,
        },
        "chunks": [
            {"ordinal": index, "sha256": hashlib.sha256(value.encode()).hexdigest(), "characters": len(value)}
            for index, value in enumerate(chunks, 1)
        ],
    }


def import_version(*, source, content, filename="source.txt", content_type="", label="", actor=None,
                   source_modified_at=None, source_etag="", publish=False, background=False):
    """Validate and stage an immutable version; optionally make it live."""
    if not isinstance(content, bytes):
        content = bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    existing = source.versions.filter(sha256=digest).first()
    created = existing is None
    if existing:
        # A background import first creates the durable row and raw object, then
        # calls back through here in its worker to do the expensive parsing. An
        # uploaded row also makes an interrupted worker resumable by re-upload.
        if existing.status == "uploaded" or (
            existing.status == "failed" and existing.error.startswith("Raw storage failed:")
        ):
            version = existing
        else:
            if publish and source.current_version_id != existing.id and existing.status != "uploaded":
                publish_version(existing, actor=actor)
            return existing, False
    else:
        number = (source.versions.aggregate(value=Max("number"))["value"] or 0) + 1
        content_type = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        raw_key = f"managed-sources/{source.slug}/versions/{number}-{digest[:12]}/source{_extension(filename)}"
        version = ManagedSourceVersion.objects.create(
            source=source, number=number, label=label, original_filename=filename,
            content_type=content_type, size_bytes=len(content), sha256=digest,
            source_modified_at=source_modified_at, source_etag=source_etag, imported_by=actor,
            parser_version=PARSER_VERSION, chunker_version=CHUNKER_VERSION, raw_key=raw_key,
        )
        ManagedSourceEvent.objects.create(source=source, version=version, action="uploaded", actor=actor)

    try:
        get_document_storage(RAW).put_bytes(
            content=content, key=version.raw_key, content_type=version.content_type,
        )
    except Exception as exc:
        version.status = "failed"
        version.error = f"Raw storage failed: {exc}"
        version.validation_report = {"valid": False, "error": version.error}
        version.save(update_fields=["status", "error", "validation_report"])
        current = ManagedSource.objects.get(pk=source.pk)
        if not current.current_version_id:
            current.state = "failed"
            current.save(update_fields=["state", "updated_at"])
        ManagedSourceEvent.objects.create(
            source=source, version=version, action="failed", actor=actor,
            detail={"error": version.error},
        )
        return version, created

    if background:
        source_id = source.pk
        actor_id = getattr(actor, "pk", None)

        def work():
            from django.contrib.auth import get_user_model
            from django.db import close_old_connections

            close_old_connections()
            try:
                worker_source = ManagedSource.objects.get(pk=source_id)
                worker_actor = get_user_model().objects.filter(pk=actor_id).first() if actor_id else None
                import_version(
                    source=worker_source, content=content, filename=filename, content_type=content_type,
                    label=label, actor=worker_actor, source_modified_at=source_modified_at,
                    source_etag=source_etag, publish=publish,
                )
            finally:
                close_old_connections()

        threading.Thread(
            target=work, name=f"managed-source-import-{version.pk}", daemon=True,
        ).start()
        return version, created

    try:
        version.status = "validating"
        version.error = ""
        version.save(update_fields=["status", "error"])
        text, pages = _extract(content, filename, content_type)
        values = _chunks(text)
        if not values:
            raise PublicationError("The extracted text did not produce any retrieval chunks.")
        proposed = _proposed_case_metadata(text) if source.kind == "case" else {}
        changed = []
        for field, value in proposed.items():
            current = getattr(source, field)
            replace_placeholder_title = (
                field == "title"
                and str(current).strip().casefold() in {
                    "uploaded decision", "untitled decision", Path(filename).stem.casefold(),
                }
            )
            if not current or replace_placeholder_title:
                setattr(source, field, value)
                changed.append(field)
        if changed:
            source.save(update_fields=[*changed, "updated_at"])
        manifest = _manifest(version, values)
        prefix = f"managed-sources/{source.slug}/versions/{version.number}-{digest[:12]}"
        manifest_key = f"{prefix}/manifest.json"
        chunks_key = f"{prefix}/chunks.jsonl"
        encoded_manifest = json.dumps(manifest, indent=2, sort_keys=True).encode()
        encoded_chunks = b"".join(
            json.dumps({"ordinal": index, "text": value}, ensure_ascii=False).encode() + b"\n"
            for index, value in enumerate(values, 1)
        )
        validated = get_document_storage(VALIDATED)
        validated.put_bytes(content=encoded_manifest, key=manifest_key, content_type="application/json")
        validated.put_bytes(content=encoded_chunks, key=chunks_key, content_type="application/x-ndjson")
        with transaction.atomic():
            ManagedSourceChunk.objects.bulk_create([
                ManagedSourceChunk(
                    version=version, ordinal=index, text=value,
                    heading=(value.splitlines()[0][:500] if value else ""),
                    sha256=hashlib.sha256(value.encode()).hexdigest(),
                ) for index, value in enumerate(values, 1)
            ])
            version.validated_manifest_key = manifest_key
            version.chunk_count = len(values)
            version.validation_report = {
                "valid": True, "characters": len(text), "pages": len(pages),
                "proposed_metadata": {key: str(value) for key, value in proposed.items()},
            }
            version.status = "pending_review"
            version.save(update_fields=[
                "validated_manifest_key", "chunk_count", "validation_report", "status",
            ])
            ManagedSource.objects.filter(
                pk=source.pk, current_version__isnull=True, state="failed",
            ).update(state="draft", updated_at=timezone.now())
        ManagedSourceEvent.objects.create(
            source=source, version=version, action="validated", actor=actor,
            detail={"chunk_count": len(values)},
        )
        if publish:
            publish_version(version, actor=actor)
        return version, created
    except Exception as exc:
        version.status = "failed"
        version.error = str(exc)
        version.validation_report = {"valid": False, "error": str(exc)}
        version.save(update_fields=["status", "error", "validation_report"])
        # The caller may hold a source instance from before a just-completed
        # publication. Read the pointer under the current database state before
        # deciding whether this failed candidate affects the source-level badge.
        current = ManagedSource.objects.get(pk=source.pk)
        if not current.current_version_id:
            current.state = "failed"
            current.save(update_fields=["state", "updated_at"])
        ManagedSourceEvent.objects.create(
            source=source, version=version, action="failed", actor=actor, detail={"error": str(exc)},
        )
        return version, created


def publish_version(version, *, actor=None):
    version = ManagedSourceVersion.objects.select_related("source").get(pk=version.pk)
    source = version.source
    if (
        not version.validated_manifest_key
        or not version.chunks.exists()
        or not version.validation_report.get("valid")
    ):
        raise PublicationError("Only a successfully validated version can be published.")
    validated = get_document_storage(VALIDATED)
    published = get_document_storage(PUBLISHED)
    prefix = version.validated_manifest_key.rsplit("/", 1)[0]
    keys = list(validated.iter_keys(prefix))
    if not keys or version.validated_manifest_key not in keys:
        raise PublicationError("Validated artifacts are missing; the live corpus was not changed.")
    try:
        for key in keys:
            published.put_bytes(content=validated.open(key).read(), key=key,
                                content_type="application/json" if key.endswith(".json") else "application/x-ndjson")
        published_source_key = f"{prefix}/source{_extension(version.original_filename)}"
        with tempfile.TemporaryDirectory() as staging:
            staged = Path(staging) / f"source{_extension(version.original_filename)}"
            get_document_storage(RAW).download_to(version.raw_key, staged)
            published.put_file(
                local_path=staged, key=published_source_key, content_type=version.content_type,
            )
    except Exception as exc:
        version.error = f"Publication storage failed: {exc}"
        version.save(update_fields=["error"])
        raise PublicationError(version.error) from exc
    now = timezone.now()
    with transaction.atomic():
        locked = ManagedSource.objects.select_for_update().get(pk=source.pk)
        if locked.current_version_id and locked.current_version_id != version.id:
            ManagedSourceVersion.objects.filter(pk=locked.current_version_id).update(status="superseded")
        version.status = "published"
        version.published_at = now
        version.retired_at = None
        version.published_manifest_key = version.validated_manifest_key
        version.published_source_key = published_source_key
        version.error = ""
        version.save(update_fields=[
            "status", "published_at", "retired_at", "published_manifest_key", "published_source_key", "error",
        ])
        locked.current_version = version
        locked.state = "published"
        locked.last_successful_refresh_at = now
        locked.last_indexed_at = now
        locked.save(update_fields=[
            "current_version", "state", "last_successful_refresh_at", "last_indexed_at", "updated_at",
        ])
        ManagedSourceEvent.objects.create(source=locked, version=version, action="published", actor=actor)
    from apps.sources.research.index import reset_index
    reset_index()
    return version


def retire_source(source, *, actor=None):
    now = timezone.now()
    source.state = "retired"
    source.save(update_fields=["state", "updated_at"])
    if source.current_version_id:
        ManagedSourceVersion.objects.filter(pk=source.current_version_id).update(retired_at=now)
    ManagedSourceEvent.objects.create(
        source=source, version=source.current_version, action="retired", actor=actor,
    )
    from apps.sources.research.index import reset_index
    reset_index()


def rollback_source(source, version, *, actor=None):
    if version.source_id != source.id:
        raise PublicationError("That version belongs to a different source.")
    result = publish_version(version, actor=actor)
    ManagedSourceEvent.objects.create(source=source, version=version, action="rolled_back", actor=actor)
    return result
