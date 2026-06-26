import json
import re

from django.conf import settings

from apps.ai.openai_client import OpenAIBackendError, OpenAICompatibleClient
from apps.ai.prompt_catalog import render_prompt
from apps.matters.serializers import matter_details, readable_summary
from apps.sources.connectors.legalserver import LegalServerClient, LegalServerError, _display_value, _first_value
from apps.sources.document_text import DocumentExtractionError, extract_text
from apps.sources.models import SourceConfiguration


DOCUMENT_TERMS = ("document", "documents", "file", "files", "attachment", "attachments", "pdf", "photo", "photos")
EXTRACT_TERMS = (
    "about",
    "describe",
    "extract",
    "load",
    "open",
    "read",
    "say",
    "says",
    "summarize",
    "summary",
    "tell",
    "text",
    "content",
)
SUMMARY_TERMS = ("about", "describe", "summarize", "summary", "tell")
RAW_TEXT_TERMS = ("full text", "raw text", "verbatim", "exact text", "quote")
DOCUMENT_EXTENSIONS = (".pdf", ".doc", ".docx", ".txt", ".rtf", ".html", ".htm")
NOTE_TERMS = ("note", "notes", "case note", "case notes", "history", "updates", "activity")
ACTION_TERMS = ("next step", "next steps", "what should i do", "what should we do", "suggest actions", "recommend actions")
TIMELINE_TERMS = ("happened", "so far", "timeline", "history", "events", "activity", "what happened")
PROCEED_TERMS = ("do it", "yes", "please do", "go ahead", "run it", "that one", "the first one")
DOCUMENT_STOPWORDS = {
    "about",
    "all",
    "and",
    "api",
    "call",
    "case",
    "content",
    "document",
    "documents",
    "does",
    "describe",
    "extract",
    "file",
    "files",
    "for",
    "from",
    "have",
    "needed",
    "retrieval",
    "say",
    "says",
    "summarize",
    "summary",
    "tell",
    "that",
    "the",
    "this",
    "what",
    "with",
    "would",
    "you",
}


def normalize_ai_text(text):
    return re.sub(r"<br\s*/?>", "\n", text or "", flags=re.IGNORECASE)


def compact_case_context(matter):
    details = {item["label"]: item["value"] for item in matter_details(matter)}
    return {
        "id": matter.external_id,
        "client": matter.client_name,
        "matter_type": matter.matter_type,
        "status": matter.posture,
        "jurisdiction": matter.jurisdiction,
        "summary": readable_summary(matter),
        "details": details,
    }


def document_to_dict(doc, matter_id):
    title = _display_value(_first_value(doc, "title", "name", "filename", "subject", default="Document"))
    doc_id = _display_value(_first_value(doc, "id", "document_id", "uuid", "external_id", default=title))
    return {
        "id": doc_id,
        "title": title,
        "date": _display_value(_first_value(doc, "date", "date_posted", "created_at", "updated_at", default="")),
        "type": _display_value(_first_value(doc, "type", "note_type", "document_type", "storage_provider", default="")),
        "url": _display_value(_first_value(doc, "download_url", "url", "web_url", "sharepoint_url", default="")),
        "snippet": _display_value(_first_value(doc, "summary", "description", "body", "snippet", default="")),
        "matter": matter_id,
    }


def note_to_dict(note, matter_id):
    created_by = note.get("created_by") if isinstance(note.get("created_by"), dict) else {}
    return {
        "id": _display_value(_first_value(note, "casenote_uuid", "id", "uuid", default="")),
        "subject": _display_value(_first_value(note, "subject", "title", default="Case note")),
        "date": _display_value(_first_value(note, "date_posted", "date_time_created", "created_at", "updated_at", default="")),
        "type": _display_value(_first_value(note, "note_type", "type", default="")),
        "body": _display_value(_first_value(note, "body", "text", "summary", "description", default="")),
        "createdBy": _display_value(created_by.get("user_name")) if created_by else "",
        "hasDocumentAttached": bool(note.get("note_has_document_attached")),
        "matter": matter_id,
    }


