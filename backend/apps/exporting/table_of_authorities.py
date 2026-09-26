"""Word's native table of authorities, marked and built at export.

A document that carries a ``TOA`` field gets every recognized citation marked
with a ``TA`` field -- the same field Word's Mark Citation dialog (Alt+Shift+I)
inserts -- and each ``TOA`` field filled with the authorities of its category.
The table is therefore Word's own: an advocate who adds a citation marks it and
presses F9, and the table rebuilds. Nothing here pretends to be Word.

Page numbers are the one thing this cannot produce. A page number exists only
once something lays the document out, so the ``TOA`` fields are flagged dirty
and the document asks Word to update its fields on open. Until it does, the
table lists its authorities without pages, and the report says so -- it never
reports the pages as checked.

A document with no ``TOA`` field is returned unchanged: marking citations
nobody asked a table for would plant fields in every letter and memo.
"""

from __future__ import annotations

import copy
import io
import re
import zipfile

from lxml import etree

from apps.exporting.authorities import category_numbers, collect_authorities, load_config


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{W_NS}}}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

TOA_ENTRY_STYLE = "TableofAuthorities"
TOA_HEADING_STYLE = "TOAHeading"
# Paragraph styles that belong to generated tables, whose text is the table
# and never a citation to mark.
GENERATED_TABLE_STYLES = {TOA_ENTRY_STYLE, TOA_HEADING_STYLE, "TOCHeading"} | {f"TOC{level}" for level in range(1, 10)}
TABLE_FIELD_RE = re.compile(r"^\s*(TOA|TOC)\b")
TOA_CATEGORY_RE = re.compile(r'\\c\s+"?(\d+)"?')
# Word reads CT_Settings in schema order; updateFields must precede these.
SETTINGS_AFTER_UPDATE_FIELDS = (
    "hdrShapeDefaults", "footnotePr", "endnotePr", "compat", "docVars", "rsids", "mathPr",
    "attachedSchema", "themeFontLang", "clrSchemeMapping", "doNotIncludeSubdocsInStats",
    "doNotAutoCompressPictures", "forceUpgrade", "captions", "readModeInkLockDown",
    "smartTagType", "schemaLibrary", "shapeDefaults", "doNotEmbedSmartTags",
    "decimalSymbol", "listSeparator",
)

STYLE_DEFINITIONS = {
    TOA_ENTRY_STYLE: (
        f'<w:style xmlns:w="{W_NS}" w:type="paragraph" w:styleId="{TOA_ENTRY_STYLE}">'
        '<w:name w:val="table of authorities"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/>'
        '<w:uiPriority w:val="99"/><w:unhideWhenUsed/>'
        '<w:pPr><w:tabs><w:tab w:val="right" w:leader="dot" w:pos="9350"/></w:tabs>'
        '<w:spacing w:after="120" w:line="240" w:lineRule="auto"/><w:ind w:left="240" w:hanging="240"/></w:pPr>'
        "</w:style>"
    ),
    TOA_HEADING_STYLE: (
        f'<w:style xmlns:w="{W_NS}" w:type="paragraph" w:styleId="{TOA_HEADING_STYLE}">'
        '<w:name w:val="toa heading"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/>'
        '<w:uiPriority w:val="99"/><w:unhideWhenUsed/>'
        '<w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/></w:pPr><w:rPr><w:b/><w:bCs/></w:rPr>'
        "</w:style>"
    ),
}


def _w(tag):
    return f"{W}{tag}"


def _paragraph_style(paragraph):
    style = paragraph.find(f"{_w('pPr')}/{_w('pStyle')}")
    return style.get(_w("val")) if style is not None else ""


def _field_instructions(paragraphs):
    """Map each paragraph to the instruction of every complex field it opens.

    Returns ``(opened, spans)`` where ``spans`` lists, for each table field
    (TOA/TOC), the index of the paragraph that opens it and the one that closes
    it -- a generated table's result runs across many paragraphs.
    """
    spans = []
    stack = []
    for index, paragraph in enumerate(paragraphs):
        for element in paragraph.iter(_w("fldChar"), _w("instrText")):
            if element.tag == _w("fldChar"):
                kind = element.get(_w("fldCharType"))
                if kind == "begin":
                    stack.append({"start": index, "instr": "", "begin": element})
                elif kind == "end" and stack:
                    field = stack.pop()
                    field["end"] = index
                    if TABLE_FIELD_RE.match(field["instr"]):
                        spans.append(field)
            elif stack:
                stack[-1]["instr"] += element.text or ""
    return spans


