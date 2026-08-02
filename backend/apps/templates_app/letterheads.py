"""One parameterized letterhead instead of one document per advocate.

An organization's letterhead is a fixed masthead plus a small contact block that
changes per author. Cleveland Legal Aid maintained thirty near-identical files
that differed only in that block, so adding a advocate meant adding a document
and correcting a letterhead meant correcting thirty.

`prepare_letterhead` converts any one of those files into a template whose
contact lines are Jinja bindings, leaving the masthead image, margins, section
setup, and continuation header untouched. Values come from the author's profile
at render time.

The contact block lives in a text box in the header, and Word mirrors text-box
content into `mc:Choice` and `mc:Fallback` for older readers. Both copies are
rewritten, or the two halves of the header would disagree about who sent the
letter.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document
from lxml import etree


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_LABEL_RE = re.compile(r"^\s*(?:phone|tel|telephone|ph)\b\s*[.:]?", re.I)
FAX_LABEL_RE = re.compile(r"^\s*fax\b\s*[.:]?", re.I)
# "Letter to ______, 7/27/2023, Page 1 of 2"
CONTINUATION_RE = re.compile(r"^(?P<lead>.*?)_{3,}(?P<rest>.*)$")
# "Closing Letter, 9/5/24, Page 1 of 2" -- same header, blank already filled in
# by whichever advocate last saved the file.
DATED_CONTINUATION_RE = re.compile(
    r"^(?P<lead>.*?),\s*(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\s*,\s*(?P<rest>Page\b.*)$",
    re.I,
)

# Core-property elements that can name the advocate whose file was the source.
SCRUBBED_PROPERTY_TAGS = {
    "creator",
    "lastModifiedBy",
    "lastPrinted",
    "title",
    "subject",
    "description",
    "keywords",
    "category",
}

LETTERHEAD_VARIABLES = {
    "advocate_name": "Advocate's full name as it should appear on the letterhead.",
    "advocate_title": "Job title, e.g. \"Staff Attorney\" or \"Paralegal II\".",
    "advocate_phone": "Direct phone number.",
    "advocate_fax": "Direct fax number. The fax line is hidden when this is empty.",
    "advocate_email": "Direct email address.",
    "office_name": "Which office the advocate works from, e.g. \"Cleveland\".",
    "office_address": "Street address of that office.",
    "letter_subject": "Short description used in the continuation header.",
    "letter_date": "Date the letter is sent.",
}


@dataclass
class LetterheadPreparation:
    """What changed when an advocate's file became a shared template."""

    variables: list[str] = field(default_factory=list)
    replaced: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _paragraph_text(paragraph_element) -> str:
    return "".join(node.text or "" for node in paragraph_element.iter(W + "t"))


def _set_paragraph_text(paragraph_element, text: str):
    """Replace a paragraph's text, keeping the first run's formatting."""
    runs = list(paragraph_element.iter(W + "r"))
    text_nodes = [node for run in runs for node in run.iter(W + "t")]
    if not text_nodes:
        return False
    leading = re.match(r"\s*", _paragraph_text(paragraph_element)).group(0)
    text_nodes[0].text = f"{leading}{text}"
    text_nodes[0].set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    for node in text_nodes[1:]:
        node.text = ""
    return True


def _header_and_footer_parts(document):
    parts = []
    for section in document.sections:
        for part in (
            section.header,
            section.footer,
            section.first_page_header,
            section.first_page_footer,
            section.even_page_header,
            section.even_page_footer,
        ):
            element = getattr(part, "_element", None)
            if element is not None and element not in parts:
                parts.append(element)
    return parts


def _leaf_paragraphs(root):
    """Paragraphs that hold text directly.

    A text box's anchor paragraph contains the whole box, so its concatenated
    text looks like every contact line at once. Only leaves are real lines.
    """
    return [
        element
        for element in root.iter(W + "p")
        if _paragraph_text(element).strip()
        and not any(nested is not element for nested in element.iter(W + "p"))
    ]


