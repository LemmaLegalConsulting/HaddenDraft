from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.caselaw.models import (
    CaseLawArtifact,
    CaseLawChunk,
    CaseLawDecision,
    CaseLawImportBatch,
    CaseLawPage,
    CaseLawSearchDocument,
)
from apps.caselaw.dates import record_date_provenance
from apps.caselaw.storage import get_caselaw_storage, sha256_file


TEXT_CHUNK_CHARS = 6000
TEXT_CHUNK_OVERLAP = 600
DATE_FIELDS = {
    "decision_date", "entry_date", "filed_date", "hearing_date", "service_date", "finality_date",
    "appeal_deadline", "appeal_filed_date", "vacated_date", "reversed_date", "superseded_date",
}
DATETIME_FIELDS = {
    "last_treatment_checked_at", "last_currentness_reviewed_at",
}
LIST_FIELDS = {
    "parties", "party_roles", "parallel_citations", "issues", "holdings", "rules_applied",
    "statutes_cited", "regulations_cited", "cases_cited", "distinguished_by", "followed_by", "cited_by",
    "search_keywords",
}
BOOL_FIELDS = {
    "is_unpublished", "is_trial_court", "is_administrative", "is_persuasive_only",
    "has_embedded_text", "has_ocr_layer",
}
TEXT_DEFAULTS = {
    "publication_status": "unpublished",
    "treatment_status": "unchecked",
}


@dataclass
class CaseFileGroup:
    stem: str
    pdf_path: Path | None = None
    txt_path: Path | None = None
    json_path: Path | None = None
    verified_json_path: Path | None = None

    @property
    def metadata_path(self):
        return self.verified_json_path or self.json_path

    @property
    def metadata_verified(self):
        return bool(self.verified_json_path)

    def incomplete_reasons(self):
        reasons = []
        if not self.pdf_path:
            reasons.append("missing_pdf")
        if not self.metadata_path:
            reasons.append("missing_metadata")
        if not self.txt_path:
            reasons.append("missing_text")
        return reasons


def canonical_stem(path):
    name = path.name
    if name.endswith(".verified.json"):
        return name[: -len(".verified.json")]
    if name.endswith(".pdf.json"):
        return name[: -len(".pdf.json")]
    if name.endswith(".pdf.txt"):
        return name[: -len(".pdf.txt")]
    if name.endswith(".pdf"):
        return name[: -len(".pdf")]
    return path.stem


# Two sidecar namings are in circulation and both have to be readable.
#
# Downloaded bundles keep the PDF's full name and append to it:
#     Smith v Jones.pdf, Smith v Jones.pdf.txt, Smith v Jones.pdf.json
# Published artifacts are named by content hash with a plain extension, because
# the storage layer splits them across directories by artifact type:
#     originals/<sha>.pdf, ocr-text/<sha>.txt, metadata/<sha>.json
#
# Recognizing only the first naming is what silently reduced a full corpus to
# "missing_text" for every group: the PDFs matched, the .verified.json matched,
# and the plain .txt beside them was invisible.
# Ordered most specific first. The index doubles as a precedence rank, so a
# directory holding both namings for one case resolves to the specific one
# regardless of the order the filesystem hands paths over.
SIDECAR_SUFFIXES = (
    (".verified.json", "verified_json_path"),
    (".pdf.json", "json_path"),
    (".pdf.txt", "txt_path"),
    (".pdf", "pdf_path"),
    (".json", "json_path"),
    (".txt", "txt_path"),
)


def sidecar_artifact_type(name):
    """Return ``(artifact_type, rank)`` for a sidecar filename, or ``None``."""
    for rank, (suffix, artifact_type) in enumerate(SIDECAR_SUFFIXES):
        if name.endswith(suffix):
            return artifact_type, rank
    return None


