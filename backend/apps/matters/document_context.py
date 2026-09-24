import hashlib
import logging
import re

from django.conf import settings
from django.core.cache import cache

from apps.sources.connectors.legalserver import (
    UUID_RE,
    LegalServerClient,
    LegalServerError,
    _display_value,
    _first_value,
    legalserver_matter_uuid,
)
from apps.sources.document_text import DocumentExtractionError, extract_text


logger = logging.getLogger(__name__)

DOCUMENT_CACHE_PREFIX = "legalserver-case-documents"
# How long the last list LegalServer returned stays usable when a later fetch
# fails. It is shown as such, never as a fresh answer.
LAST_GOOD_DOCUMENTS_SECONDS = 24 * 60 * 60

NOTE_KEYS = ("case_notes", "notes", "case_note", "intake_notes", "narrative", "description")
DOCUMENT_KEYS = ("documents", "case_documents", "files", "uploaded_documents", "attachments")
NOTE_DOCUMENT_KEYS = ("documents", "attachments", "files", "case_documents", "uploaded_documents", "document", "note_documents")
TEXT_KEYS = ("text", "content", "body", "summary", "description", "snippet")
CUSTOM_FIELD_HINTS = (
    "narrative",
    "summary",
    "facts",
    "intake",
    "story",
    "client statement",
    "defense",
    "notice",
    "rent",
    "ledger",
    "subsidy",
    "voucher",
    "disability",
    "reasonable accommodation",
    "repairs",
    "conditions",
    "timeline",
    "relief",
    "goal",
    "household",
    "income",
)


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _stable_id(*parts):
    digest = hashlib.sha1("|".join(_clean(part) for part in parts).encode("utf-8")).hexdigest()[:12]
    return f"case-doc-{digest}"


def _document_title(raw, default="Case document"):
    return _clean(_first_value(raw, "title", "name", "filename", "file_name", default=default)) or default


def _document_url(raw):
    return _clean(_first_value(raw, "download_url", "url", "web_url", "sharepoint_url", default=""))


def _document_external_id(raw):
    return _clean(_first_value(raw, "id", "document_id", "uuid", "external_id", default=""))


def _text_from_raw(raw):
    for key in TEXT_KEYS:
        value = raw.get(key) if isinstance(raw, dict) else None
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _document_date(raw):
    return _clean(_first_value(raw, "date", "date_posted", "created_at", "updated_at", default=""))


def _attached_documents(raw, source_note_id=""):
    attachments = []
    if not isinstance(raw, dict):
        return attachments
    for key in NOTE_DOCUMENT_KEYS:
        value = raw.get(key)
        values = value if isinstance(value, list) else [value] if isinstance(value, dict) else []
        for item in values:
            if not isinstance(item, dict):
                continue
            title = _document_title(item, default="Attached document")
            external_id = _document_external_id(item)
            url = _document_url(item)
            attachments.append(
                {
                    "id": external_id or _stable_id(source_note_id, title, url),
                    "title": title,
                    "filename": _clean(_first_value(item, "filename", "file_name", default=title)),
                    "downloadUrl": url,
                    "url": url,
                    "type": _clean(_first_value(item, "type", "document_type", "mime_type", default="")),
                    "date": _document_date(item),
                    "sourceNoteId": source_note_id,
                    "hasText": bool(_text_from_raw(item) or url),
                    "needsDownload": bool(url and not _text_from_raw(item)),
                }
            )
    return attachments


def is_document_webhook_note(note):
    text = " ".join(
        [
            str(note.get("subject", "")),
            str(note.get("body", "")),
            str(note.get("title", "")),
            str(note.get("type", "")),
            str(note.get("text", "")),
        ]
    ).casefold()
    return (
        "documents received via webhook" in text
        or "document received" in text
        or bool(note.get("note_has_document_attached"))
        or bool(note.get("hasDocumentAttached"))
    )


def _note_items(raw_payload):
    notes = []
    for key in NOTE_KEYS:
        value = raw_payload.get(key)
        if isinstance(value, str) and value.strip():
            notes.append({"title": key.replace("_", " ").title(), "text": value})
        elif isinstance(value, list):
            for index, item in enumerate(value, start=1):
                if isinstance(item, str) and item.strip():
                    notes.append({"title": f"Case note {index}", "text": item})
                elif isinstance(item, dict):
                    text = _text_from_raw(item) or _display_value(item)
                    if text:
                        title = _clean(_first_value(item, "title", "subject", "created_at", default=f"Case note {index}"))
                        note_id = _clean(_first_value(item, "casenote_uuid", "id", "uuid", default=""))
                        notes.append(
                            {
                                "id": note_id,
                                "title": title,
                                "text": text,
                                "date": _document_date(item),
                                "type": _clean(_first_value(item, "note_type", "type", default="")),
                                "raw": item,
                                "attachedDocuments": _attached_documents(item, note_id),
                                "isWebhookDocumentNotice": is_document_webhook_note(item),
                            }
                        )
    return notes