def _already_bound(text: str) -> bool:
    return "{{" in text or "{%" in text


def _rewrite_contact_block(root, preparation):
    """Bind every advocate contact line in this story.

    Word mirrors text-box content into `mc:Choice` and `mc:Fallback`, so the
    same four lines appear twice. Both copies are rewritten -- stopping at the
    first would leave the fallback naming the advocate whose file was used as
    the source.
    """
    paragraphs = _leaf_paragraphs(root)
    changed = False

    for index, element in enumerate(paragraphs):
        text = _paragraph_text(element).strip()
        if _already_bound(text):
            continue

        if PHONE_LABEL_RE.match(text):
            label = PHONE_LABEL_RE.match(text)
            prefix = text[: label.end()].strip()
            if _set_paragraph_text(element, f"{prefix}  {{{{ advocate_phone }}}}"):
                preparation.replaced.append(f"phone: {text}")
                changed = True
            # The line immediately above the phone number is the name.
            if index:
                previous = paragraphs[index - 1]
                previous_text = _paragraph_text(previous).strip()
                if not _already_bound(previous_text) and not EMAIL_RE.search(previous_text):
                    if _set_paragraph_text(previous, "{{ advocate_name }}"):
                        preparation.replaced.append(f"name: {previous_text}")
                        changed = True
        elif FAX_LABEL_RE.match(text):
            label = FAX_LABEL_RE.match(text)
            prefix = text[: label.end()].strip()
            # Not every advocate publishes a fax number, so the whole line goes
            # away when the profile has none rather than printing a bare label.
            replacement = "{%% if advocate_fax %%}%s  {{ advocate_fax }}{%% endif %%}" % prefix
            if _set_paragraph_text(element, replacement):
                preparation.replaced.append(f"fax: {text}")
                changed = True
        elif EMAIL_RE.fullmatch(text.strip()):
            if _set_paragraph_text(element, "{{ advocate_email }}"):
                preparation.replaced.append(f"email: {text}")
                changed = True
    return changed


def _rewrite_continuation_header(root, preparation):
    """Turn "Letter to ______, 7/27/2023, Page 1 of 2" into bindings."""
    changed = False
    for element in _leaf_paragraphs(root):
        text = _paragraph_text(element).strip()
        if _already_bound(text):
            continue

        blank = CONTINUATION_RE.match(text) if "_" in text else None
        if blank:
            rest = blank.group("rest")
            # Drop the stale hard-coded date that follows the blank.
            rest = re.sub(r"^\s*,\s*\d{1,2}/\d{1,2}/\d{2,4}\s*,", ", {{ letter_date }},", rest)
            replacement = f"{blank.group('lead')}{{{{ letter_subject }}}}{rest}"
        else:
            dated = DATED_CONTINUATION_RE.match(text)
            if not dated:
                continue
            replacement = (
                f"{{{{ letter_subject }}}}, {{{{ letter_date }}}}, {dated.group('rest')}"
            )

        if _set_paragraph_text(element, replacement):
            preparation.replaced.append(f"continuation header: {text}")
            changed = True
    return changed


def prepare_letterhead(source: Path, output: Path) -> LetterheadPreparation:
    """Convert one advocate's letterhead into an organization-wide template."""
    preparation = LetterheadPreparation()
    document = Document(source)

    contact_rewritten = False
    for part in _header_and_footer_parts(document):
        if _rewrite_contact_block(part, preparation):
            contact_rewritten = True
        _rewrite_continuation_header(part, preparation)

    # Some of the maintained files keep the contact block in the body instead of
    # the header, depending on which advocate last saved the file.
    body = document._body._element
    if not contact_rewritten:
        contact_rewritten = _rewrite_contact_block(body, preparation)
    _rewrite_continuation_header(body, preparation)

    if not contact_rewritten:
        preparation.warnings.append(
            "No advocate contact block was found. Check the letterhead's text box "
            "and fill in the variables by hand if the layout differs."
        )

    _scrub_document_properties(document, preparation)
    _scrub_external_links(document, preparation)
    preparation.variables = _bound_variables(document)
    output.parent.mkdir(parents=True, exist_ok=True)
    document.save(output)
    return preparation