def _text_segments(paragraph):
    """The paragraph's visible text, and where each character lives.

    Field instructions are skipped, field results are read, and tabs, breaks,
    and Word's non-breaking hyphen count as the characters they print as.
    """
    segments = []
    depth = 0
    in_instruction = []
    for run in paragraph.iter(_w("r")):
        for child in run:
            if child.tag == _w("fldChar"):
                kind = child.get(_w("fldCharType"))
                if kind == "begin":
                    depth += 1
                    in_instruction.append(True)
                elif kind == "separate" and in_instruction:
                    in_instruction[-1] = False
                elif kind == "end" and in_instruction:
                    depth -= 1
                    in_instruction.pop()
                continue
            if in_instruction and in_instruction[-1]:
                continue
            if child.tag == _w("t"):
                text = child.text or ""
            elif child.tag == _w("tab"):
                text = "\t"
            elif child.tag in {_w("br"), _w("cr")}:
                text = "\n"
            elif child.tag == _w("noBreakHyphen"):
                text = "-"
            else:
                continue
            if text:
                segments.append((run, child, text))
    return segments


def _split_run_after(run, child, offset):
    """Split ``run`` so the text through ``offset`` of ``child`` ends it.

    Returns the run after which a field may be inserted. Formatting is copied to
    the second half, so the text after the split looks exactly as before.
    """
    children = list(run)
    position = children.index(child)
    text = child.text or "" if child.tag == _w("t") else None
    trailing_children = children[position + 1:]
    remainder = text[offset:] if text is not None else ""
    if not remainder and not trailing_children:
        return run
    tail = etree.Element(_w("r"), nsmap=run.nsmap)
    properties = run.find(_w("rPr"))
    if properties is not None:
        tail.append(copy.deepcopy(properties))
    if remainder:
        child.text = text[:offset]
        child.set(XML_SPACE, "preserve")
        tail_text = etree.SubElement(tail, _w("t"))
        tail_text.text = remainder
        tail_text.set(XML_SPACE, "preserve")
    for moved in trailing_children:
        run.remove(moved)
        tail.append(moved)
    run.addnext(tail)
    return run


# CT_RPr is a sequence; <w:i> must come before these or Word rejects the file.
_RPR_AFTER_ITALIC = {
    "caps", "smallCaps", "strike", "dstrike", "outline", "shadow", "emboss", "imprint", "noProof",
    "snapToGrid", "vanish", "webHidden", "color", "spacing", "w", "kern", "position", "sz", "szCs",
    "highlight", "u", "effect", "bdr", "shd", "fitText", "vertAlign", "rtl", "cs", "em", "lang",
    "eastAsianLayout", "specVanish", "oMath",
}


def _set_italic(run):
    properties = run.find(_w("rPr"))
    if properties is None:
        properties = etree.Element(_w("rPr"))
        run.insert(0, properties)
    if properties.find(_w("i")) is not None:
        return
    anchor = next(
        (child for child in properties if etree.QName(child).localname in _RPR_AFTER_ITALIC),
        None,
    )
    for tag in ("i", "iCs"):
        element = etree.Element(_w(tag))
        if anchor is not None:
            anchor.addprevious(element)
        else:
            properties.append(element)


def _boundaries(paragraph):
    boundaries = []
    position = 0
    for run, child, text in _text_segments(paragraph):
        boundaries.append((position, position + len(text), run, child))
        position += len(text)
    return boundaries


def _split_at(paragraph, position):
    """Make ``position`` a run boundary, splitting the run that straddles it."""
    for start, end, run, child in _boundaries(paragraph):
        if start < position < end and child.tag == _w("t"):
            _split_run_after(run, child, position - start)
            return


def _italicize(paragraph, span):
    start, end = span
    _split_at(paragraph, start)
    _split_at(paragraph, end)
    for run_start, run_end, run, child in _boundaries(paragraph):
        if child.tag == _w("t") and start <= run_start and run_end <= end:
            _set_italic(run)


def _field_quote(text):
    # Inside a field code a literal quotation mark is escaped with a backslash.
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _instruction_run(text, *, italic=False):
    run = etree.Element(_w("r"))
    if italic:
        properties = etree.SubElement(run, _w("rPr"))
        etree.SubElement(properties, _w("i"))
        etree.SubElement(properties, _w("iCs"))
    instruction = etree.SubElement(run, _w("instrText"))
    instruction.text = text
    instruction.set(XML_SPACE, "preserve")
    return run