def _raw_documents(raw_payload):
    documents = []
    for key in DOCUMENT_KEYS:
        value = raw_payload.get(key)
        if isinstance(value, list):
            documents.extend(item for item in value if isinstance(item, dict))
    return documents


def _legalserver_identifiers(matter):
    raw_payload = matter.raw_payload or {}
    seen = set()
    for value in (
        matter.external_id,
        raw_payload.get("matter_uuid"),
        raw_payload.get("database_id"),
        raw_payload.get("id"),
        raw_payload.get("case_number"),
    ):
        value = _clean(value)
        if value and value not in seen:
            seen.add(value)
            yield value


def _refresh_legalserver_matter_payload(matter, legalserver, *, force=False):
    raw_payload = matter.raw_payload or {}
    if matter.source_system.casefold() != "legalserver" or (
        not force and any(key in raw_payload for key in NOTE_KEYS)
    ):
        return raw_payload
    for identifier in _legalserver_identifiers(matter):
        try:
            payload = legalserver.get_matter(identifier)
        except LegalServerError:
            continue
        if isinstance(payload, dict) and payload:
            merged = {**raw_payload, **payload}
            matter_uuid = legalserver_matter_uuid(merged)
            if matter_uuid and hasattr(legalserver, "get_matter_notes"):
                try:
                    notes = legalserver.get_matter_notes(matter_uuid)
                except LegalServerError:
                    notes = []
                if notes:
                    merged["notes"] = notes
            matter.raw_payload = merged
            matter.save(update_fields=["raw_payload", "updated_at"])
            return matter.raw_payload
    return raw_payload


def _document_identifiers(matter):
    """The matter's identifiers, UUID first.

    The documents API searches by the matter's UUID; given the human case
    number it answers 404 every time. Asking that first doubled every document
    load against LegalServer's rate limit for no chance of an answer.
    """
    identifiers = list(_legalserver_identifiers(matter))
    return sorted(identifiers, key=lambda value: 0 if UUID_RE.match(value) else 1)


def _fetch_remote_documents(matter, legalserver, *, force=False):
    """Return (documents, problem) for a LegalServer matter.

    `problem` is empty when LegalServer answered -- including when it answered
    that there are no documents -- and a sentence when it could not be asked.
    The two used to be the same empty list: a 429 from LegalServer showed an
    advocate "No case documents were returned" for a case holding twenty-two.
    """
    ttl = int(getattr(settings, "LEGALSERVER_DOCUMENT_CACHE_SECONDS", 0) or 0)
    key = f"{DOCUMENT_CACHE_PREFIX}:{matter.pk}"
    if ttl and not force:
        cached = cache.get(key)
        if cached is not None:
            return cached, ""

    answered = None
    failures = []
    for identifier in _document_identifiers(matter):
        try:
            documents = legalserver.get_matter_documents(identifier)
        except LegalServerError as error:
            failures.append(str(error))
            continue
        answered = documents
        if documents:
            break

    if answered is not None:
        if ttl:
            cache.set(key, answered, ttl)
            cache.set(f"{key}:last-good", answered, LAST_GOOD_DOCUMENTS_SECONDS)
        return answered, ""

    reason = failures[-1] if failures else "no identifier LegalServer recognizes"
    logger.warning("Could not fetch LegalServer documents for matter %s: %s", matter.external_id, reason)
    stale = cache.get(f"{key}:last-good") if ttl else None
    if stale is not None:
        return stale, (
            f"LegalServer did not return this case's documents just now ({reason}). "
            "This is the list from an earlier load."
        )
    return [], f"LegalServer did not return this case's documents ({reason}). The case may hold documents not shown here."


def get_case_documents(matter, *, client=None, include_remote=True, force_refresh=False):
    documents, _problem = get_case_documents_with_status(
        matter, client=client, include_remote=include_remote, force_refresh=force_refresh
    )
    return documents