def _scrub_document_properties(document, preparation):
    """Drop the source advocate's name from the package metadata.

    The file being shared organization-wide started life as one person's copy,
    and Word records who created and last saved it. That name is invisible in
    the letterhead itself but travels with every letter built from it.
    """
    # Edited through the XML rather than `document.core_properties`. Importing
    # docxcompose -- which the export pipeline does -- replaces python-docx's
    # core-properties accessors, and the replacement reports `last_modified_by`
    # as empty. Going through it here would silently leave the source advocate's
    # name in the shared letterhead.
    element = document.core_properties._element
    for child in element:
        tag = etree.QName(child).localname
        if tag not in SCRUBBED_PROPERTY_TAGS:
            continue
        value = (child.text or "").strip()
        if not value:
            continue
        preparation.replaced.append(f"document property {tag}: {value}")
        child.text = ""


R_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _is_identifying_link(rel) -> bool:
    """Whether a relationship carries the source advocate rather than layout."""
    target = str(getattr(rel, "target_ref", "") or "")
    if rel.reltype.endswith("attachedTemplate"):
        # Points at the authoring machine, e.g. file:///C:\Users\<person>\...
        return True
    return target.lower().startswith("mailto:")


def _scrub_external_links(document, preparation):
    """Remove links that name the advocate whose copy seeded the template.

    The email line is a mailto hyperlink, and Word records the letterhead the
    file was attached to as a path on the author's own machine. Neither is
    visible in the document, and neither can be templated, so both go.
    """
    for part in document.part.package.iter_parts():
        rels = getattr(part, "rels", None)
        if not rels:
            continue
        dropped = []
        for rel_id, rel in list(rels.items()):
            if not rel.is_external or not _is_identifying_link(rel):
                continue
            preparation.replaced.append(f"link {rel.reltype.rsplit('/', 1)[-1]}: {rel.target_ref}")
            part.drop_rel(rel_id)
            dropped.append(rel_id)
        if dropped:
            _unwrap_hyperlinks(part, dropped)


def _unwrap_hyperlinks(part, dropped_ids):
    """Keep hyperlink text after its relationship is gone.

    A `w:hyperlink` whose `r:id` no longer resolves makes Word treat the file as
    corrupt, so the runs are lifted out and the wrapper removed. The visible text
    is the `{{ advocate_email }}` binding, which is what should remain.
    """
    element = getattr(part, "element", None)
    if element is None:
        return
    for hyperlink in list(element.iter(W + "hyperlink")):
        if hyperlink.get(R_ID) not in dropped_ids:
            continue
        parent = hyperlink.getparent()
        if parent is None:
            continue
        index = list(parent).index(hyperlink)
        for offset, run in enumerate(list(hyperlink)):
            parent.insert(index + offset, run)
        parent.remove(hyperlink)


VARIABLE_RE = re.compile(r"\{\{\s*([A-Za-z_][\w.]*)")


def _bound_variables(document) -> list[str]:
    """Which variables the prepared letterhead actually references."""
    stories = [document._body._element, *_header_and_footer_parts(document)]
    found = set()
    for story in stories:
        xml = etree.tostring(story, encoding="unicode")
        found.update(VARIABLE_RE.findall(xml))
    return sorted(found)


def letterhead_context(author, *, subject="", date="", office=None):
    """Values a letterhead template expects, from an author profile."""
    author = author or {}
    office = office or {}
    return {
        "advocate_name": author.get("displayName") or author.get("display_name") or "",
        "advocate_title": author.get("title") or "",
        "advocate_phone": author.get("phone") or "",
        "advocate_fax": author.get("fax") or "",
        "advocate_email": author.get("email") or "",
        "office_name": office.get("name") or author.get("officeName") or "",
        "office_address": office.get("address") or author.get("address") or "",
        "letter_subject": subject,
        "letter_date": date,
    }