def discover_case_groups(root):
    root = Path(root)
    groups = {}
    ranks = {}
    total_files = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        matched = sidecar_artifact_type(path.name)
        if not matched:
            continue
        artifact_type, rank = matched
        total_files += 1
        stem = canonical_stem(path)
        group = groups.setdefault(stem, CaseFileGroup(stem=stem))
        slot = (stem, artifact_type)
        if slot not in ranks or rank < ranks[slot]:
            ranks[slot] = rank
            setattr(group, artifact_type, path)
    return list(groups.values()), total_files


def load_metadata(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("metadata"), dict):
        merged = {**payload["metadata"], **{key: value for key, value in payload.items() if key != "metadata"}}
        return merged
    if not isinstance(payload, dict):
        raise ValueError("Metadata JSON must contain an object")
    return payload


def load_group_metadata(group):
    if group.verified_json_path:
        try:
            return load_metadata(group.verified_json_path), group.verified_json_path, "verified_json"
        except json.JSONDecodeError:
            if group.json_path:
                return load_metadata(group.json_path), group.json_path, "verified_marker_json"
            raise
    if group.json_path:
        return load_metadata(group.json_path), group.json_path, "unverified_json"
    return {"title": group.stem}, None, "missing_metadata"


def normalize_key(key):
    key = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(key)).replace("-", "_").replace(" ", "_")
    return key.lower()


FIELD_ALIASES = {
    "case_name": "title",
    "name": "title",
    "caption": "title",
    "short_name": "short_title",
    "docket": "docket_number",
    "docket_no": "docket_number",
    "docket_number": "docket_number",
    "case_no": "case_number",
    "date": "decision_date",
    "decided": "decision_date",
    "decided_date": "decision_date",
    "filed": "filed_date",
    "entry": "entry_date",
    "citations": "parallel_citations",
    "citation": "citation_string",
    "facts": "key_facts",
    "rules": "rules_applied",
    "statutes": "statutes_cited",
    "regulations": "regulations_cited",
    "cited_cases": "cases_cited",
    "negative_treatment": "negative_treatment_type",
}


def metadata_value(metadata, field, default=""):
    aliases = [field, FIELD_ALIASES.get(field, field)]
    for key, value in metadata.items():
        normalized = FIELD_ALIASES.get(normalize_key(key), normalize_key(key))
        if normalized in aliases or normalized == field:
            return value
    return default


def as_list(value):
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def as_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        return "; ".join(as_text(item) for item in value if as_text(item))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def as_date(value):
    """Parse a sidecar date, or return None.

    This body once sat below a ``return`` inside ``as_datetime`` where nothing
    could reach it, leaving ``as_date`` a stub that answered None for every
    value. Every date field in the corpus imported empty, silently, and the
    absence looked like documents that simply had no dates.
    """
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    # A sidecar may carry several dates in one field ("1991-08-12; 1991-08-20")
    # where the document held several hearings. The field takes one; the raw
    # wording is kept in the provenance record beside it.
    text = text.split(";")[0].strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y", "%d %B %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def as_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value if timezone.is_aware(value) else timezone.make_aware(value)
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)
    except ValueError:
        parsed_date = as_date(text)
        return timezone.make_aware(datetime.combine(parsed_date, datetime.min.time())) if parsed_date else None


def normalized_case_hash(metadata, group):
    parts = [
        as_text(metadata_value(metadata, "title", group.stem)),
        as_text(metadata_value(metadata, "docket_number")),
        as_text(metadata_value(metadata, "decision_date")),
        group.pdf_path.name if group.pdf_path else group.stem,
    ]
    return hashlib.sha256("|".join(parts).casefold().encode("utf-8")).hexdigest()