def get_case_documents_with_status(matter, *, client=None, include_remote=True, force_refresh=False):
    """Like get_case_documents, plus why the list may be incomplete ("" if not)."""
    legalserver = client or LegalServerClient()
    raw_payload = matter.raw_payload or {}
    remote_available = (
        include_remote
        and matter.source_system.casefold() == "legalserver"
        and legalserver.configured
    )
    if remote_available:
        raw_payload = _refresh_legalserver_matter_payload(matter, legalserver, force=force_refresh)
    documents = []

    note_texts = _note_items(raw_payload)
    normalized_notes = {re.sub(r"\s+", " ", note["text"]).strip().casefold() for note in note_texts}
    normalized_summary = re.sub(r"\s+", " ", matter.summary or "").strip().casefold()
    if normalized_summary and normalized_summary not in normalized_notes:
        note_texts.append({"title": "Case summary", "text": matter.summary})
    for index, note in enumerate(note_texts, start=1):
        text = note["text"]
        title = note["title"]
        note_id = note.get("id") or _stable_id(matter.external_id, "note", index, title, text[:80])
        documents.append(
            {
                "id": note_id,
                "kind": "case_note",
                "title": title,
                "filename": "",
                "citation": f"{title}, {matter.external_id}",
                "source": "LegalServer case note" if matter.source_system == "LegalServer" else "Case note",
                "snippet": summarize_text(text, max_sentences=1),
                "text": text,
                "size": len(text),
                "hasText": True,
                "needsDownload": False,
                "date": note.get("date", ""),
                "type": note.get("type", ""),
                "attachedDocuments": note.get("attachedDocuments", []),
                "isWebhookDocumentNotice": bool(note.get("isWebhookDocumentNotice")),
                "raw": {**(note.get("raw") or {}), "text": text},
            }
        )

    raw_documents = _raw_documents(raw_payload)
    problem = ""
    if remote_available and not raw_documents:
        raw_documents, problem = _fetch_remote_documents(matter, legalserver, force=force_refresh)

    for raw in raw_documents:
        title = _document_title(raw)
        url = _document_url(raw)
        external_id = _document_external_id(raw)
        inline_text = _text_from_raw(raw)
        documents.append(
            {
                "id": _stable_id(matter.external_id, "document", external_id, title, url),
                "kind": "case_document",
                "title": title,
                "filename": _clean(_first_value(raw, "filename", "file_name", default=title)),
                "citation": title,
                "source": _clean(_first_value(raw, "storage", "storage_provider", "source", default="Case document")),
                "mimeType": _clean(_first_value(raw, "mime_type", "content_type", "type", default="")),
                "snippet": summarize_text(inline_text, max_sentences=1) if inline_text else _clean(_first_value(raw, "description", "snippet", default="")),
                "size": len(inline_text) if inline_text else raw.get("size") or raw.get("byte_size") or None,
                "hasText": bool(inline_text or url),
                "hasFile": bool(url),
                "needsDownload": bool(url and not inline_text),
                "raw": raw,
            }
        )
    from apps.matters.work_product import label_work_product

    return label_work_product(matter, documents), problem


def _custom_field_candidates(raw_payload):
    fields = []

    def add_field(key, value, label=""):
        if value in (None, "", [], {}):
            return
        if isinstance(value, (dict, list)):
            preview = _display_value(value)
            if not preview:
                return
            value_text = preview
        else:
            value_text = str(value)
        normalized_key = str(key).strip()
        if not normalized_key:
            return
        fields.append({"key": normalized_key, "label": label or normalized_key.replace("_", " ").title(), "value": value_text})

    explicit = raw_payload.get("custom_fields") or raw_payload.get("customFields") or raw_payload.get("fields")
    if isinstance(explicit, dict):
        for key, value in explicit.items():
            add_field(key, value)
    elif isinstance(explicit, list):
        for item in explicit:
            if not isinstance(item, dict):
                continue
            key = _first_value(item, "key", "name", "field_name", "slug", "id", default="")
            value = _first_value(item, "value", "display_value", "text", "answer", default="")
            label = _first_value(item, "label", "display_name", "name", default=key)
            add_field(key, value, label)

    excluded = set(NOTE_KEYS) | set(DOCUMENT_KEYS) | {
        "assignments",
        "users",
        "events",
        "created_by_user_id",
        "created_by_username",
        "manual_entry",
        "custom_fields_normalized",
    }
    for key, value in raw_payload.items():
        if key in excluded:
            continue
        if isinstance(value, (str, int, float, bool)) and str(value).strip():
            add_field(key, value)
    return fields


