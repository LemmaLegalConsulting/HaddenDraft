import zipfile
import tempfile
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree

from django.core.files import File
from django.test import TestCase
from django.test.utils import override_settings
from docx import Document

from apps.ai.services import ConstrainedDraftingService
from apps.drafting.models import DraftDocument, DraftingSession
from apps.exporting.services import export_docx
from apps.matters.models import Matter
from apps.templates_app.models import DocumentTemplate, TemplateBlock
from apps.templates_app.serializers import template_to_dict
from apps.templates_app.template_variables import (
    extract_template_variables_from_text,
    block_variable_metadata,
)


class DraftRenderingTests(TestCase):
    def test_template_variable_parser_resolves_dotted_paths_and_loop_aliases(self):
        variables = extract_template_variables_from_text(
            "{% for fact in selected_facts %}{{ fact.text }} {{ client.name.first }}{% endfor %}"
        )

        self.assertIn("selected_facts[i].text", variables)
        self.assertIn("client.name.first", variables)

    def test_repository_docx_template_variables_are_classified(self):
        template, _created = DocumentTemplate.objects.update_or_create(
            slug="answer-counterclaims-cleveland",
            defaults={
                "title": "Answer and Counterclaims",
                "kind": "answer_counterclaims",
            },
        )
        block, _created = TemplateBlock.objects.update_or_create(
            template=template,
            key="caption",
            defaults={
                "label": "Court caption",
                "block_type": "caption",
                "order": 10,
                "body": "{{ court }}",
            },
        )

        metadata = block_variable_metadata(template, block)

        self.assertEqual(metadata["source"], "repository")
        self.assertIn("defendant", metadata["variables"]["providedBySystem"])
        self.assertIn("document.title", metadata["variables"]["providedBySystem"])
        self.assertEqual(metadata["variables"]["externalData"], [])

    def test_template_serializer_includes_word_template_variable_metadata(self):
        template, _created = DocumentTemplate.objects.update_or_create(
            slug="answer-counterclaims-cleveland",
            defaults={
                "title": "Answer and Counterclaims",
                "kind": "answer_counterclaims",
            },
        )
        template.blocks.all().delete()
        TemplateBlock.objects.create(
            template=template,
            key="custom",
            label="Custom",
            block_type="optional_clause",
            order=10,
            body="{{ client_preferred_name }} {{ matter.client_name }}",
        )

        data = template_to_dict(template, include_blocks=True)

        self.assertIn("wordTemplateVariables", data)
        self.assertIn("client_preferred_name", data["wordTemplateVariables"]["variables"]["externalData"])
        self.assertIn("matter.client_name", data["wordTemplateVariables"]["variables"]["providedBySystem"])

    def test_generated_text_normalizes_html_breaks(self):
        service = ConstrainedDraftingService()

        self.assertEqual(service.normalize_generated_text("Line one<br/>Line two<br>Line three"), "Line one\nLine two\nLine three")

    def test_export_docx_renders_sections_and_numbering_part(self):
        draft = SimpleNamespace(
            id=42,
            title="Test Draft",
            sections=[
                {
                    "label": "Facts",
                    "body": "First fact.\nSecond fact.",
                    "format": {"style": "numbered", "headingNumbering": "roman"},
                }
            ],
        )

        response = export_docx(draft)

        self.assertEqual(response["Content-Disposition"], 'attachment; filename="draft-42.docx"')
        self.assertEqual(response["Content-Type"], "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            names = set(archive.namelist())
            self.assertIn("word/document.xml", names)
            self.assertIn("word/numbering.xml", names)
            self.assertIn("word/styles.xml", names)
            document_xml = archive.read("word/document.xml").decode("utf-8")
        self.assertIn("I. FACTS", document_xml)
        self.assertIn("First fact.", document_xml)
        self.assertIn("<w:numPr>", document_xml)

    def test_export_docx_can_restart_numbering(self):
        draft = SimpleNamespace(
            id=43,
            title="Restart Draft",
            sections=[
                {"label": "Facts", "body": "One", "format": {"style": "numbered"}},
                {"label": "Argument", "body": "Fresh one", "format": {"style": "numbered", "restartNumbering": True}},
            ],
        )

        response = export_docx(draft)

        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")
            numbering_xml = archive.read("word/numbering.xml").decode("utf-8")
        self.assertIn('<w:numId w:val="1"/>', document_xml)
        self.assertIn('<w:numId w:val="2"/>', document_xml)
        self.assertIn('<w:num w:numId="2">', numbering_xml)

    def test_export_docx_removes_xml_forbidden_characters(self):
        draft = SimpleNamespace(
            id=44,
            title="Bad\x0bTitle",
            sections=[
                {
                    "label": "Facts",
                    "body": "Text with invalid XML control \x0b and safe <xml> characters.",
                    "format": {},
                }
            ],
        )

        response = export_docx(draft)

        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            document_xml = archive.read("word/document.xml")
            core_xml = archive.read("docProps/core.xml")
        ElementTree.fromstring(document_xml)
        ElementTree.fromstring(core_xml)
        self.assertNotIn(b"\x0b", document_xml)
        self.assertNotIn(b"\x0b", core_xml)

    def test_export_docx_renders_and_composes_uploaded_block_templates(self):
        temp_dir = tempfile.TemporaryDirectory()
        media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(media_dir.cleanup)
        source_dir = Path(temp_dir.name)

        style_source = source_dir / "styles.docx"
        style_doc = Document()
        style_doc.add_paragraph("Style source body should be cleared.")
        style_doc.save(style_source)

        caption_source = source_dir / "caption.docx"
        caption_doc = Document()
        caption_doc.add_paragraph("Caption for {{ defendant }}")
        caption_doc.add_paragraph("Reviewed body: {{ section.body }}")
        caption_doc.save(caption_source)

        with override_settings(MEDIA_ROOT=media_dir.name):
            matter = Matter.objects.create(
                external_id="24-CV-100",
                client_name="Jane Tenant",
                matter_type="Eviction",
                jurisdiction="Housing Court",
            )
            template = DocumentTemplate.objects.create(
                title="Answer",
                slug="answer-docx-template-test",
                kind="answer_counterclaims",
                style_template=File(style_source.open("rb"), name="styles.docx"),
            )
            TemplateBlock.objects.create(
                template=template,
                key="caption",
                label="Caption",
                block_type="caption",
                order=10,
                body="{{ court }}",
                docx_template=File(caption_source.open("rb"), name="caption.docx"),
            )
            session = DraftingSession.objects.create(
                mode="draft_from_template",
                matter=matter,
                template=template,
                author_profile={"displayName": "Ada Advocate"},
            )
            draft = DraftDocument.objects.create(
                session=session,
                title="Answer",
                sections=[{"key": "caption", "label": "Caption", "body": "Edited caption text."}],
                plain_text="CAPTION\nEdited caption text.",
            )

            response = export_docx(draft)

        self.assertEqual(response["Content-Type"], "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")
        ElementTree.fromstring(document_xml)
        self.assertIn("Jane Tenant", document_xml)
        self.assertIn("Edited caption text.", document_xml)
        self.assertNotIn("Style source body should be cleared.", document_xml)

    def test_export_docx_uses_repository_default_block_templates(self):
        matter = Matter.objects.create(
            external_id="24-CV-101",
            client_name="John Tenant",
            matter_type="Eviction",
            jurisdiction="Housing Court",
        )
        template, _created = DocumentTemplate.objects.update_or_create(
            slug="answer-counterclaims-cleveland",
            defaults={
                "title": "Answer and Counterclaims",
                "kind": "answer_counterclaims",
            },
        )
        template.blocks.all().delete()
        TemplateBlock.objects.create(
            template=template,
            key="caption",
            label="Court caption",
            block_type="caption",
            order=10,
            body="{{ court }}",
        )
        TemplateBlock.objects.create(
            template=template,
            key="relief",
            label="Prayer for relief",
            block_type="relief",
            order=90,
            body="{{ section.body }}",
        )
        session = DraftingSession.objects.create(
            mode="draft_from_template",
            matter=matter,
            template=template,
            author_profile={"displayName": "Ada Advocate"},
        )
        draft = DraftDocument.objects.create(
            session=session,
            title="Answer and Counterclaims",
            sections=[
                {"key": "caption", "label": "Court caption", "body": "Caption text."},
                {"key": "relief", "label": "Prayer for relief", "body": "dismiss the complaint"},
            ],
            plain_text="CAPTION\nCaption text.\n\nRELIEF\ndismiss the complaint",
        )

        response = export_docx(draft)

        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")
        ElementTree.fromstring(document_xml)
        self.assertIn("John Tenant", document_xml)
        self.assertIn("Prayer for Relief", document_xml)
        self.assertIn("dismiss the complaint", document_xml)