def _char_run(kind, *, dirty=False):
    run = etree.Element(_w("r"))
    char = etree.SubElement(run, _w("fldChar"))
    char.set(_w("fldCharType"), kind)
    if dirty:
        char.set(_w("dirty"), "true")
    return run


def ta_field_runs(authority, *, first, category_number):
    """The runs of one TA field, as Word's Mark Citation writes them."""
    runs = [_char_run("begin")]
    short = _field_quote(authority.short_cite)
    if first:
        long_cite = authority.long_cite
        runs.append(_instruction_run(' TA \\l "'))
        if authority.italic:
            start, end = authority.italic
            if start:
                runs.append(_instruction_run(_field_quote(long_cite[:start])))
            runs.append(_instruction_run(_field_quote(long_cite[start:end]), italic=True))
            if long_cite[end:]:
                runs.append(_instruction_run(_field_quote(long_cite[end:])))
        else:
            runs.append(_instruction_run(_field_quote(long_cite)))
        runs.append(_instruction_run(f'" \\s "{short}" \\c {category_number} '))
    else:
        runs.append(_instruction_run(f' TA \\s "{short}" '))
    runs.append(_char_run("end"))
    return runs


def _mark_paragraph(paragraph, occurrences, registry, numbers):
    if not occurrences:
        return 0
    # Case names are italicized in the brief as in the table. Splitting runs
    # for italics moves run boundaries, so the text map is read after it.
    for occurrence in occurrences:
        if occurrence.name_span:
            _italicize(paragraph, occurrence.name_span)
    boundaries = _boundaries(paragraph)
    marked = 0
    # Right to left, so an insertion never shifts a later offset.
    for occurrence in sorted(occurrences, key=lambda item: item.end, reverse=True):
        target = next(
            (item for item in boundaries if item[0] < occurrence.end <= item[1] and item[3].tag == _w("t")),
            None,
        )
        if target is None:
            continue
        start, _end, run, child = target
        anchor = _split_run_after(run, child, occurrence.end - start)
        authority = registry.authorities[occurrence.key]
        for field_run in reversed(
            ta_field_runs(authority, first=occurrence.first, category_number=numbers[authority.category])
        ):
            anchor.addnext(field_run)
        marked += 1
    return marked


def _entry_paragraph(authority, template_properties):
    paragraph = etree.Element(_w("p"))
    if template_properties is not None:
        properties = copy.deepcopy(template_properties)
        for child in list(properties):
            if child.tag in {_w("rPr"), _w("sectPr"), _w("numPr")}:
                properties.remove(child)
        paragraph.append(properties)
    else:
        properties = etree.SubElement(paragraph, _w("pPr"))
    style = properties.find(_w("pStyle"))
    if style is None:
        style = etree.Element(_w("pStyle"))
        properties.insert(0, style)
    style.set(_w("val"), TOA_ENTRY_STYLE)

    def text_run(text, *, italic=False):
        run = etree.SubElement(paragraph, _w("r"))
        if italic:
            run_properties = etree.SubElement(run, _w("rPr"))
            etree.SubElement(run_properties, _w("i"))
            etree.SubElement(run_properties, _w("iCs"))
        element = etree.SubElement(run, _w("t"))
        element.text = text
        element.set(XML_SPACE, "preserve")

    if authority.italic:
        start, end = authority.italic
        if start:
            text_run(authority.long_cite[:start])
        text_run(authority.long_cite[start:end], italic=True)
        if authority.long_cite[end:]:
            text_run(authority.long_cite[end:])
    else:
        text_run(authority.long_cite)
    tab_run = etree.SubElement(paragraph, _w("r"))
    etree.SubElement(tab_run, _w("tab"))
    return paragraph


def _rebuild_toa_field(paragraphs, field, entries):
    """Replace one TOA field's result with ``entries``, keeping its instruction."""
    first = paragraphs[field["start"]]
    template_properties = first.find(_w("pPr"))
    new_paragraphs = [_entry_paragraph(authority, template_properties) for authority in entries]
    opening = new_paragraphs[0]
    # begin, instruction, separate -- then the first entry's own runs.
    field_head = [_char_run("begin", dirty=True), _instruction_run(f" {field['instr'].strip()} "), _char_run("separate")]
    insert_at = 1 if opening.find(_w("pPr")) is not None else 0
    for offset, run in enumerate(field_head):
        opening.insert(insert_at + offset, run)
    new_paragraphs[-1].append(_char_run("end"))
    for paragraph in new_paragraphs:
        first.addprevious(paragraph)
    for paragraph in paragraphs[field["start"]: field["end"] + 1]:
        paragraph.getparent().remove(paragraph)