def custom_fields_inventory(matter):
    fields = []
    seen = set()
    for field in _custom_field_candidates(matter.raw_payload or {}):
        key = field["key"]
        if key in seen:
            continue
        seen.add(key)
        value = field["value"]
        search_name = key.replace("_", " ").casefold()
        hint_hits = [hint for hint in CUSTOM_FIELD_HINTS if hint in search_name]
        category = "narrative" if any(hit in hint_hits for hit in ("narrative", "summary", "facts", "intake", "story", "client statement")) else "case_data"
        score = len(hint_hits) * 20 + min(len(value), 600) / 30
        confidence = "likely_useful" if score >= 20 or len(value) >= 180 else "possibly_useful" if score >= 8 else "background"
        fields.append(
            {
                "key": key,
                "label": field["label"],
                "value": value,
                "valuePreview": summarize_text(value, max_sentences=2, max_chars=240),
                "hasValue": bool(value.strip()),
                "category": category,
                "confidence": confidence,
                "reason": "Field name/value suggests drafting relevance." if confidence == "likely_useful" else "Available case field with a value.",
                "score": score,
            }
        )
    return sorted(fields, key=lambda item: (-item["score"], item["label"]))


def case_materials_payload(matter, *, client=None, force_refresh=False):
    from apps.matters.serializers import fact_to_dict

    materials, documents_problem = get_case_documents_with_status(matter, client=client, force_refresh=force_refresh)
    notes = [document_to_public_dict(item) for item in materials if item["kind"] == "case_note"]
    documents = [document_to_public_dict(item) for item in materials if item["kind"] == "case_document"]
    custom_fields = custom_fields_inventory(matter)
    drafting_facts = [fact_to_dict(fact) for fact in matter.facts.all()]
    return {
        "summary": {
            "noteCount": len(notes),
            "documentCount": len(documents),
            "customFieldCount": len([field for field in custom_fields if field["hasValue"]]),
            "draftingFactCount": len(drafting_facts),
        },
        # Said in words, and distinct from an empty list: "could not fetch" is
        # not "there are none".
        "documentsUnavailable": documents_problem,
        "notes": notes,
        "documents": documents,
        "customFields": custom_fields,
        "draftingFacts": drafting_facts,
    }


def get_case_document(matter, document_id):
    for document in get_case_documents(matter):
        if document["id"] == document_id:
            return document
    return None


def get_document_text(document, *, client=None):
    inline_text = _text_from_raw(document.get("raw") or {})
    if inline_text:
        return inline_text
    if document["kind"] == "case_note":
        return (document.get("raw") or {}).get("text", "")
    url = _document_url(document.get("raw") or {})
    if not url:
        return document.get("snippet") or ""
    try:
        legalserver = client or LegalServerClient()
        downloaded = legalserver.download_document(url)
        result = extract_text(
            downloaded["content"],
            filename=document.get("filename") or downloaded["filename"],
            content_type=downloaded["content_type"],
        )
        return result["text"]
    except (LegalServerError, DocumentExtractionError):
        return document.get("snippet") or ""


def get_document_file(document, *, client=None):
    url = _document_url(document.get("raw") or {})
    if not url:
        raise LegalServerError("No viewable file is available for this document")
    legalserver = client or LegalServerClient()
    return legalserver.download_document(url)


def summarize_text(text, *, max_sentences=4, max_chars=900):
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    summary = " ".join(sentence for sentence in sentences[:max_sentences] if sentence).strip()
    if len(summary) > max_chars:
        summary = summary[: max_chars - 1].rsplit(" ", 1)[0] + "..."
    return summary


def chunk_text(text, *, words_per_chunk=180, overlap=35):
    words = re.findall(r"\S+", text or "")
    chunks = []
    if not words:
        return chunks
    step = max(words_per_chunk - overlap, 1)
    for index, start in enumerate(range(0, len(words), step), start=1):
        chunk_words = words[start : start + words_per_chunk]
        if not chunk_words:
            continue
        chunks.append(
            {
                "id": f"chunk-{index}",
                "index": index,
                "startWord": start,
                "endWord": start + len(chunk_words),
                "text": " ".join(chunk_words),
            }
        )
        if start + words_per_chunk >= len(words):
            break
    return chunks


def search_chunks(chunks, query, *, limit=5):
    terms = {term.casefold() for term in re.findall(r"[a-zA-Z0-9']+", query or "") if len(term) > 2}
    if not terms:
        return chunks[:limit]
    scored = []
    for chunk in chunks:
        haystack = chunk["text"].casefold()
        score = sum(haystack.count(term) for term in terms)
        if score:
            scored.append((score, chunk))
    scored.sort(key=lambda item: (-item[0], item[1]["index"]))
    return [chunk for _score, chunk in scored[:limit]]


def document_to_public_dict(document):
    return {key: value for key, value in document.items() if key != "raw"}
