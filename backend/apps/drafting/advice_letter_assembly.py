"""Assembling a client advice letter from the wrapper and chosen sections.

A letter is the Model Letter's opening, the sections the advocate picked in the
order they picked them, and the Model Letter's closing -- composed onto the
organization's letterhead through the same path an ordinary letter takes.

Composition is deliberately deterministic. The model's job in this workflow is
choosing sections and filling their blanks, not writing the advice: the wording
is what the working group revised for readability, and regenerating it would
throw that work away. Readability is scored after assembly so an advocate sees
what the client will face.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from apps.drafting.letters import LetterRequest, compose_letter_docx
from apps.templates_app.jinja_filters import template_environment
from apps.templates_app.template_variables import template_field_values
from apps.validation.readability import check_readability


# "[Insert next defense/advice]" left in maintained text; composition supplies
# the following section instead, so the note itself must never print.
SLOT_RE = re.compile(r"\[\s*(?:insert|section to add)\b[^\]]*\]", re.I)


@dataclass
class AssembledLetter:
    paragraphs: list = field(default_factory=list)
    sections: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    readability: dict = field(default_factory=dict)

    @property
    def body(self):
        return "\n".join(self.paragraphs)


def _render(text, context):
    environment = template_environment()
    return environment.from_string(text or "").render(**context)


def render_context(*, author_profile=None, matter=None, template_data=None):
    """Values the maintained section text binds to.

    Client details come from the case rather than from the advocate retyping
    them; a letter that greets "[Client]" is the failure this prevents.
    """
    from apps.matters.client_letter_context import client_letter_context, salutation_name

    author = author_profile or {}
    data = template_data or {}
    case = client_letter_context(matter) if matter is not None else {}
    return {
        "client_name": salutation_name(case.get("recipientName", "")),
        "matter_subject": case.get("matterSubject", "housing issue"),
        "case_reference": case.get("caseReference", ""),
        "fields": template_field_values(data),
        "client": {"name": getattr(matter, "client_name", "")},
        "defendant": salutation_name(case.get("recipientName", "")) or getattr(matter, "client_name", ""),
        "court": getattr(matter, "jurisdiction", ""),
        "case_number": data.get("court_case_number") or case.get("caseNumber", ""),
        "advocate_name": author.get("displayName", ""),
        "advocate_title": author.get("title", ""),
        "advocate_phone": author.get("phone", ""),
        "advocate_email": author.get("email", ""),
        "advocate_signoff": author.get("signoff") or "Sincerely,",
    }


def assemble_letter(
    sections,
    *,
    intro=None,
    closing=None,
    author_profile=None,
    matter=None,
    template_data=None,
    kind="advice",
) -> AssembledLetter:
    """Build the letter body from the wrapper and the chosen sections."""
    context = render_context(
        author_profile=author_profile, matter=matter, template_data=template_data
    )
    letter = AssembledLetter()

    ordered = []
    if intro is not None:
        ordered.append(intro)
    ordered.extend(sections)
    if closing is not None:
        ordered.append(closing)

    for section in ordered:
        status = getattr(section, "status", "ready")
        if getattr(section, "needs_attorney_review", False):
            reason = getattr(section, "review_summary", "") or status
            letter.warnings.append(f"{section.title}: {reason}. Read it before sending.")
        for note in getattr(section, "notes", None) or []:
            letter.warnings.append(f"{section.title}: {note}")

        rendered = _render(section.body or "", context)
        for line in rendered.split("\n"):
            line = SLOT_RE.sub("", line).strip()
            if line:
                letter.paragraphs.append(line)
        letter.sections.append(
            {
                "slug": section.slug,
                "title": section.title,
                "status": status,
                "needsReview": bool(getattr(section, "needs_attorney_review", False)),
                "reviewReason": getattr(section, "review_summary", ""),
            }
        )

    report = check_readability(letter.body, kind=kind)
    letter.readability = report.as_dict()
    if not report.passed:
        letter.warnings.append(
            f"Readability: {len(report.warnings)} item(s) miss the plain-language targets."
        )
    return letter


def compose_advice_letter_docx(
    letter: AssembledLetter,
    *,
    author_profile=None,
    request: LetterRequest = None,
    output_path: Path,
):
    """Put an assembled letter onto the organization's letterhead."""
    request = request or LetterRequest(letter_kind="advice")
    author = author_profile or {}
    lines = []
    if request.deadline:
        lines.extend([request.deadline, ""])
    if request.recipient_name:
        lines.append(request.recipient_name)
    if request.recipient_address:
        lines.extend(request.recipient_address.splitlines())
    if request.recipient_name or request.recipient_address:
        lines.append("")
    for method in request.delivery:
        lines.append(f"Sent via {method}")
    if request.delivery:
        lines.append("")
    if request.subject:
        lines.extend([f"Re: {request.subject}", ""])
    lines.append(f"Dear {request.recipient_name or '[Client]'}:")
    lines.append("")
    lines.extend(letter.paragraphs)
    lines.extend(["", author.get("signoff") or "Sincerely,", "", author.get("displayName", "")])
    if author.get("title"):
        lines.append(author["title"])

    return compose_letter_docx(
        "\n".join(lines),
        author_profile=author_profile,
        request=request,
        output_path=output_path,
    )
