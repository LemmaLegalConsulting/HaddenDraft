"""Document builders for tests.

Format checks read type size, spacing, margins, and page counts out of real
files, so the tests have to hand them real files. These build the smallest DOCX
and PDF that carry those properties -- writing them here rather than committing
binary fixtures keeps what is being asserted visible in the test.
"""

import io
import zipfile


WORD_NAMESPACE = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def build_docx(paragraphs, *, default_size_pt=12, margins_in=1.0, line=480, font="Times New Roman"):
    """A DOCX carrying the run properties, spacing, and margins the checks read.

    ``paragraphs`` items are either a string or ``(text, {"style":…, "size_pt":…})``.
    ``line`` is Word's own unit: 240ths of a line, so 480 is double-spaced.
    """
    body = []
    for item in paragraphs:
        text, options = item if isinstance(item, tuple) else (item, {})
        style = options.get("style", "")
        size = options.get("size_pt", default_size_pt)
        family = options.get("font", font)
        properties = "".join(
            [
                f'<w:pStyle w:val="{style}"/>' if style else "",
                f'<w:spacing w:line="{line}" w:lineRule="auto"/>',
            ]
        )
        body.append(
            f"<w:p><w:pPr>{properties}</w:pPr>"
            f'<w:r><w:rPr><w:rFonts w:ascii="{family}"/><w:sz w:val="{int(size * 2)}"/></w:rPr>'
            f"<w:t xml:space=\"preserve\">{text}</w:t></w:r></w:p>"
        )
    twips = int(margins_in * 1440)
    section = (
        f'<w:sectPr><w:pgMar w:top="{twips}" w:bottom="{twips}" '
        f'w:left="{twips}" w:right="{twips}"/></w:sectPr>'
    )
    document = f"<w:document {WORD_NAMESPACE}><w:body>{''.join(body)}{section}</w:body></w:document>"
    styles = (
        f"<w:styles {WORD_NAMESPACE}><w:docDefaults><w:rPrDefault><w:rPr>"
        f'<w:sz w:val="{int(default_size_pt * 2)}"/></w:rPr></w:rPrDefault></w:docDefaults></w:styles>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document)
        archive.writestr("word/styles.xml", styles)
    return buffer.getvalue()


def build_pdf(page_texts, *, font_size=12):
    """A small multi-page PDF: enough for pypdf to read text, pages, and type size."""
    font_id = 3
    objects = {font_id: "<</Type/Font/Subtype/Type1/BaseFont/Times-Roman>>"}
    page_ids = []
    next_id = 4
    for text in page_texts:
        page_id, content_id = next_id, next_id + 1
        next_id += 2
        page_ids.append(page_id)
        lines = []
        for index, line in enumerate(str(text).splitlines() or [""]):
            escaped = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
            lines.append(f"{'T*' if index else '72 720 Td'} ({escaped}) Tj")
        stream = f"BT /F1 {font_size} Tf {font_size * 2} TL\n" + "\n".join(lines) + "\nET"
        objects[page_id] = (
            "<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]"
            f"/Resources<</Font<</F1 {font_id} 0 R>>>>/Contents {content_id} 0 R>>"
        )
        objects[content_id] = f"<</Length {len(stream)}>>stream\n{stream}\nendstream"
    objects[1] = "<</Type/Catalog/Pages 2 0 R>>"
    objects[2] = f"<</Type/Pages/Kids[{' '.join(f'{page} 0 R' for page in page_ids)}]/Count {len(page_ids)}>>"

    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for object_id in sorted(objects):
        offsets[object_id] = len(out)
        out += f"{object_id} 0 obj\n{objects[object_id]}\nendobj\n".encode("latin-1")
    xref_at = len(out)
    count = max(objects) + 1
    out += f"xref\n0 {count}\n0000000000 65535 f \n".encode()
    for object_id in range(1, count):
        out += f"{offsets.get(object_id, 0):010d} 00000 n \n".encode()
    out += f"trailer\n<</Size {count}/Root 1 0 R>>\nstartxref\n{xref_at}\n%%EOF\n".encode()
    return bytes(out)