def decision_defaults(metadata, group, source_sha256, metadata_verified, *, allow_search, metadata_source=None):
    model_fields = {field.name for field in CaseLawDecision._meta.fields}
    values = {}
    for field in model_fields:
        if field in {"id", "imported_at", "updated_at"}:
            continue
        if field in LIST_FIELDS:
            values[field] = as_list(metadata_value(metadata, field, []))
        elif field in DATE_FIELDS:
            values[field] = as_date(metadata_value(metadata, field))
        elif field in DATETIME_FIELDS:
            values[field] = as_datetime(metadata_value(metadata, field))
        elif field in BOOL_FIELDS:
            raw = metadata_value(metadata, field, None)
            if raw is not None:
                values[field] = as_bool(raw)
        elif field in {"source_sha256"}:
            values[field] = source_sha256
        elif field in {"file_size_bytes"}:
            values[field] = group.pdf_path.stat().st_size if group.pdf_path else None
        elif field in {"metadata_verified"}:
            values[field] = metadata_verified
        elif field in {"metadata_source"}:
            values[field] = metadata_source or ("verified_json" if metadata_verified else "unverified_json")
        elif field in {"approved_for_search"}:
            values[field] = allow_search
        elif field in {"approved_for_drafting"}:
            values[field] = as_bool(metadata_value(metadata, field, False))
        elif field in {"original_filename"}:
            values[field] = group.pdf_path.name if group.pdf_path else group.stem
        elif field in {"mime_type"}:
            values[field] = "application/pdf" if group.pdf_path else ""
        else:
            values[field] = as_text(metadata_value(metadata, field, TEXT_DEFAULTS.get(field, "")))

    values["title"] = values["title"] or group.stem
    values["short_title"] = values["short_title"] or values["title"]
    values["normalized_title"] = values["normalized_title"] or re.sub(r"\s+", " ", values["title"].casefold()).strip()
    values["source_sha256"] = source_sha256
    return clamp_to_field_widths(values)


def clamp_to_field_widths(values):
    """Truncate text values that exceed their column width.

    Sidecar metadata is largely model-generated, so a field meant to hold a short
    classification label sometimes comes back as a sentence: a corpus of 1,215
    cases lost 17 of them outright to `value too long for type character
    varying(120)`, 15 on `tenant_landlord_role` and 2 on `publication_status`.

    Dropping an entire decision because one descriptive field ran long is the
    wrong trade. Nothing is permanently lost either way — the full sidecar JSON
    is kept as a stored artifact, so a widened column and a re-ingest can recover
    the untruncated value.
    """
    widths = {
        field.name: field.max_length
        for field in CaseLawDecision._meta.fields
        if getattr(field, "max_length", None)
    }
    for name, limit in widths.items():
        value = values.get(name)
        if isinstance(value, str) and len(value) > limit:
            values[name] = value[:limit]
    return values


def artifact_key(prefix, artifact_type, sha256, suffix):
    folder = {
        "original_pdf": "originals",
        "ocr_text": "ocr-text",
        "metadata_json": "metadata",
        "verified_metadata_json": "metadata",
    }.get(artifact_type, artifact_type)
    return f"{prefix.rstrip('/')}/{folder}/{sha256}{suffix}"


def put_artifact(decision, storage, *, path, artifact_type, key, content_type):
    result = storage.put_file(local_path=path, key=key, content_type=content_type)
    CaseLawArtifact.objects.update_or_create(
        decision=decision,
        artifact_type=artifact_type,
        storage_key=key,
        defaults={
            "original_filename": Path(path).name,
            "storage_backend": storage.backend_name,
            "content_type": content_type,
            "size_bytes": result["size"],
            "sha256": result["sha256"],
        },
    )


def compact_text(text):
    return " ".join((text or "").split())


def chunk_text(text):
    text = compact_text(text)
    if not text:
        return []
    if len(text) <= 4000:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + TEXT_CHUNK_CHARS, len(text))
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - TEXT_CHUNK_OVERLAP, start + 1)
    return chunks


def add_search_doc(decision, document_type, title, parts, *, metadata=None, chunk=None):
    text = compact_text(" ".join(as_text(part) for part in parts if as_text(part)))
    if not text:
        return
    CaseLawSearchDocument.objects.create(
        decision=decision,
        chunk=chunk,
        document_type=document_type,
        title=title[:500],
        search_text=text,
        metadata=metadata or {},
    )


