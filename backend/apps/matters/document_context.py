import hashlib
import re

from apps.sources.connectors.legalserver import LegalServerClient, LegalServerError, _display_value, _first_value
from apps.sources.document_text import DocumentExtractionError, extract_text


NOTE_KEYS = ("case_notes", "notes", "case_note", "intake_notes", "narrative", "description")
DOCUMENT_KEYS = ("documents", "case_documents", "files", "uploaded_documents", "attachments")
TEXT_KEYS = ("text", "content", "body", "summary", "description", "snippet")


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
                        notes.append({"title": title, "text": text})
    return notes


def _raw_documents(raw_payload):
    documents = []
    for key in DOCUMENT_KEYS:
        value = raw_payload.get(key)
        if isinstance(value, list):
            documents.extend(item for item in value if isinstance(item, dict))
    return documents


def get_case_documents(matter, *, client=None, include_remote=True):
    raw_payload = matter.raw_payload or {}
    documents = []

    note_texts = _note_items(raw_payload)
    if not note_texts and matter.summary:
        note_texts.append({"title": "Case summary", "text": matter.summary})
    for index, note in enumerate(note_texts, start=1):
        text = note["text"]
        title = note["title"]
        documents.append(
            {
                "id": _stable_id(matter.external_id, "note", index, title, text[:80]),
                "kind": "case_note",
                "title": title,
                "filename": "",
                "citation": f"{title}, {matter.external_id}",
                "source": "Case notes",
                "snippet": summarize_text(text, max_sentences=1),
                "size": len(text),
                "hasText": True,
                "needsDownload": False,
                "raw": {"text": text},
            }
        )

    raw_documents = _raw_documents(raw_payload)
    if include_remote and not raw_documents:
        try:
            legalserver = client or LegalServerClient()
            if legalserver.configured:
                raw_documents = legalserver.get_matter_documents(matter.external_id)
        except LegalServerError:
            raw_documents = []

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
                "snippet": summarize_text(inline_text, max_sentences=1) if inline_text else _clean(_first_value(raw, "description", "snippet", default="")),
                "size": len(inline_text) if inline_text else raw.get("size") or raw.get("byte_size") or None,
                "hasText": bool(inline_text or url),
                "needsDownload": bool(url and not inline_text),
                "raw": raw,
            }
        )
    return documents


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
