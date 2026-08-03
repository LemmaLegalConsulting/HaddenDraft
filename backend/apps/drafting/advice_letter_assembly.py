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
from apps.templates_app.placeholders import convert_editor_state, convert_text
from apps.templates_app.template_variables import template_field_values
from apps.validation.readability import check_readability


# "[Insert next defense/advice]" left in maintained text; composition supplies
# the following section instead, so the note itself must never print.
SLOT_RE = re.compile(r"\[\s*(?:insert|section to add)\b[^\]]*\]", re.I)


@dataclass
class AssembledLetter:
    paragraphs: list = field(default_factory=list)
    rich_paragraphs: list = field(default_factory=list)
    sections: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    readability: dict = field(default_factory=dict)

    @property
    def body(self):
        return "\n".join(self.paragraphs)


def _render(text, context):
    environment = template_environment()
    return environment.from_string(text or "").render(**context)


def _normalized_section_body(section, fallback):
    body = SLOT_RE.sub("", getattr(section, "body", "") or "")
    return convert_text(body, fallback)[0]


def _rendered_lines(section, context, *, body=None, fallback="section"):
    """Render one maintained section into the editable paragraph shape."""
    rendered = _render(
        _normalized_section_body(section, fallback) if body is None else body,
        context,
    )
    lines = []
    for line in rendered.split("\n"):
        line = SLOT_RE.sub("", line).strip()
        if line:
            lines.append(line)
    return lines


def _rich_paragraphs_from_state(state):
    """Project a Lexical document state into export-friendly run objects."""
    if not isinstance(state, dict) or not isinstance(state.get("root"), dict):
        return None
    paragraphs = []
    for node in state["root"].get("children") or []:
        if node.get("type") != "paragraph":
            continue
        runs = []
        for child in node.get("children") or []:
            if child.get("type") == "text":
                runs.append(
                    {
                        "text": child.get("text", ""),
                        "format": int(child.get("format") or 0),
                    }
                )
            elif child.get("type") == "linebreak":
                runs.append({"text": "\n", "format": 0})
        paragraphs.append({"runs": runs})
    return paragraphs


def _paragraph_text(paragraph):
    return "".join(run.get("text", "") for run in paragraph.get("runs") or [])


def _state_with_children(state, children):
    if not isinstance(state, dict) or not isinstance(state.get("root"), dict):
        return None
    return {"root": {**state["root"], "children": children}}


def _state_has_text(state):
    paragraphs = _rich_paragraphs_from_state(state)
    return bool(paragraphs and any(_paragraph_text(paragraph).strip() for paragraph in paragraphs))


def _split_issue_statement(state):
    """Separate the maintained opening issue statement from later advice.

    Advice-letter source files commonly start with one or two paragraphs that
    explain the case-specific problem before the procedural advice begins. The
    source DOCX already gives us the paragraph boundaries, so expose those
    paragraphs as their own editor block without reconstructing or rewriting
    their rich text. A short one-paragraph section remains one block.
    """
    if not isinstance(state, dict) or not isinstance(state.get("root"), dict):
        return None
    children = list(state["root"].get("children") or [])
    paragraph_indexes = [
        index
        for index, node in enumerate(children)
        if node.get("type") == "paragraph"
        and any(
            child.get("type") == "text" and child.get("text", "").strip()
            for child in node.get("children") or []
        )
    ]
    if len(paragraph_indexes) < 2:
        return None

    issue_end = paragraph_indexes[1]
    issue_state = _state_with_children(state, children[: issue_end + 1])
    advice_state = _state_with_children(state, children[issue_end + 1 :])
    return issue_state, advice_state if _state_has_text(advice_state) else None


def _body_from_rendered_state(state):
    paragraphs = _rich_paragraphs_from_state(state)
    if paragraphs is None:
        return None
    return "\n".join(
        text.strip()
        for text in (_paragraph_text(paragraph) for paragraph in paragraphs)
        if text.strip()
    )


def _render_editor_state(state, context):
    """Render Jinja placeholders without flattening the Lexical formatting."""
    if not isinstance(state, dict) or not isinstance(state.get("root"), dict):
        return None
    children = []
    for node in state["root"].get("children") or []:
        if node.get("type") != "paragraph":
            continue
        rendered_children = []
        for child in node.get("children") or []:
            if child.get("type") != "text":
                rendered_children.append(dict(child))
                continue
            rendered_children.append(
                {
                    **child,
                    "text": SLOT_RE.sub("", _render(child.get("text", ""), context)),
                }
            )
        children.append({**node, "children": rendered_children})
    return {"root": {**state["root"], "children": children}}