def rebuild_search_documents(decision, ocr_text):
    decision.search_documents.all().delete()
    decision.chunks.all().delete()
    title = decision.title
    add_search_doc(decision, "overview", title, [decision.title, decision.court, decision.decision_date, decision.posture, decision.outcome])
    add_search_doc(decision, "keywords", title, decision.search_keywords)
    add_search_doc(decision, "issues", title, decision.issues)
    add_search_doc(decision, "holdings", title, decision.holdings)
    add_search_doc(decision, "rules", title, [decision.rules_applied, decision.statutes_cited, decision.regulations_cited, decision.cases_cited])
    add_search_doc(decision, "facts", title, [decision.key_facts])
    add_search_doc(decision, "procedural_posture", title, [decision.motion_type, decision.procedural_stage, decision.posture, decision.disposition])
    add_search_doc(decision, "outcome", title, [decision.outcome, decision.relief_granted, decision.relief_denied])
    for ordinal, text in enumerate(chunk_text(ocr_text), start=1):
        chunk = CaseLawChunk.objects.create(
            decision=decision,
            chunk_type="body",
            page_start=1,
            page_end=1,
            text=text,
            ordinal=ordinal,
        )
        add_search_doc(
            decision,
            "ocr_chunk",
            title,
            [text],
            metadata={"ordinal": ordinal, "pageStart": 1, "pageEnd": 1},
            chunk=chunk,
        )


def ingest_group(group, *, storage, storage_prefix, require_verified, allow_missing_pdf, allow_missing_metadata, allow_missing_text, force):
    if require_verified and not group.verified_json_path:
        return {"status": "skipped", "stem": group.stem, "reason": "missing_verified_metadata"}
    if not group.metadata_path and not allow_missing_metadata:
        return {"status": "skipped", "stem": group.stem, "reason": "missing_metadata"}
    if not group.pdf_path and not allow_missing_pdf:
        return {"status": "skipped", "stem": group.stem, "reason": "missing_pdf"}
    if not group.txt_path and not allow_missing_text:
        return {"status": "skipped", "stem": group.stem, "reason": "missing_text"}

    metadata, metadata_path, metadata_source = load_group_metadata(group)
    source_sha256 = sha256_file(group.pdf_path) if group.pdf_path else normalized_case_hash(metadata, group)
    if CaseLawDecision.objects.filter(source_sha256=source_sha256).exists() and not force:
        # The import is still idempotent: reruns refresh metadata and documents.
        pass
    allow_search = settings.CASELAW_IMPORT_APPROVE_VERIFIED_FOR_SEARCH if group.metadata_verified else settings.CASELAW_IMPORT_APPROVE_UNVERIFIED_FOR_SEARCH
    defaults = decision_defaults(
        metadata,
        group,
        source_sha256,
        group.metadata_verified,
        allow_search=allow_search,
        metadata_source=metadata_source,
    )

    with transaction.atomic():
        decision, created = CaseLawDecision.objects.update_or_create(
            source_sha256=source_sha256,
            defaults=defaults,
        )
        if group.pdf_path:
            put_artifact(
                decision,
                storage,
                path=group.pdf_path,
                artifact_type="original_pdf",
                key=artifact_key(storage_prefix, "original_pdf", source_sha256, ".pdf"),
                content_type="application/pdf",
            )
        if group.txt_path:
            put_artifact(
                decision,
                storage,
                path=group.txt_path,
                artifact_type="ocr_text",
                key=artifact_key(storage_prefix, "ocr_text", source_sha256, ".txt"),
                content_type="text/plain",
            )
        if group.json_path:
            put_artifact(
                decision,
                storage,
                path=group.json_path,
                artifact_type="metadata_json",
                key=artifact_key(storage_prefix, "metadata_json", source_sha256, ".json"),
                content_type="application/json",
            )
        if group.verified_json_path:
            put_artifact(
                decision,
                storage,
                path=group.verified_json_path,
                artifact_type="verified_metadata_json",
                key=artifact_key(storage_prefix, "verified_metadata_json", source_sha256, ".verified.json"),
                content_type="application/json",
            )

        text = group.txt_path.read_text(encoding="utf-8", errors="replace") if group.txt_path else ""
        decision.pages.all().delete()
        if text:
            CaseLawPage.objects.create(decision=decision, page_number=1, text=text)
        # Dates arrive from a sidecar a model wrote while reading this document.
        # Recording where each one came from, and whether the document's own
        # text shows it, is what keeps an extracted date checkable.
        record_date_provenance(
            decision,
            metadata,
            source_key=str(metadata_path) if metadata_path else "",
            source_sha256=sha256_file(metadata_path) if metadata_path else "",
            text=text,
        )
        rebuild_search_documents(decision, text)

    return {
        "status": "imported",
        "stem": group.stem,
        "decision_id": decision.id,
        "created": created,
        "incomplete": group.incomplete_reasons(),
        "metadata_verified": group.metadata_verified,
        "approved_for_search": allow_search,
    }


