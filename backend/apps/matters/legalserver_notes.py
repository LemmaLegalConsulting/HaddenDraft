"""Case note bodies for work saved back to LegalServer.

A note written to a client's case file outlives the session that produced it and
will be read by someone who was not there, so each body says what produced it,
what it was asked, and that it has not been checked by an attorney.
"""

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