def document_candidates_from_raw_payload(matter):
    candidates = []
    for key in ("documents", "notes", "events"):
        values = matter.raw_payload.get(key) if matter.raw_payload else None
        if not isinstance(values, list):
            continue
        for value in values[:20]:
            if isinstance(value, dict):
                candidates.append(document_to_dict(value, matter.external_id))
    return candidates


def notes_from_payload(payload, matter_id):
    notes = payload.get("notes") if payload else None
    if not isinstance(notes, list):
        return []
    return [note_to_dict(note, matter_id) for note in notes[:20] if isinstance(note, dict)]


def refresh_matter_payload(matter):
    client = LegalServerClient()
    if not client.configured:
        return matter.raw_payload or {}
    identifiers = [
        matter.external_id,
        matter.raw_payload.get("matter_uuid") if matter.raw_payload else "",
        matter.raw_payload.get("case_number") if matter.raw_payload else "",
    ]
    for identifier in [item for item in identifiers if item]:
        try:
            payload = client.get_matter(identifier)
        except LegalServerError:
            continue
        if isinstance(payload, dict) and payload:
            matter.raw_payload = payload
            matter.save(update_fields=["raw_payload", "updated_at"])
            return payload
    return matter.raw_payload or {}


def get_case_notes(matter):
    notes = notes_from_payload(matter.raw_payload or {}, matter.external_id)
    if notes:
        return notes
    return notes_from_payload(refresh_matter_payload(matter), matter.external_id)


def get_case_documents(matter):
    identifiers = [
        matter.external_id,
        matter.raw_payload.get("matter_uuid") if matter.raw_payload else "",
        matter.raw_payload.get("case_number") if matter.raw_payload else "",
    ]
    client = LegalServerClient()
    if client.configured:
        for identifier in [item for item in identifiers if item]:
            try:
                docs = client.get_matter_documents(identifier)
                if docs:
                    return [document_to_dict(doc, matter.external_id) for doc in docs[:20]]
            except LegalServerError:
                continue
    return document_candidates_from_raw_payload(matter)


def should_fetch_documents(message):
    text = message.casefold()
    return any(term in text for term in DOCUMENT_TERMS) or (
        any(term in text for term in EXTRACT_TERMS) and any(extension in text for extension in DOCUMENT_EXTENSIONS)
    )


def should_fetch_notes(message):
    text = message.casefold()
    return any(term in text for term in NOTE_TERMS)


def select_relevant_documents(documents, message, *, require_match=False):
    terms = [
        term
        for term in re.split(r"[^a-z0-9_-]+", message.casefold())
        if len(term) > 2 and term not in DOCUMENT_STOPWORDS
    ]
    matches = []
    for doc in documents:
        haystack = " ".join(str(doc.get(key, "")) for key in ("title", "type", "snippet", "date")).casefold()
        if any(term in haystack for term in terms):
            matches.append(doc)
    if matches:
        return matches
    return [] if require_match and terms else documents


def should_extract_document_text(message):
    text = message.casefold()
    return should_fetch_documents(message) and any(term in text for term in EXTRACT_TERMS)


def should_summarize_document_text(message):
    text = message.casefold()
    return any(term in text for term in SUMMARY_TERMS) and not any(term in text for term in RAW_TEXT_TERMS)


def recent_conversation_text(messages, *, limit=4):
    return "\n".join(
        item.get("content", "")
        for item in messages[-limit:]
        if item.get("role") in {"user", "assistant"} and item.get("content")
    )


def is_proceed_request(message):
    text = message.casefold().strip()
    return any(term == text or term in text for term in PROCEED_TERMS)


def should_extract_from_context(latest, messages):
    context = recent_conversation_text(messages)
    return (
        should_extract_document_text(latest)
        or (
            is_proceed_request(latest)
            and should_fetch_documents(context)
            and any(term in context.casefold() for term in EXTRACT_TERMS)
        )
    )


