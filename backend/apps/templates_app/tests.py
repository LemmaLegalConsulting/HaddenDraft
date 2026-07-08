import tempfile
import zipfile
from io import BytesIO
from pathlib import Path

import yaml
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from docx import Document

from apps.core.content_library import organization_content_library_dir
from apps.drafting.models import DraftDocument, DraftingSession
from apps.exporting.services import _remove_editorial_caption_label, _render_docx_template, export_docx
from apps.matters.models import Matter
from apps.templates_app.content_library import sync_prepared_templates, sync_template_overrides
from apps.templates_app.ingestion import convert_placeholder_text, discover_blocks, ingest_docx
from apps.templates_app.jinja_filters import (
    as_noun,
    comma_and_list,
    did_verb,
    does_verb,
    pronoun_objective,
    pronoun_possessive,
    pronoun_subjective,
)
from apps.templates_app.models import DocumentTemplate
from apps.templates_app.template_variables import template_field_values


def make_source_docx(path: Path):
    document = Document()
    section = document.sections[0]
    section.header.paragraphs[0].text = "Legal Aid letterhead"
    document.add_heading("FACTS", level=1)
    fact = document.add_paragraph(style="List Number")
    fact.add_run("[Insert case specific facts]").bold = True
    document.add_paragraph("Further affiant sayeth naught.")
    document.add_heading("CERTIFICATE OF SERVICE", level=1)
    document.add_paragraph("I served this document on [DATE].")
    table = document.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "Case No. [CASE NUMBER]"
    document.save(path)