def advice_section_source(section, *, block_role=""):
    """Return durable provenance for a catalog section used as a block."""
    content_path = getattr(section, "content_path", "") or ""
    checksum = getattr(section, "source_checksum", "") or ""
    return {
        "id": f"advice-letter:{section.slug}",
        "title": section.title,
        "sourceKind": getattr(section, "source_kind", "") or "content_library",
        "sourceLabel": content_path or "Advice-letter library",
        "citation": content_path,
        "purpose": "background_reference",
        "snippet": section.body or "",
        "metadata": {
            "contentPath": content_path,
            "sourceChecksum": checksum,
            "sectionSlug": section.slug,
            **({"blockRole": block_role} if block_role else {}),
        },
    }


def advice_draft_sections(
    sections,
    *,
    intro=None,
    closing=None,
    author_profile=None,
    matter=None,
    template_data=None,
):
    """Build the block shape used by the shared rich-text draft editor.

    The catalog remains the source of maintained wording. The returned body is
    the rendered starting point, while the source descriptor and review fields
    travel with the block so later human/AI versions can be audited.
    """
    context = render_context(
        author_profile=author_profile, matter=matter, template_data=template_data
    )
    ordered = []
    if intro is not None:
        ordered.append(intro)
    ordered.extend(sections)
    if closing is not None:
        ordered.append(closing)

    payload = []
    for index, section in enumerate(ordered, start=1):
        fallback = f"advice_section_{index}"
        body = _normalized_section_body(section, fallback)
        source_state, _conversion = convert_editor_state(
            getattr(section, "editor_state", None), fallback
        )

        def block_payload(
            *,
            key,
            label,
            state,
            block_role="",
            ai_latitude="guided",
            fallback_body=None,
        ):
            rendered_state = _render_editor_state(state, context)
            rendered_body = _body_from_rendered_state(rendered_state)
            if rendered_body is None:
                rendered_body = "\n".join(
                    _rendered_lines(
                        section,
                        context,
                        body=body if fallback_body is None else fallback_body,
                        fallback=fallback,
                    )
                )
            return {
                "key": key,
                "label": label,
                "body": rendered_body,
                "sources": [advice_section_source(section, block_role=block_role)],
                "blockType": "advice_letter_issue" if block_role else "advice_letter_section",
                "aiFillMode": "none",
                "aiLatitude": ai_latitude,
                "origin": "template",
                "adviceSectionSlug": section.slug,
                "adviceSectionTitle": section.title,
                "adviceBlockRole": block_role,
                "status": getattr(section, "status", "ready"),
                "needsReview": bool(getattr(section, "needs_attorney_review", False)),
                "reviewReason": getattr(section, "review_summary", ""),
                "notes": list(getattr(section, "notes", None) or []),
                "format": {"style": "plain", "headingNumbering": "none"},
                "sourceEditorState": rendered_state,
            }

        # Body sections often begin with the maintained explanation of the
        # issue in this case. Make that explanation a visible, locked block so
        # an advocate can review/edit it directly and AI redrafting cannot
        # accidentally turn a deterministic case statement into new law.
        split = _split_issue_statement(source_state) if getattr(section, "role", "body") == "body" else None
        if split:
            issue_state, advice_state = split
            payload.append(
                block_payload(
                    key=f"issue-statement-{section.slug}",
                    label=f"{section.title}: issue statement",
                    state=issue_state,
                    block_role="issue_statement",
                    ai_latitude="locked",
                )
            )
            if advice_state is not None:
                payload.append(
                    block_payload(
                        key=section.slug,
                        label=section.title,
                        state=advice_state,
                        fallback_body=body,
                    )
                )
            continue

        payload.append(
            block_payload(
                key=section.slug,
                label=section.title,
                state=source_state,
                fallback_body=body,
            )
        )
    return payload