def should_suggest_actions(message):
    text = message.casefold()
    return any(term in text for term in ACTION_TERMS)


def should_build_timeline(message):
    text = message.casefold()
    return any(term in text for term in TIMELINE_TERMS)


def extract_document_text_for_chat(document):
    url = document.get("url")
    if not url:
        return {
            "document": document,
            "error": "No downloadable URL is available for this document.",
        }
    client = LegalServerClient()
    try:
        downloaded = client.download_document(url)
        extracted = extract_text(
            downloaded["content"],
            filename=document.get("title") or downloaded["filename"],
            content_type=downloaded["content_type"],
        )
    except (LegalServerError, DocumentExtractionError) as exc:
        return {"document": document, "error": str(exc)}
    return {
        "document": document,
        "extractor": extracted["extractor"],
        "text": extracted["text"][:12000],
    }


def extractive_summary(text, *, max_sentences=5):
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return "No text was extracted from the document."
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    summary = " ".join(sentences[:max_sentences]).strip()
    return summary[:1800]


def summarize_document_text(extraction, *, llm_client=None):
    if extraction.get("error"):
        return ""
    text = extraction.get("text", "")
    fallback = extractive_summary(text)
    ai_config = SourceConfiguration.effective_settings("openai", {"enabled": settings.AI_DRAFTING_ENABLED})
    if str(ai_config.get("enabled", "")).lower() in {"0", "false", "no", "off"}:
        return fallback
    prompt = render_prompt(
        "case_chat.document_summary",
        document_title=extraction.get("document", {}).get("title", "Document"),
        document_text=text[:12000],
    )
    try:
        client = llm_client or OpenAICompatibleClient()
        return client.complete(
            system=prompt.system,
            user=prompt.user,
            temperature=0.1,
            model=prompt.default_model,
            reasoning_level=prompt.default_reasoning_level,
        )
    except OpenAIBackendError:
        return fallback


def select_relevant_notes(notes, message):
    terms = [term for term in message.casefold().replace("?", " ").replace(".", " ").split() if len(term) > 2]
    matches = []
    for note in notes:
        haystack = " ".join(str(note.get(key, "")) for key in ("subject", "type", "body", "date", "createdBy")).casefold()
        if any(term in haystack for term in terms):
            matches.append(note)
    return matches or notes


def deterministic_action_cards(case_context, tool_results):
    cards = []
    documents = tool_results.get("documents") or []
    notes = tool_results.get("case_notes") or []
    if documents:
        cards.append(
            {
                "id": "review-documents",
                "type": "review_documents",
                "title": "Review case documents",
                "summary": f"Review {len(documents)} available document(s) before drafting.",
            }
        )
    if notes:
        cards.append(
            {
                "id": "summarize-notes",
                "type": "case_chat",
                "title": "Summarize case notes",
                "summary": "Use the case notes to identify deadlines, missing documents, and procedural posture.",
                "prompt": "Summarize the case notes and identify deadlines, missing documents, and drafting issues.",
            }
        )
    cards.append(
        {
            "id": "custom-motion",
            "type": "custom_motion",
            "title": "Create a custom motion",
            "summary": "Start a scratch draft using the case posture and selected facts.",
            "instructions": f"Draft a motion or filing for {case_context['client']} based on the selected case facts and sources.",
        }
    )
    cards.append(
        {
            "id": "template-draft",
            "type": "draft_template",
            "title": "Use a document template",
            "summary": "Choose a template, select supporting facts and sources, then generate a draft.",
        }
    )
    return cards


