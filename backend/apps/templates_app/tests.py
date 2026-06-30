import tempfile
import zipfile
from io import BytesIO
from pathlib import Path

import yaml
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from docx import Document

from apps.drafting.models import DraftDocument, DraftingSession
from apps.exporting.services import export_docx
from apps.matters.models import Matter
from apps.templates_app.content_library import sync_prepared_templates
from apps.templates_app.ingestion import ingest_docx
from apps.templates_app.models import DocumentTemplate


def make_source_docx(path: Path):
    document = Document()
    section = document.sections[0]
    section.header.paragraphs[0].text = "Legal Aid letterhead"
    document.add_heading("FACTS", level=1)
    fact = document.add_paragraph(style="List Number")
    fact.add_run("[Insert case specific facts]").bold = True
    document.add_heading("CERTIFICATE OF SERVICE", level=1)
    document.add_paragraph("I served this document on [DATE].")
    table = document.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "Case No. [CASE NUMBER]"
    document.save(path)


class TemplateIngestionTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.content = self.root / "content"
        self.source = self.content / "original_templates" / "Test Motion.docx"
        self.source.parent.mkdir(parents=True)
        make_source_docx(self.source)

    def ingest(self):
        return ingest_docx(
            self.source,
            self.content / "document-templates",
            self.content / "docx-snippets",
            force=True,
        )

    def test_ingestion_preserves_word_structure_and_adds_list_loop(self):
        manifest_path = self.ingest()
        manifest = yaml.safe_load(manifest_path.read_text())
        template_path = manifest_path.parent / "template.docx"

        self.assertEqual(manifest["render"]["strategy"], "full_document")
        facts = next(block for block in manifest["blocks"] if block["type"] == "facts")
        self.assertEqual(facts["input"]["type"], "array")
        self.assertEqual(facts["lexical"]["node"], "list")
        self.assertTrue((self.content / facts["docx"]).is_file())

        converted = Document(template_path)
        self.assertEqual(converted.sections[0].header.paragraphs[0].text, "Legal Aid letterhead")
        self.assertEqual(len(converted.tables), 1)
        self.assertIn("{{ case_number }}", converted.tables[0].cell(0, 0).text)
        with zipfile.ZipFile(template_path) as archive:
            xml = archive.read("word/document.xml").decode("utf-8")
        self.assertIn('{%p for item in blocks["facts"]["items"] %}', xml)
        self.assertIn("{{ item }}", xml)
        self.assertIn("{%p endfor %}", xml)

    def test_sync_indexes_manifests_and_preserves_admin_slug_conflicts(self):
        manifest_path = self.ingest()
        with self.settings(CONTENT_LIBRARY_DIR=self.content):
            results = sync_prepared_templates()
            template = DocumentTemplate.objects.get(slug="test-motion")
            self.assertEqual(template.source_kind, "content_library")
            self.assertEqual(template.content_path, "document-templates/test-motion/manifest.yaml")
            self.assertTrue(template.blocks.filter(block_type="facts", input_schema__type="array").exists())
            self.assertEqual(results[0]["status"], "created")

            template.source_kind = "database"
            template.title = "Admin title"
            template.save()
            results = sync_prepared_templates()
            template.refresh_from_db()
            self.assertEqual(template.title, "Admin title")
            self.assertEqual(results[0]["status"], "conflict")

    def test_unchanged_sync_does_not_write_to_database(self):
        self.ingest()
        with self.settings(CONTENT_LIBRARY_DIR=self.content):
            sync_prepared_templates()

            with CaptureQueriesContext(connection) as queries:
                results = sync_prepared_templates()

        self.assertEqual(results[0]["status"], "unchanged")
        write_statements = [
            query["sql"]
            for query in queries.captured_queries
            if query["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        ]
        self.assertEqual(write_statements, [])

    def test_full_template_export_uses_edited_lexical_block_values(self):
        self.ingest()
        with self.settings(CONTENT_LIBRARY_DIR=self.content):
            sync_prepared_templates()
            template = DocumentTemplate.objects.prefetch_related("blocks").get(slug="test-motion")
            matter = Matter.objects.create(
                external_id="2026-CVG-1",
                client_name="Jane Tenant",
                matter_type="Eviction",
                jurisdiction="Housing Court",
            )
            session = DraftingSession.objects.create(
                mode="draft_from_template",
                matter=matter,
                template=template,
                template_data={"filing_date": "June 28, 2026"},
            )
            draft = DraftDocument.objects.create(
                session=session,
                title="Test Motion",
                sections=[
                    {"key": "facts", "label": "Facts", "body": "1. First edited fact.\n2. Second edited fact."},
                    {"key": "certificate-of-service", "label": "Certificate of Service", "body": "Edited certificate text.\nAdded overflow paragraph."},
                ],
                plain_text="",
            )

            response = export_docx(draft)

        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            xml = archive.read("word/document.xml").decode("utf-8")
        self.assertIn("First edited fact.", xml)
        self.assertIn("Second edited fact.", xml)
        self.assertIn("Edited certificate text.", xml)
        self.assertIn("Added overflow paragraph.", xml)
        self.assertNotIn("{%p", xml)