def ingest_caselaw_directory(
    source_path,
    *,
    dry_run=False,
    force=False,
    require_verified=None,
    allow_missing_pdf=False,
    allow_missing_metadata=False,
    allow_missing_text=False,
    limit=None,
    storage_prefix="caselaw",
):
    source_path = Path(source_path)
    groups, total_files = discover_case_groups(source_path)
    groups = groups[:limit] if limit else groups
    require_verified = settings.CASELAW_IMPORT_REQUIRE_VERIFIED if require_verified is None else require_verified
    storage = get_caselaw_storage()
    report = {
        "source_path": str(source_path),
        "total_files": total_files,
        "total_cases": len(groups),
        "imported": [],
        "skipped": [],
        "failed": [],
        "dry_run": dry_run,
    }

    if dry_run:
        for group in groups:
            reason = ""
            if require_verified and not group.verified_json_path:
                reason = "missing_verified_metadata"
            elif not group.metadata_path and not allow_missing_metadata:
                reason = "missing_metadata"
            elif not group.pdf_path and not allow_missing_pdf:
                reason = "missing_pdf"
            elif not group.txt_path and not allow_missing_text:
                reason = "missing_text"
            item = {
                "stem": group.stem,
                "metadata": str(group.metadata_path) if group.metadata_path else "",
                "metadata_verified": group.metadata_verified,
                "pdf": str(group.pdf_path) if group.pdf_path else "",
                "text": str(group.txt_path) if group.txt_path else "",
                "incomplete": group.incomplete_reasons(),
            }
            report["skipped" if reason else "imported"].append({**item, **({"reason": reason} if reason else {})})
        return report

    batch = CaseLawImportBatch.objects.create(
        source_path=str(source_path),
        storage_backend=storage.backend_name,
        total_files=total_files,
        total_cases=len(groups),
    )
    try:
        for group in groups:
            try:
                result = ingest_group(
                    group,
                    storage=storage,
                    storage_prefix=storage_prefix,
                    require_verified=require_verified,
                    allow_missing_pdf=allow_missing_pdf,
                    allow_missing_metadata=allow_missing_metadata,
                    allow_missing_text=allow_missing_text,
                    force=force,
                )
                report["imported" if result["status"] == "imported" else "skipped"].append(result)
            except Exception as exc:
                report["failed"].append({"stem": group.stem, "error": str(exc)})
        batch.imported_cases = len(report["imported"])
        batch.skipped_cases = len(report["skipped"])
        batch.failed_cases = len(report["failed"])
        batch.status = "failed" if report["failed"] else "finished"
        batch.finished_at = timezone.now()
        batch.report = report
        batch.save()
    except Exception:
        batch.status = "failed"
        batch.finished_at = timezone.now()
        batch.report = report
        batch.save()
        raise
    return report
