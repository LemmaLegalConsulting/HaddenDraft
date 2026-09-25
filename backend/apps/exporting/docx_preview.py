"""A low-fidelity reading view of a rendered DOCX: paragraphs, tables, and
inline marks for prompts and supplied values. Not a layout engine -- page
breaks, fonts, and spacing are left to Word."""
import io
import re

from docx import Document

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
TOKEN = re.compile(r"(FIL[LV][0-9A-F]{32}END)")
MAX_BLOCKS = 3000


def _flag(properties, name):
    element = properties.find(W + name) if properties is not None else None
    return element is not None and element.get(W + "val") not in {"0", "false", "none"}


def _paragraph(element, marked):
    properties = element.find(W + "pPr")
    style = properties.find(W + "pStyle") if properties is not None else None
    justify = properties.find(W + "jc") if properties is not None else None
    segments = []
    for run in element.iter(W + "r"):
        run_properties = run.find(W + "rPr")
        text = "".join(child.text or "" if child.tag == W + "t" else "\t" if child.tag == W + "tab" else "\n" if child.tag in {W + "br", W + "cr"} else ""
                       for child in run)
        style_flags = {name: True for name in ("bold", "italic", "underline")
                       if _flag(run_properties, {"bold": "b", "italic": "i", "underline": "u"}[name])}
        for piece in TOKEN.split(text):
            if not piece:
                continue
            mark = marked.get(piece)
            if mark and mark["kind"] == "prompt":
                segments.append({"prompt": mark["label"], "key": mark.get("key")})
            elif mark:
                segments.append({"filled": mark["text"], "key": mark["key"], "label": mark["label"], **style_flags})
            elif segments and set(segments[-1]) == {"text", *style_flags}:  # same formatting: one segment
                segments[-1]["text"] += piece
            else:
                segments.append({"text": piece, **style_flags})
    block = {"kind": "p", "segments": segments}
    if style is not None and re.match(r"(?i)heading\s*\d|title", style.get(W + "val", "")):
        block["heading"] = True
    if justify is not None and justify.get(W + "val") in {"center", "right", "both"}:
        block["align"] = {"both": "justify"}.get(justify.get(W + "val"), justify.get(W + "val"))
    return block


def _blocks(parent, marked):
    blocks = []
    for child in parent:
        if child.tag == W + "p":
            blocks.append(_paragraph(child, marked))
        elif child.tag == W + "tbl":
            rows = [[_blocks(cell, marked) for cell in row.findall(W + "tc")] for row in child.findall(W + "tr")]
            blocks.append({"kind": "table", "rows": rows})
        elif child.tag in {W + "sdt", W + "sdtContent", W + "customXml"}:
            blocks.extend(_blocks(child, marked))
    # Keep one empty paragraph where a run of them separated passages.
    collapsed = []
    for block in blocks:
        empty = block["kind"] == "p" and not any((s.get("text") or "").strip() or "text" not in s for s in block["segments"])
        if empty and (not collapsed or collapsed[-1].get("empty")):
            continue
        collapsed.append({**block, "empty": True} if empty else block)
    return collapsed


def docx_preview(content, marked):
    document = Document(io.BytesIO(content))
    section = document.sections[0] if document.sections else None
    header = _blocks(section.header._element, marked) if section is not None and not section.header.is_linked_to_previous else []
    footer = _blocks(section.footer._element, marked) if section is not None and not section.footer.is_linked_to_previous else []
    body = _blocks(document.element.body, marked)
    truncated = len(body) > MAX_BLOCKS
    return {"header": header, "body": body[:MAX_BLOCKS], "footer": footer, "truncated": truncated}