class TemplatePhrasingFilterTests(TestCase):
    def test_list_and_number_aware_language_matches_assemblyline_conventions(self):
        self.assertEqual(comma_and_list(["Ada", "Grace", "Katherine"]), "Ada, Grace, and Katherine")
        self.assertEqual(comma_and_list(["Ada", "Grace"], and_string="or"), "Ada or Grace")
        self.assertEqual(does_verb(["Ada"], "live"), "lives")
        self.assertEqual(does_verb(["Ada", "Grace"], "live"), "live")
        self.assertEqual(did_verb(["Ada"], "be"), "was")
        self.assertEqual(did_verb(["Ada", "Grace"], "be"), "were")
        self.assertEqual(as_noun(["Ada"], "occupant"), "occupant")
        self.assertEqual(as_noun(["Ada", "Grace"], "occupant"), "occupants")

    def test_explicit_and_custom_pronoun_sets_are_not_inferred_from_names(self):
        she = {"name": "Ada", "pronouns": "she/her/hers"}
        custom = {"name": "River", "pronouns": "ze/zir/zirs"}
        unknown = {"name": "Morgan", "pronouns": ""}

        self.assertEqual(pronoun_subjective(she), "she")
        self.assertEqual(pronoun_objective(custom), "zir")
        self.assertEqual(pronoun_possessive(custom, "home"), "zir home")
        self.assertEqual(pronoun_subjective(unknown), "Morgan")
        self.assertEqual(pronoun_possessive(unknown, "home"), "Morgan's home")

    def test_docx_renderer_registers_custom_filters(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "phrasing.docx"
            output = Path(directory) / "rendered.docx"
            document = Document()
            document.add_paragraph(
                '{{ client | pronoun_subjective(capitalize=True) }} lives with '
                '{{ household | comma_and_list }} in '
                '{{ client | pronoun_possessive("home") }}.'
            )
            document.save(source)

            _render_docx_template(
                source,
                {
                    "client": {"name": "Ada", "pronouns": "she/her/hers"},
                    "household": ["Ben", "Cam"],
                },
                output,
            )

            self.assertEqual(
                Document(output).paragraphs[0].text,
                "She lives with Ben and Cam in her home.",
            )


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
        self.assertIn("Further affiant sayeth naught.", xml)

    def test_ingestion_preserves_editorial_brackets_and_names_generic_inputs_from_context(self):
        converted, fields = convert_placeholder_text(
            "Equity [a]bhors forfeiture under note [216]. Hearing date: [INSERT]",
            "body_1",
        )

        self.assertIn("[a]bhors", converted)
        self.assertIn("[216]", converted)
        self.assertIn("{{ fields.hearing_date }}", converted)
        self.assertEqual(fields, ["fields.hearing_date"])

    def test_blank_placeholder_uses_surrounding_party_context(self):
        converted, fields = convert_placeholder_text(
            "Now comes Defendant [ ] by and through counsel.",
            "caption_1",
        )

        self.assertIn("{{ defendant }}", converted)
        self.assertEqual(fields, [])

    def test_styled_email_placeholder_is_not_discovered_as_a_section(self):
        document = Document()
        document.add_heading("SIGNATURE", level=1)
        document.add_paragraph("[Email]", style="Heading 2")

        blocks = discover_blocks(document)

        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].label, "Signature")

    def test_export_cleanup_removes_editorial_case_caption_label(self):
        path = self.root / "caption.docx"
        document = Document()
        document.add_paragraph("Case Caption - Defendant's Motion to Dismiss")
        document.add_paragraph("Now comes Defendant Jane Tenant.")
        document.save(path)
        block = type(
            "Block",
            (),
            {"label": "Case Caption - Defendant's Motion to Dismiss"},
        )()

        _remove_editorial_caption_label(
            path,
            block,
            {
                "court": "Housing Court",
                "plaintiff": "Example Landlord",
                "defendant": "Jane Tenant",
                "case_number": "CASE-1",
                "document": {"title": "Motion to Dismiss"},
            },
        )

        rendered = Document(path)
        text = "\n".join(paragraph.text for paragraph in rendered.paragraphs)
        table_text = "\n".join(cell.text for cell in rendered.tables[0].rows[0].cells)
        self.assertNotIn("Case Caption -", text)
        self.assertIn("Now comes Defendant Jane Tenant.", text)
        self.assertIn("Example Landlord", table_text)
        self.assertIn("CASE-1", table_text)

    def test_first_block_keeps_leading_caption_tables(self):
        source = self.source.parent / "Table Caption Motion.docx"
        document = Document()
        table = document.add_table(rows=1, cols=2)
        table.cell(0, 0).text = "Plaintiff"
        table.cell(0, 1).text = "Case No. [CASE NUMBER]"
        document.add_heading("INTRODUCTION", level=1)
        document.add_paragraph("Body text.")
        document.save(source)

        manifest_path = ingest_docx(
            source,
            self.content / "document-templates",
            self.content / "docx-snippets",
            force=True,
        )
        manifest = yaml.safe_load(manifest_path.read_text())
        first_block_path = self.content / manifest["blocks"][0]["docx"]
        first_block = Document(first_block_path)

        self.assertEqual(len(first_block.tables), 1)
        self.assertIn("{{ case_number }}", first_block.tables[0].cell(0, 1).text)

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

    def test_missing_content_provider_does_not_deactivate_indexed_templates(self):
        template = DocumentTemplate.objects.create(
            slug="provider-temporarily-missing",
            title="Provider temporarily missing",
            kind="motion",
            source_kind="content_library",
            content_path="document-templates/provider-temporarily-missing/manifest.yaml",
        )
        missing_root = self.root / "not-mounted"

        with self.settings(CONTENT_LIBRARY_DIR=missing_root):
            results = sync_prepared_templates()

        template.refresh_from_db()
        self.assertEqual(results, [])
        self.assertTrue(template.is_active)

    def test_private_template_override_updates_metadata_and_blocks(self):
        template = DocumentTemplate.objects.create(
            slug="private-override-test",
            title="Original title",
            kind="motion",
            jurisdiction="Ohio",
        )
        block = template.blocks.create(
            key="facts",
            label="Facts",
            block_type="facts",
            body="Original body",
        )
        removable = template.blocks.create(
            key="editorial-note",
            label="Editorial note",
            block_type="optional_clause",
            body="Remove me",
        )
        private = self.root / "private"
        override_dir = private / "template-overrides"
        override_dir.mkdir(parents=True)
        (override_dir / "private-override-test.yaml").write_text(
            yaml.safe_dump(
                {
                    "schema_version": 1,
                    "slug": template.slug,
                    "template": {
                        "jurisdiction": "Housing Court",
                        "metadata": {
                            "fields": ["fields.client_pronouns"],
                            "fieldSchema": {"client_pronouns": {"type": "pronouns"}},
                        },
                    },
                    "blocks": [
                        {"key": block.key, "body": "{{ client | pronoun_subjective }} lives here."},
                        {"key": removable.key, "delete": True},
                        {
                            "key": "argument",
                            "create": True,
                            "label": "Argument",
                            "block_type": "argument",
                            "order": 30,
                            "body": "Argument body",
                            "ai_fill_mode": "constrained_generation",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        with self.settings(
            CONTENT_LIBRARY_DIR=self.content,
            ORGANIZATION_CONTENT_LIBRARY_DIR=private,
        ):
            results = sync_template_overrides()

        template.refresh_from_db()
        block.refresh_from_db()
        self.assertEqual(results[0]["status"], "updated")
        self.assertEqual(template.jurisdiction, "Housing Court")
        self.assertEqual(template.metadata["fieldSchema"]["client_pronouns"]["type"], "pronouns")
        self.assertIn("pronoun_subjective", block.body)
        self.assertFalse(template.blocks.filter(pk=removable.pk).exists())
        self.assertTrue(template.blocks.filter(key="argument", block_type="argument").exists())

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


class RepositorySnippetRenderingTests(TestCase):
    def test_every_maintained_docx_snippet_renders(self):
        snippet_root = organization_content_library_dir() / "docx-snippets"
        paths = sorted(snippet_root.glob("*/blocks/*.docx"))
        if not paths:
            self.skipTest("No private organization snippets are mounted")
        block_keys = {path.stem for path in paths}
        context = {
            "fields": template_field_values(),
            "blocks": {key: {"body": "", "paragraphs": [], "items": []} for key in block_keys},
            "document": {},
            "section": {},
            "matter": {},
            "author": {},
            "selected_facts": [],
            "selected_curated_facts": [],
            "selected_sources": [],
            "instructions": "",
            "court": "[Court]",
            "plaintiff": "Plaintiff",
            "defendant": "[Defendant]",
            "case_number": "[Case Number]",
            "advocate_name": "[Advocate]",
            "advocate_signoff": "Respectfully submitted,",
            "advocate_salutation": "",
            "advocate_organization": "",
            "advocate_email": "[Email]",
            "advocate_phone": "[Phone]",
            "advocate_address": "[Address]",
            "advocate_contact": "[Advocate Contact]",
            "advocate_signature_image": "",
        }

        with tempfile.TemporaryDirectory() as directory:
            for index, path in enumerate(paths):
                output = Path(directory) / f"{index}.docx"
                _render_docx_template(path, context, output)
                Document(output)
