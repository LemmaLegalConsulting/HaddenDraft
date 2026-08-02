import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import yaml
from django.test import TestCase

from apps.templates_app.spreadsheets import (
    SHEET_NS,
    convert_caps_placeholders,
    ingest_xlsx,
    render_workbook,
)


SHEET_XML = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
 <sheetData>
  <row r="1"><c r="A1" t="s"><v>0</v></c></row>
  <row r="3"><c r="E3"><f>C3-D3</f><v>0</v></c></row>
 </sheetData>
</worksheet>"""

SHARED_STRINGS = """<?xml version="1.0" encoding="UTF-8"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="3" uniqueCount="3">
 <si><t>RENT LEDGER - CLIENT NAME | ADDRESS</t></si>
 <si><t>Date</t></si>
 <si><t>TOTAL REQUESTED</t></si>
</sst>"""

WORKBOOK_XML = """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
 <sheets><sheet name="Ledger" sheetId="1" r:id="rId1"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/></sheets>
</workbook>"""


def make_workbook(path: Path):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", WORKBOOK_XML)
        archive.writestr("xl/worksheets/sheet1.xml", SHEET_XML)
        archive.writestr("xl/sharedStrings.xml", SHARED_STRINGS)


def shared_strings(path: Path):
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return [
        "".join(node.text or "" for node in item.iter(f"{{{SHEET_NS}}}t"))
        for item in root.findall(f"{{{SHEET_NS}}}si")
    ]


class SpreadsheetTemplateTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "Rent Ledger Template.xlsx"
        make_workbook(self.source)

    def test_shouted_fill_ins_become_variables_but_headings_do_not(self):
        converted, fields = convert_caps_placeholders(
            "RENT LEDGER - CLIENT NAME | ADDRESS", "cell_1"
        )

        self.assertIn("RENT LEDGER", converted)
        self.assertIn("{{ defendant }}", converted)
        self.assertIn("{{ fields.premises_address }}", converted)
        self.assertIn("fields.premises_address", fields)

    def test_column_headings_are_left_alone(self):
        converted, _fields = convert_caps_placeholders("TOTAL REQUESTED", "cell_1")

        self.assertEqual(converted, "TOTAL REQUESTED")

    def test_ingest_produces_a_workbook_manifest(self):
        manifest_path = ingest_xlsx(self.source, self.root / "prepared")
        manifest = yaml.safe_load(manifest_path.read_text())

        self.assertEqual(manifest["kind"], "worksheet")
        self.assertEqual(manifest["render"]["strategy"], "workbook")
        self.assertEqual(manifest["blocks"], [])
        self.assertIn("fields.premises_address", manifest["fields"])
        self.assertTrue((manifest_path.parent / "template.xlsx").is_file())

    def test_prepared_workbook_keeps_formulas_and_headings(self):
        manifest_path = ingest_xlsx(self.source, self.root / "prepared")
        prepared = manifest_path.parent / "template.xlsx"

        with zipfile.ZipFile(prepared) as archive:
            sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        self.assertIn("<f>C3-D3</f>", sheet)
        self.assertIn("Date", shared_strings(prepared))

    def test_rendering_fills_the_title_row(self):
        manifest_path = ingest_xlsx(self.source, self.root / "prepared")
        prepared = manifest_path.parent / "template.xlsx"
        output = self.root / "rendered.xlsx"

        render_workbook(
            prepared,
            {"defendant": "Jane Tenant", "fields": {"premises_address": "123 Main St"}},
            output,
        )

        self.assertIn("RENT LEDGER - Jane Tenant | 123 Main St", shared_strings(output))
        with zipfile.ZipFile(output) as archive:
            self.assertIn("<f>C3-D3</f>", archive.read("xl/worksheets/sheet1.xml").decode("utf-8"))

    def test_reingest_is_skipped_when_the_source_is_unchanged(self):
        first = ingest_xlsx(self.source, self.root / "prepared")
        stamp = yaml.safe_load(first.read_text())["source"]["converted_at"]

        second = ingest_xlsx(self.source, self.root / "prepared")

        self.assertEqual(yaml.safe_load(second.read_text())["source"]["converted_at"], stamp)
