from django.test import TestCase

from apps.matters.document_context import case_materials_payload, get_case_documents
from apps.matters.models import LegalServerDelivery, Matter
from apps.matters.work_product import evidence_only
from apps.templates_app.models import DocumentTemplate


class CaseFileClient:
    """A LegalServer case file holding the client's evidence and this tool's output."""

    configured = True

    def __init__(self, documents):
        self.documents = documents

    def get_matter(self, _identifier):
        return {}

    def get_matter_notes(self, _identifier):
        return []

    def get_matter_documents(self, _identifier):
        return self.documents


class WorkProductTests(TestCase):
    def setUp(self):
        self.matter = Matter.objects.create(
            external_id="26-000085",
            client_name="Heat Client",
            matter_type="Conditions",
            source_system="LegalServer",
            raw_payload={
                "matter_uuid": "72d4848e-7187-11f1-bb35-0a2523f9a7d8",
                "notes": [
                    {"id": "n1", "subject": "Intake Notes", "body": "No heat since January 3."},
                    {"id": "n2", "subject": "Case chat: summarize the lack of heat", "body": "AI: I found these case documents: …"},
                    {"id": "n3", "subject": "AI usage audit — CLE Emergency Motion for Heat", "body": "Model: …"},
                ],
            },
        )
        DocumentTemplate.objects.get_or_create(
            slug="e2e-work-product-heat",
            defaults={"title": "E2E Emergency Motion for Heat", "kind": "motion", "is_active": True},
        )

    def _documents(self):
        return [
            {"id": "d1", "filename": "Gas_Company_Inspection_Report.pdf", "download_url": "https://files.example/1"},
            {"id": "d2", "title": "E2E Emergency Motion for Heat", "filename": "motion.docx", "download_url": "https://files.example/2"},
            {"id": "d3", "title": "Client advice letter", "filename": "letter.docx", "download_url": "https://files.example/3"},
            {"id": "d4", "title": "Photo of meter", "filename": "meter.png", "download_url": "https://files.example/4"},
        ]

    def test_the_tools_own_notes_and_drafts_are_labelled(self):
        payload = case_materials_payload(self.matter, client=CaseFileClient(self._documents()))

        labelled = {item["title"]: bool(item["workProduct"]) for item in payload["notes"] + payload["documents"]}
        self.assertEqual(labelled["Intake Notes"], False)
        self.assertEqual(labelled["Case chat: summarize the lack of heat"], True)
        self.assertEqual(labelled["AI usage audit — CLE Emergency Motion for Heat"], True)
        self.assertEqual(labelled["Gas_Company_Inspection_Report.pdf"], False)
        self.assertEqual(labelled["E2E Emergency Motion for Heat"], True)
        self.assertEqual(labelled["Client advice letter"], True)

    def test_a_recorded_delivery_marks_its_document_whatever_it_is_called(self):
        LegalServerDelivery.objects.create(
            matter=self.matter,
            kind=LegalServerDelivery.DOCUMENT,
            status=LegalServerDelivery.SAVED,
            title="Renamed by the advocate",
            remote_id="d4",
        )

        documents = get_case_documents(self.matter, client=CaseFileClient(self._documents()))

        meter = next(item for item in documents if item["title"] == "Photo of meter")
        self.assertTrue(meter["workProduct"])

    def test_only_evidence_reaches_fact_recommendation(self):
        documents = get_case_documents(self.matter, client=CaseFileClient(self._documents()))

        titles = {item["title"] for item in evidence_only(documents)}

        self.assertEqual(titles, {"Intake Notes", "Gas_Company_Inspection_Report.pdf", "Photo of meter"})


class TriageReadsNoWorkProductTests(TestCase):
    def test_triage_text_leaves_out_the_tools_own_notes(self):
        from apps.matters.triage import matter_triage_text

        matter = Matter.objects.create(
            external_id="26-000086",
            client_name="Heat Client",
            matter_type="Conditions",
            source_system="LegalServer",
            raw_payload={
                "notes": [
                    {"subject": "Intake Notes", "body": "No heat since January 3."},
                    {"subject": "AI usage audit — CLE Emergency Motion for Heat", "body": "Summary of the drafted motion."},
                    {"subject": "Case chat: what happened?", "body": "AI: the case is about heat."},
                ],
            },
        )

        text = matter_triage_text(matter)

        self.assertIn("No heat since January 3.", text)
        self.assertNotIn("Summary of the drafted motion.", text)
        self.assertNotIn("AI: the case is about heat.", text)
