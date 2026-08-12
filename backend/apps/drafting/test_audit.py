import json
import zipfile
from io import BytesIO
from xml.etree import ElementTree as ET

from django.test import TestCase

from apps.drafting.audit import draft_ai_audit
from apps.drafting.components import record_sections
from apps.drafting.models import DraftDocument, DraftingSession, SourceBinding
from apps.exporting.services import render_docx_bytes
from apps.matters.models import Matter
from apps.matters.legalserver_notes import ai_audit_case_note


CUSTOM_NS = "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"


class DraftAIAuditTests(TestCase):
    def setUp(self):
        matter = Matter.objects.create(
            external_id="LS-AUDIT",
            client_name="Jane Tenant",
            matter_type="Eviction",
            jurisdiction="Housing Court",
        )
        session = DraftingSession.objects.create(mode="draft_from_template", matter=matter)
        self.draft = DraftDocument.objects.create(
            session=session,
            title="Answer",
            sections=[],
            plain_text="",
        )
        record_sections(
            self.draft,
            [{"key": "defense", "label": "Defense", "body": "First AI paragraph.\n\nSecond AI paragraph."}],
            origin="ai",
            instruction="Explain the notice defect.",
        )
        version = self.draft.components.get(stable_key="defense").current_version
        SourceBinding.objects.create(
            component_version=version,
            source_key="orc-5321",
            source_kind="statute",
            role="legal_authority",
            support_type="direct",
            label="Ohio Revised Code",
            citation="R.C. 5321.04",
            locator={"section": "5321.04"},
            excerpt="A landlord shall maintain fit premises.",
        )

    def test_audit_keeps_ai_output_after_a_human_rewrites_the_component(self):
        record_sections(
            self.draft,
            [{"key": "defense", "label": "Defense", "body": "Attorney-approved replacement."}],
            origin="human",
        )

        audit = draft_ai_audit(self.draft)

        self.assertEqual(len(audit["aiInteractions"]), 1)
        interaction = audit["aiInteractions"][0]
        self.assertFalse(interaction["isCurrentVersion"])
        self.assertEqual(
            [paragraph["text"] for paragraph in interaction["paragraphs"]],
            ["First AI paragraph.", "Second AI paragraph."],
        )
        self.assertEqual(interaction["instruction"], "Explain the notice defect.")
        self.assertEqual(interaction["sources"][0]["sourceKey"], "orc-5321")
        note = ai_audit_case_note(audit)
        self.assertIn("AI version 1 (superseded)", note)
        self.assertIn("R.C. 5321.04", note)
        self.assertIn("has not been reviewed by an attorney", note)
        self.assertTrue(note.endswith("not a substitute for checking current law."))

    def test_docx_custom_properties_carry_the_same_json_audit(self):
        payload = render_docx_bytes(self.draft)

        with zipfile.ZipFile(BytesIO(payload)) as archive:
            custom = ET.fromstring(archive.read("docProps/custom.xml"))
            properties = {
                child.get("name"): next(iter(child)).text
                for child in custom.findall(f"{{{CUSTOM_NS}}}property")
            }
            content_types = archive.read("[Content_Types].xml").decode("utf-8")
            relationships = archive.read("_rels/.rels").decode("utf-8")

        embedded = json.loads(properties["Legal Drafting Tool AI Audit JSON"])
        self.assertEqual(embedded["document"]["draftId"], self.draft.id)
        self.assertEqual(embedded["aiInteractions"][0]["paragraphs"][0]["text"], "First AI paragraph.")
        self.assertEqual(properties["Legal Drafting Tool AI Paragraph Count"], "2")
        self.assertIn("custom-properties", content_types)
        self.assertIn("custom-properties", relationships)