def letter_from_draft_sections(sections, *, kind="advice", editor_state=None):
    """Rebuild a letter preview from the current editable blocks."""
    letter = AssembledLetter()
    block_states = (editor_state or {}).get("blocks") or {}
    seen_advice_sections = set()
    for section in sections or []:
        # Draft editor state is already the rendered, user-facing projection.
        # Do not turn an unresolved visible `[Field]` back into Jinja here: this
        # path has no case context, and doing so would export literal template
        # syntax instead of the clear missing-value marker.
        body = SLOT_RE.sub("", section.get("body") or "")
        block_state = block_states.get(section.get("key"))
        if block_state is None and section.get("origin") != "ai":
            block_state = section.get("sourceEditorState")
        rich_paragraphs = _rich_paragraphs_from_state(block_state)
        if rich_paragraphs is None:
            rich_paragraphs = [
                {"runs": [{"text": line, "format": 0}]}
                for line in body.split("\n")
            ]
        letter.rich_paragraphs.extend(rich_paragraphs)
        letter.paragraphs.extend(
            line.strip()
            for line in (_paragraph_text(paragraph) for paragraph in rich_paragraphs)
            if line.strip()
        )
        advice_slug = section.get("adviceSectionSlug") or section.get("key", "")
        if advice_slug not in seen_advice_sections:
            seen_advice_sections.add(advice_slug)
            needs_review = bool(section.get("needsReview"))
            reason = section.get("reviewReason") or section.get("status") or ""
            display_title = section.get("adviceSectionTitle") or section.get("label", "")
            if needs_review:
                letter.warnings.append(
                    f"{display_title}: {reason}. Read it before sending."
                )
            for note in section.get("notes") or []:
                letter.warnings.append(f"{display_title}: {note}")
            letter.sections.append(
                {
                    "slug": advice_slug,
                    "title": display_title,
                    "status": section.get("status", "ready"),
                    "needsReview": needs_review,
                    "reviewReason": reason if needs_review else "",
                }
            )

    report = check_readability(letter.body, kind=kind)
    letter.readability = report.as_dict()
    if not report.passed:
        letter.warnings.append(
            f"Readability: {len(report.warnings)} item(s) miss the plain-language targets."
        )
    return letter


def render_context(*, author_profile=None, matter=None, template_data=None):
    """Values the maintained section text binds to.

    Client details come from the case rather than from the advocate retyping
    them; a letter that greets "[Client]" is the failure this prevents.
    """
    from apps.matters.client_letter_context import (
        client_letter_context,
        letter_template_fields,
        salutation_name,
    )

    author = author_profile or {}
    data = template_data or {}
    case = client_letter_context(matter) if matter is not None else {}
    case_fields, field_sources = letter_template_fields(matter) if matter is not None else ({}, {})
    merged_fields = {**case_fields, **data}
    return {
        "client_name": salutation_name(case.get("recipientName", "")),
        "matter_subject": case.get("matterSubject", "housing issue"),
        "case_reference": case.get("caseReference", ""),
        "fields": template_field_values(merged_fields),
        "field_sources": field_sources,
        "client": {"name": getattr(matter, "client_name", "")},
        "defendant": salutation_name(case.get("recipientName", "")) or getattr(matter, "client_name", ""),
        "court": getattr(matter, "jurisdiction", ""),
        "case_number": (
            data.get("court_case_number")
            or merged_fields.get("case_number")
            or case.get("caseNumber", "")
        ),
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

        fallback = f"advice_section_{len(letter.sections) + 1}"
        normalized_body = _normalized_section_body(section, fallback)
        rendered_lines = _rendered_lines(
            section, context, body=normalized_body, fallback=fallback
        )
        normalized_state, _conversion = convert_editor_state(
            getattr(section, "editor_state", None), fallback
        )
        rendered_state = _render_editor_state(normalized_state, context)
        rich_paragraphs = _rich_paragraphs_from_state(rendered_state)
        if rich_paragraphs is None:
            letter.paragraphs.extend(rendered_lines)
            rich_paragraphs = [
                {"runs": [{"text": line, "format": 0}]}
                for line in rendered_lines
            ]
        else:
            # The plain projection above is what readability checks; the rich
            # projection is what the editor and DOCX export display.
            letter.paragraphs.extend([
                _paragraph_text(paragraph).strip()
                for paragraph in rich_paragraphs
                if _paragraph_text(paragraph).strip()
            ])
        letter.rich_paragraphs.extend(rich_paragraphs)
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
    prefix = []
    if request.deadline:
        prefix.extend([request.deadline, ""])
    if request.recipient_name:
        prefix.append(request.recipient_name)
    if request.recipient_address:
        prefix.extend(request.recipient_address.splitlines())
    if request.recipient_name or request.recipient_address:
        prefix.append("")
    for method in request.delivery:
        prefix.append(f"Sent via {method}")
    if request.delivery:
        prefix.append("")
    if request.subject:
        prefix.extend([f"Re: {request.subject}", ""])
    prefix.extend([f"Dear {request.recipient_name or '[Client]'}:", ""])
    suffix = ["", author.get("signoff") or "Sincerely,", "", author.get("displayName", "")]
    if author.get("title"):
        suffix.append(author["title"])

    lines = prefix + letter.paragraphs + suffix
    body_rich = letter.rich_paragraphs or [
        {"runs": [{"text": line, "format": 0}]} for line in letter.paragraphs
    ]
    formatted_body = (
        [{"runs": [{"text": line, "format": 0}]} for line in prefix]
        + body_rich
        + [{"runs": [{"text": line, "format": 0}]} for line in suffix]
    )

    return compose_letter_docx(
        "\n".join(lines),
        author_profile=author_profile,
        request=request,
        output_path=output_path,
        formatted_body=formatted_body,
    )