def suggest_case_actions(case_context, tool_results, *, llm_client=None):
    cards = deterministic_action_cards(case_context, tool_results)
    fallback = (
        "Recommended next step: review the available notes and documents, then choose either a template draft "
        "or a custom motion depending on the filing you need."
    )
    ai_config = SourceConfiguration.effective_settings("openai", {"enabled": settings.AI_DRAFTING_ENABLED})
    if str(ai_config.get("enabled", "")).lower() in {"0", "false", "no", "off"}:
        return {"summary": fallback, "actions": cards}
    prompt = render_prompt(
        "case_chat.suggest_actions",
        case_context=json.dumps(case_context, indent=2),
        tool_results=json.dumps(tool_results, indent=2),
    )
    try:
        client = llm_client or OpenAICompatibleClient(model=settings.CASE_ACTION_MODEL)
        summary = client.complete(
            system=prompt.system,
            user=prompt.user,
            temperature=0.1,
            model=prompt.default_model,
            reasoning_level=prompt.default_reasoning_level,
        )
    except OpenAIBackendError:
        summary = fallback
    return {"summary": summary, "actions": cards}


def build_case_timeline(case_context, tool_results):
    events = []
    details = case_context.get("details", {})
    if details.get("Opened"):
        events.append({"date": details["Opened"], "title": "Case opened", "detail": case_context.get("summary", "")})
    for note in tool_results.get("case_notes") or []:
        events.append(
            {
                "date": note.get("date", ""),
                "title": note.get("subject") or "Case note",
                "detail": note.get("body", ""),
                "source": "LegalServer case note",
            }
        )
    for document in tool_results.get("documents") or []:
        if document.get("date"):
            events.append(
                {
                    "date": document["date"],
                    "title": f"Document: {document.get('title', 'Document')}",
                    "detail": document.get("snippet", ""),
                    "source": "LegalServer document",
                }
            )
    events.sort(key=lambda event: event.get("date") or "")
    return events[:20]


def deterministic_case_answer(message, case_context, tool_results):
    if tool_results.get("case_timeline") is not None:
        timeline = tool_results["case_timeline"]
        if not timeline:
            return "I do not see enough dated case activity to build a timeline."
        lines = [
            f"{index}. {event.get('date') or 'No date'} - {event.get('title')}: {event.get('detail', '')[:220]}"
            for index, event in enumerate(timeline, start=1)
        ]
        return "Here is the case timeline so far:\n" + "\n".join(lines)
    if tool_results.get("suggested_actions") is not None:
        return normalize_ai_text(tool_results["suggested_actions"]["summary"])
    if tool_results.get("document_text") is not None:
        extraction = tool_results["document_text"]
        if extraction.get("error"):
            return f"I could not extract text from {extraction['document'].get('title', 'the document')}: {extraction['error']}"
        if tool_results.get("document_summary"):
            return normalize_ai_text(
                f"Summary of {extraction['document'].get('title', 'the document')}:\n"
                f"{tool_results['document_summary']}"
            )
        text = extraction.get("text", "")
        return f"Extracted text from {extraction['document'].get('title', 'the document')}:\n{text[:1500]}"
    if tool_results.get("case_notes") is not None:
        notes = tool_results["case_notes"]
        if not notes:
            return "I do not see any case notes available through the current LegalServer API response."
        lines = [
            f"{index}. {note['date'] or 'No date'} - {note['subject']}: {note['body'][:220]}"
            for index, note in enumerate(notes[:10], start=1)
        ]
        return "I found these case notes:\n" + "\n".join(lines)
    if tool_results.get("documents") is not None:
        documents = tool_results["documents"]
        if not documents:
            if should_extract_from_context(message, []):
                return "I could not find a matching case document to extract text from."
            return "I do not see any case documents available through the current LegalServer API response."
        lines = [f"{index}. {doc['title']}" for index, doc in enumerate(documents[:10], start=1)]
        return "I found these case documents:\n" + "\n".join(lines)
    return (
        f"{case_context['client']} is the selected case. "
        f"Status: {case_context.get('status') or 'not listed'}. "
        f"Summary: {case_context.get('summary') or 'no summary available'}."
    )


