"""Case note bodies for work saved back to LegalServer.

A note written to a client's case file outlives the session that produced it and
will be read by someone who was not there, so each body says what produced it,
what it was asked, and that it has not been checked by an attorney.
"""

import json

from apps.drafting.audit import ai_audit_counts

REVIEW_FOOTER = (
    "Written by the AI drafting tool as a working aid. It has not been reviewed "
    "by an attorney and is not a substitute for checking current law."
)


def _section(heading, body):
    body = (body or "").strip()
    return f"{heading}:\n{body}" if body else ""


def _bullets(items, limit=12):
    return "\n".join(f"- {item}" for item in list(items or [])[:limit] if str(item).strip())


def triage_case_note_body(assessment):
    """Summarize a triage assessment for the case file."""
    rubric = getattr(assessment, "rubric", None)
    parts = [
        _section("Rubric", getattr(rubric, "name", "")),
        _section("Outcome", assessment.priority_label or ("Priority" if assessment.priority else "")),
        _section("Confidence", assessment.confidence),
        _section("Legal problem", assessment.case_type),
        _section("Summary", assessment.summary),
        _section("Reasoning", assessment.reasoning),
        _section("Criteria met", _bullets(assessment.matched_criteria)),
        _section("Missing information", _bullets(assessment.missing_information)),
        REVIEW_FOOTER,
    ]
    return "\n\n".join(part for part in parts if part)


def research_case_note_body(*, question, answer, citations=(), jurisdiction=""):
    """Record a research question and the answer it produced."""
    sources = _bullets(
        [
            " - ".join(
                str(value)
                for value in (citation.get("citation") or citation.get("title"), citation.get("url"))
                if value
            )
            if isinstance(citation, dict)
            else str(citation)
            for citation in citations or ()
        ]
    )
    parts = [
        _section("Question", question),
        _section("Jurisdiction", jurisdiction),
        _section("Answer", answer),
        _section("Sources consulted", sources),
        REVIEW_FOOTER,
    ]
    return "\n\n".join(part for part in parts if part)


def document_case_note_body(*, title, filename, template="", summary=""):
    """Note the fact of a generated document, for sites that want a trail."""
    parts = [
        _section("Document", title),
        _section("File", filename),
        _section("Template", template),
        _section("Summary", summary),
        REVIEW_FOOTER,
    ]
    return "\n\n".join(part for part in parts if part)


def ai_audit_case_note(audit):
    """Render a stable, human-readable audit of model-written draft parts."""
    counts = ai_audit_counts(audit)
    document = audit.get("document") or {}
    lines = [
        "AI USAGE AUDIT",
        "",
        f"Document: {document.get('title') or 'Untitled draft'} (draft {document.get('draftId')})",
        f"Audit updated: {audit.get('createdAt', '')}",
        (
            f"Recorded AI interactions: {counts['interactions']}; "
            f"AI output paragraphs: {counts['paragraphs']}; sources: {counts['sources']}."
        ),
    ]
    for interaction in audit.get("aiInteractions") or []:
        current = "current" if interaction.get("isCurrentVersion") else "superseded"
        lines.extend(
            [
                "",
                (
                    f"[{interaction.get('componentKey')}] {interaction.get('componentLabel')} — "
                    f"AI version {interaction.get('componentVersion')} ({current}), "
                    f"{interaction.get('createdAt')}"
                ),
            ]
        )
        if interaction.get("instruction"):
            lines.append(f"Instruction: {interaction['instruction']}")
        lines.append("AI output:")
        for paragraph in interaction.get("paragraphs") or []:
            lines.append(f"  {paragraph.get('index')}. {paragraph.get('text', '')}")
        bindings = interaction.get("sources") or []
        if bindings:
            lines.append("Sources:")
        for source in bindings:
            label = source.get("label") or source.get("citation") or source.get("sourceKey") or "Source"
            details = [source.get("role", ""), source.get("supportType", ""), source.get("citation", "")]
            lines.append(f"  - {label}" + " | " + " | ".join(item for item in details if item))
            if source.get("locator"):
                lines.append(f"    Locator: {json.dumps(source['locator'], sort_keys=True)}")
            if source.get("excerpt"):
                lines.append(f"    Excerpt: {source['excerpt']}")
    lines.extend(["", REVIEW_FOOTER])
    return "\n".join(lines).strip()