def _remove_toa_field(paragraphs, field):
    first = paragraphs[field["start"]]
    heading = first.getprevious()
    for paragraph in paragraphs[field["start"]: field["end"] + 1]:
        paragraph.getparent().remove(paragraph)
    if heading is not None and heading.tag == _w("p") and _paragraph_style(heading) == TOA_HEADING_STYLE:
        heading.getparent().remove(heading)


def _ensure_update_fields(settings_xml):
    root = etree.fromstring(settings_xml)
    existing = root.find(_w("updateFields"))
    if existing is None:
        existing = etree.Element(_w("updateFields"))
        anchor = next(
            (child for child in root if etree.QName(child).localname in SETTINGS_AFTER_UPDATE_FIELDS),
            None,
        )
        if anchor is not None:
            anchor.addprevious(existing)
        else:
            root.append(existing)
    existing.set(_w("val"), "true")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _ensure_styles(styles_xml):
    root = etree.fromstring(styles_xml)
    present = {style.get(_w("styleId")) for style in root.findall(_w("style"))}
    for style_id, definition in STYLE_DEFINITIONS.items():
        if style_id not in present:
            root.append(etree.fromstring(definition))
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def apply_table_of_authorities(docx_bytes, config=None):
    """Mark citations and fill TOA fields. Returns ``(docx_bytes, report)``.

    ``report`` is ``None`` when the document has no TOA field, so a caller can
    tell "no table was asked for" from "a table with nothing in it".
    """
    source = zipfile.ZipFile(io.BytesIO(docx_bytes))
    document = etree.fromstring(source.read("word/document.xml"))
    body = document.find(_w("body"))
    paragraphs = list(body.iter(_w("p")))
    spans = _field_instructions(paragraphs)
    toa_fields = [field for field in spans if field["instr"].strip().startswith("TOA")]
    if not toa_fields:
        return docx_bytes, None

    config = config or load_config()
    numbers = category_numbers(config)
    categories_by_number = {number: key for key, number in numbers.items()}
    if any((text.text or "").lstrip().startswith("TA ") for text in body.iter(_w("instrText"))):
        # The author marked citations in Word. Their marks and their table are
        # theirs: adding marks of our own, or rebuilding a table from only the
        # citations we recognize, would drop entries they chose. Word is still
        # asked to refresh the table when the file opens.
        return _rewrite_parts(source, document), {
            "authorities": [],
            "unmarked": [],
            "marked": 0,
            "categories": [],
            "authorMarked": True,
            "pageNumbers": "unmeasured",
            "pageNumbersReason": (
                "This document's citations were marked in Word, so its table was left as the author built it. "
                "Word fills in page numbers when it updates the table's fields."
            ),
        }
    excluded = set()
    for field in spans:
        excluded.update(range(field["start"], field["end"] + 1))
    readable = [
        paragraph
        for index, paragraph in enumerate(paragraphs)
        if index not in excluded and _paragraph_style(paragraph) not in GENERATED_TABLE_STYLES
    ]

    registry, marks = collect_authorities(["".join(text for _run, _child, text in _text_segments(p)) for p in readable], config)
    marked = sum(
        _mark_paragraph(paragraph, occurrences, registry, numbers)
        for paragraph, occurrences in zip(readable, marks)
    )

    grouped = registry.by_category()
    filled = []
    for field in reversed(toa_fields):
        match = TOA_CATEGORY_RE.search(field["instr"])
        category = categories_by_number.get(int(match.group(1))) if match else None
        entries = grouped.get(category) or []
        if entries:
            _rebuild_toa_field(paragraphs, field, entries)
            filled.append(category)
        else:
            _remove_toa_field(paragraphs, field)

    report = registry.report()
    report["marked"] = marked
    report["categories"] = [
        {"key": row["key"], "heading": row["heading"], "count": len(grouped.get(row["key"]) or [])}
        for row in config.get("categories") or []
        if row["key"] in filled
    ]
    return _rewrite_parts(source, document), report


def _rewrite_parts(source, document):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "word/document.xml":
                data = etree.tostring(document, xml_declaration=True, encoding="UTF-8", standalone=True)
            elif item.filename == "word/settings.xml":
                data = _ensure_update_fields(data)
            elif item.filename == "word/styles.xml":
                data = _ensure_styles(data)
            target.writestr(item, data)
    return output.getvalue()