def case_chat_reply(*, matter, messages, llm_client=None):
    latest = (messages[-1].get("content") if messages else "") or ""
    document_query = recent_conversation_text(messages) if is_proceed_request(latest) else latest
    case_context = compact_case_context(matter)
    tool_results = {}
    tools_used = []
    if should_fetch_notes(latest):
        notes = select_relevant_notes(get_case_notes(matter), latest)
        tool_results["case_notes"] = notes
        tools_used.append("legalserver.case_notes")
    if should_fetch_documents(latest) or should_extract_from_context(latest, messages):
        extracting_document = should_extract_from_context(latest, messages)
        documents = select_relevant_documents(
            get_case_documents(matter),
            document_query,
            require_match=extracting_document,
        )
        tool_results["documents"] = documents
        tools_used.append("legalserver.documents")
        if extracting_document and documents:
            tool_results["document_text"] = extract_document_text_for_chat(documents[0])
            tools_used.append("document.extract_text")
            if should_summarize_document_text(document_query):
                tool_results["document_summary"] = summarize_document_text(tool_results["document_text"], llm_client=llm_client)
                tools_used.append("document.summarize")
    if should_build_timeline(latest):
        if "case_notes" not in tool_results:
            tool_results["case_notes"] = get_case_notes(matter)
            tools_used.append("legalserver.case_notes")
        if "documents" not in tool_results:
            tool_results["documents"] = get_case_documents(matter)
            tools_used.append("legalserver.documents")
        tool_results["case_timeline"] = build_case_timeline(case_context, tool_results)
        tools_used.append("case.timeline")
    if should_suggest_actions(latest):
        if "case_notes" not in tool_results:
            tool_results["case_notes"] = get_case_notes(matter)
            tools_used.append("legalserver.case_notes")
        if "documents" not in tool_results:
            tool_results["documents"] = get_case_documents(matter)
            tools_used.append("legalserver.documents")
        tool_results["suggested_actions"] = suggest_case_actions(case_context, tool_results)
        tools_used.append("case.suggest_actions")

    ai_config = SourceConfiguration.effective_settings("openai", {"enabled": settings.AI_DRAFTING_ENABLED})
    if str(ai_config.get("enabled", "")).lower() in {"0", "false", "no", "off"}:
        return {
            "message": normalize_ai_text(deterministic_case_answer(latest, case_context, tool_results)),
            "caseContext": case_context,
            "toolsUsed": tools_used,
            "toolResults": tool_results,
            "actions": tool_results.get("suggested_actions", {}).get("actions", []),
        }
    if any(
        key in tool_results
        for key in ("documents", "document_text", "case_notes", "case_timeline", "suggested_actions")
    ):
        return {
            "message": normalize_ai_text(deterministic_case_answer(latest, case_context, tool_results)),
            "caseContext": case_context,
            "toolsUsed": tools_used,
            "toolResults": tool_results,
            "actions": tool_results.get("suggested_actions", {}).get("actions", []),
        }

    prompt = render_prompt(
        "case_chat.reply",
        case_context=json.dumps(case_context, indent=2),
        tool_results=json.dumps(tool_results, indent=2),
    )
    llm_messages = [
        {"role": "system", "content": prompt.system},
        {"role": "user", "content": prompt.user},
        *[
            {"role": item.get("role", "user"), "content": item.get("content", "")}
            for item in messages[-6:]
            if item.get("role") in {"user", "assistant"} and item.get("content")
        ],
    ]
    try:
        client = llm_client or OpenAICompatibleClient()
        answer = normalize_ai_text(
            client.complete_messages(
                messages=llm_messages,
                temperature=0.1,
                model=prompt.default_model,
                reasoning_level=prompt.default_reasoning_level,
            )
        )
    except OpenAIBackendError:
        answer = normalize_ai_text(deterministic_case_answer(latest, case_context, tool_results))
    return {
        "message": answer,
        "caseContext": case_context,
        "toolsUsed": tools_used,
        "toolResults": tool_results,
        "actions": tool_results.get("suggested_actions", {}).get("actions", []),
    }
