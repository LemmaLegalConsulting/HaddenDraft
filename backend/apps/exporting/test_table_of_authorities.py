import io
import zipfile

from django.test import SimpleTestCase
from docx import Document
from lxml import etree

from apps.exporting.table_of_authorities import apply_table_of_authorities
from apps.templates_app.filing_templates import _configure_styles, _field_paragraph


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _docx(paragraphs, *, with_toa=True):
    """A document with TOA fields for cases and statutes, then ``paragraphs``.

    Each paragraph is a list of runs; a run is text or ``(text, italic)``.
    """
    document = Document()
    _configure_styles(document)
    if with_toa:
        for number, heading in ((1, "Cases"), (2, "Statutes and Ordinances"), (4, "Rules")):
            document.add_paragraph(heading, style="toa heading")
            _field_paragraph(document, f'TOA \\c "{number}"', "pending", style="table of authorities")
    for runs in paragraphs:
        paragraph = document.add_paragraph()
        for run in runs:
            text, italic = run if isinstance(run, tuple) else (run, False)
            paragraph.add_run(text).italic = italic or None
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def _part(data, name):
    return zipfile.ZipFile(io.BytesIO(data)).read(name).decode("utf-8")


def _field_codes(document_xml):
    """Every complex field's instruction, joined across its instruction runs."""
    root = etree.fromstring(document_xml.encode("utf-8"))
    codes, stack = [], []
    for element in root.iter(f"{W}fldChar", f"{W}instrText"):
        if element.tag == f"{W}fldChar":
            kind = element.get(f"{W}fldCharType")
            if kind == "begin":
                stack.append("")
            elif kind == "end":
                codes.append(stack.pop().strip())
        elif stack:
            stack[-1] += element.text or ""
    return codes


class TableOfAuthoritiesExportTests(SimpleTestCase):
    def test_a_document_without_a_toa_field_is_returned_unchanged(self):
        data = _docx([["Dresher v. Burt, 75 Ohio St.3d 280 (1996)."]], with_toa=False)
        result, report = apply_table_of_authorities(data)
        self.assertIs(result, data)
        self.assertIsNone(report)

    def test_citations_are_marked_with_word_ta_fields(self):
        data = _docx(
            [
                # Word splits runs mid-citation all the time.
                ["The standard is settled. Dresher v. Bu", "rt, 75 Ohio St.3d 280, 293 (1996); Civ.R. 56(C)."],
                ["Under R.C. 5321.04(A)(2) the landlord must repair. Dresher, 75 Ohio St.3d 280, 294."],
            ]
        )
        result, report = apply_table_of_authorities(data)
        codes = [code for code in _field_codes(_part(result, "word/document.xml")) if code.startswith("TA ")]
        self.assertEqual(
            codes,
            [
                'TA \\l "Dresher v. Burt, 75 Ohio St.3d 280 (1996)" \\s "Dresher, 75 Ohio St.3d 280" \\c 1',
                'TA \\l "Civ.R. 56" \\s "Civ.R. 56" \\c 4',
                'TA \\l "R.C. 5321.04" \\s "R.C. 5321.04" \\c 2',
                'TA \\s "Dresher, 75 Ohio St.3d 280"',
            ],
        )
        self.assertEqual(report["marked"], 4)
        self.assertEqual(report["pageNumbers"], "unmeasured")

    def test_visible_text_is_unchanged_and_case_names_are_italicized(self):
        data = _docx([["See Dresher v. Burt, 75 Ohio St.3d 280 (1996), for the rule."]])
        result, _report = apply_table_of_authorities(data)
        document = Document(io.BytesIO(result))
        paragraph = document.paragraphs[-1]
        self.assertEqual(paragraph.text, "See Dresher v. Burt, 75 Ohio St.3d 280 (1996), for the rule.")
        italic = "".join(run.text for run in paragraph.runs if run.italic)
        self.assertEqual(italic, "Dresher v. Burt")

    def test_toa_fields_are_filled_and_empty_categories_removed(self):
        data = _docx([["Dresher v. Burt, 75 Ohio St.3d 280 (1996); Temple v. Wean United, Inc., 50 Ohio St.2d 317 (1977)."]])
        result, report = apply_table_of_authorities(data)
        document_xml = _part(result, "word/document.xml")
        toa_codes = [code for code in _field_codes(document_xml) if code.startswith("TOA")]
        # Only the cases table has entries; the statutes and rules tables and
        # their headings are gone rather than printed empty.
        self.assertEqual(toa_codes, ['TOA \\c "1"'])
        self.assertNotIn("Statutes and Ordinances", document_xml)
        self.assertEqual([row["key"] for row in report["categories"]], ["cases"])
        entries = [
            paragraph.text
            for paragraph in Document(io.BytesIO(result)).paragraphs
            if paragraph.style.style_id == "TableofAuthorities"
        ]
        self.assertEqual(
            entries,
            [
                "Dresher v. Burt, 75 Ohio St.3d 280 (1996)\t",
                "Temple v. Wean United, Inc., 50 Ohio St.2d 317 (1977)\t",
            ],
        )
        # Word rebuilds the table, with page numbers, when it opens the file.
        self.assertIn('w:fldCharType="begin" w:dirty="true"', document_xml)

    def test_word_is_asked_to_update_fields_in_schema_order(self):
        result, _report = apply_table_of_authorities(_docx([["R.C. 1923.04."]]))
        settings_xml = _part(result, "word/settings.xml")
        self.assertIn('<w:updateFields w:val="true"/>', settings_xml)
        update = settings_xml.index("updateFields")
        later = [settings_xml.index(f"<w:{tag}") for tag in ("compat", "rsids") if f"<w:{tag}" in settings_xml]
        self.assertTrue(all(update < position for position in later))

    def test_a_document_the_author_marked_keeps_the_authors_marks_and_table(self):
        document = Document()
        _configure_styles(document)
        _field_paragraph(document, 'TOA \\c "2"', "pending", style="table of authorities")
        paragraph = document.add_paragraph("R.C. 1923.04 applies.")
        for kind, text in (("begin", None), (None, ' TA \\l "R.C. 1923.04" \\s "R.C. 1923.04" \\c 2 '), ("end", None)):
            run = etree.SubElement(paragraph._p, f"{W}r")
            if kind:
                etree.SubElement(run, f"{W}fldChar").set(f"{W}fldCharType", kind)
            else:
                etree.SubElement(run, f"{W}instrText").text = text
        output = io.BytesIO()
        document.save(output)
        result, report = apply_table_of_authorities(output.getvalue())
        codes = [code for code in _field_codes(_part(result, "word/document.xml")) if code.startswith("TA ")]
        self.assertEqual(codes, ['TA \\l "R.C. 1923.04" \\s "R.C. 1923.04" \\c 2'])
        self.assertEqual(report["marked"], 0)
        self.assertTrue(report["authorMarked"])
        # The author's table survives even though nothing here listed an entry for it.
        self.assertIn('TOA \\c "2"', " ".join(_field_codes(_part(result, "word/document.xml"))))
