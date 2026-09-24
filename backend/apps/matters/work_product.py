"""Recognize what this tool itself wrote into a LegalServer case file.

Saving to LegalServer is on by default for documents, and chat transcripts,
research answers, triage results and AI-usage audits can be saved as notes. All
of it comes back in the case materials beside the client's evidence. Read as
evidence, it closes a loop: a drafted motion's excerpt -- unfilled placeholders
and a chat reply included -- became a "fact" in the next motion's Relevant
Facts section, cited as though it were a source.

So work product is labelled wherever materials are listed, and is never a
source of fact: not for fact recommendation, and not as the case record an
argument-gym run checks a brief against. It is still shown; an advocate may
well want to read an earlier draft.

Two signals, because either alone misses cases. A `LegalServerDelivery` row is
certain but exists only in the database that made the save -- a case file also
holds what other deployments and earlier databases wrote. The titles this tool
gives what it writes are stable and cover those.
"""

import re

from apps.matters.models import LegalServerDelivery

# Titles given by legalserver_delivery.save_draft_ai_audit, sources/views.py
# (research answers), matters/views.py (triage), and the frontend's
# chatTranscriptTitle. Keep in step with those call sites.
NOTE_TITLE_PATTERNS = (
    re.compile(r"^AI usage audit\b", re.I),
    re.compile(r"^AI research:", re.I),
    re.compile(r"^AI triage:", re.I),
    re.compile(r"^Case chat(:|$)", re.I),
)
# advice_letter_views.py saves letters under this title; drafts are saved under
# the draft's title, which is its template's.
DOCUMENT_TITLES = {"client advice letter"}


def _normalized(value):
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


class WorkProductIndex:
    """What counts as this tool's output on one matter. Build once per listing."""

    def __init__(self, matter):
        from apps.templates_app.models import DocumentTemplate

        saved = LegalServerDelivery.objects.filter(matter=matter, status=LegalServerDelivery.SAVED)
        self.remote_ids = {str(item.remote_id) for item in saved if item.remote_id}
        self.saved_names = {
            _normalized(name) for item in saved for name in (item.title, item.filename) if name
        }
        self.template_titles = {_normalized(title) for title in DocumentTemplate.objects.values_list("title", flat=True)}

    def reason(self, item):
        """A short sentence when `item` (a case_note or case_document) is work product, else ""."""
        raw = item.get("raw") or {}
        remote = {str(raw.get(key)) for key in ("id", "uuid", "document_uuid", "note_uuid") if raw.get(key)}
        if remote & self.remote_ids:
            return "Saved to this case file by the drafting tool."
        title = _normalized(item.get("title"))
        filename = _normalized(item.get("filename"))
        if item.get("kind") == "case_note":
            if any(pattern.search(item.get("title") or "") for pattern in NOTE_TITLE_PATTERNS):
                return "A note the drafting tool wrote (chat, research, triage, or AI audit)."
            if title and title in self.saved_names:
                return "Saved to this case file by the drafting tool."
            return ""
        if title in DOCUMENT_TITLES or (title and title in self.saved_names) or (filename and filename in self.saved_names):
            return "Saved to this case file by the drafting tool."
        if title in self.template_titles:
            return "Named after a drafting template: most likely a draft this tool produced."
        return ""


def label_work_product(matter, items):
    """Set `workProduct` on each item (a reason, or "") and return the items."""
    index = WorkProductIndex(matter)
    for item in items:
        item["workProduct"] = index.reason(item)
    return items


def evidence_only(items):
    """The items that are the client's material, not this tool's output."""
    return [item for item in items if not item.get("workProduct")]


def is_work_product_note(note):
    """Whether a raw LegalServer note is one this tool wrote, by its title."""
    title = ""
    if isinstance(note, dict):
        title = str(note.get("subject") or note.get("title") or note.get("name") or "")
    return any(pattern.search(title) for pattern in NOTE_TITLE_PATTERNS)


def without_work_product_notes(raw_payload):
    """A copy of a matter's raw payload without the notes this tool wrote.

    For consumers that read the whole payload as the case record -- triage
    flattens it into its prompt -- where an AI usage audit summarizing a drafted
    motion otherwise came back as evidence about the client's case.
    """
    from apps.matters.document_context import NOTE_KEYS

    cleaned = dict(raw_payload or {})
    for key in NOTE_KEYS:
        value = cleaned.get(key)
        if isinstance(value, list):
            cleaned[key] = [item for item in value if not is_work_product_note(item)]
    return cleaned
