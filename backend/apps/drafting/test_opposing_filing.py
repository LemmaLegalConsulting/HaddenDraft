import io
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from docx import Document

from apps.ai.services import ConstrainedDraftingService, responding_to_prompt
from apps.core.storage import RAW, get_document_storage
from apps.drafting import opposing_filing
from apps.drafting.models import DraftingSession, OpposingFiling
from apps.drafting.services import regeneration_context
from apps.matters.models import Matter
from apps.templates_app.models import DocumentTemplate, TemplateBlock


def _docx_bytes(*paragraphs):
    document = Document()
    for text in paragraphs:
        document.add_paragraph(text)
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


class OpposingFilingApiTests(TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        storage = override_settings(
            DOCUMENT_STORAGE_BACKEND="filesystem",
            DOCUMENT_STORAGE_ROOT=str(Path(self.scratch.name)),
        )
        storage.enable()
        self.addCleanup(storage.disable)
        self.user = User.objects.create_user("advocate", password="pw")
        self.client.force_login(self.user)
        self.matter = Matter.objects.create(
            external_id="MANUAL-REPLY-1",
            client_name="Jane Tenant",
            matter_type="Eviction defense",
            source_system="Manual",
            summary="Plaintiff opposed the motion for summary judgment.",
            raw_payload={
                "created_by_user_id": self.user.id,
                "case_notes": [{"subject": "Call", "body": "Client called about the hearing."}],
                "documents": [
                    {
                        "id": "opp-1",
                        "title": "2026-09-12 Plaintiff's Brief in Opposition - FILED.pdf",
                        "date": "2026-09-12",
                        "text": "Plaintiff argues that the acceptance of rent was inadvertent and did not waive the notice.",
                    },
                    {"id": "lease-1", "title": "Lease.pdf", "date": "2025-01-01", "text": "Residential lease."},
                ],
            },
        )
        self.template = DocumentTemplate.objects.create(
            title="Reply in Support of Motion for Summary Judgment",
            slug="reply-test",
            kind="brief",
            metadata={
                "respondsTo": {
                    "required": True,
                    "expects": ["brief_in_opposition"],
                    "question": "Which brief in opposition is this reply answering?",
                }
            },
        )
        TemplateBlock.objects.create(
            template=self.template,
            key="reply-argument",
            label="Reply argument",
            block_type="argument",
            order=10,
            body="Answer the opposition.",
            ai_latitude="generate",
            ai_fill_mode="constrained_generation",
            ai_instructions=["Answer the arguments in the order the opposition makes them."],
        )
        self.session = DraftingSession.objects.create(
            mode="draft_from_template", matter=self.matter, template=self.template
        )
        self.url = f"/api/drafting-sessions/{self.session.id}/opposing-filing/"

    def _document_id(self, title_prefix):
        documents = self.client.get(self.url).json()["caseFileDocuments"]
        return next(document["documentId"] for document in documents if document["title"].startswith(title_prefix))

    def test_get_reports_the_requirement_and_case_file_documents(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIsNone(body["opposingFiling"])
        self.assertTrue(body["requirement"]["required"])
        self.assertIn("Which brief in opposition", body["missing"])
        self.assertEqual(body["caseFileProblem"], "")
        titles = [document["title"] for document in body["caseFileDocuments"]]
        # Newest first, and case notes are not filings.
        self.assertEqual(titles, ["2026-09-12 Plaintiff's Brief in Opposition - FILED.pdf", "Lease.pdf"])

    def test_choosing_a_case_file_document_keeps_a_reference_only(self):
        document_id = self._document_id("2026-09-12")
        response = self.client.put(self.url, {"documentId": document_id}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        filing = response.json()["opposingFiling"]
        self.assertEqual(filing["sourceType"], "matter_document")
        self.assertEqual(filing["documentId"], document_id)
        self.assertEqual(filing["description"], "Plaintiff's Brief in Opposition")
        self.assertEqual(filing["displayName"], "Plaintiff's Brief in Opposition, filed September 12, 2026")
        self.assertEqual(response.json()["missing"], "")
        stored = OpposingFiling.objects.get(session=self.session)
        self.assertEqual(stored.extracted_text, "")
        self.assertEqual(stored.storage_key, "")

        # The text is read from the case file when drafting.
        context = opposing_filing.prompt_context(self.session)
        self.assertIn("acceptance of rent was inadvertent", context["text"])

    def test_a_document_outside_the_case_file_is_refused(self):
        response = self.client.put(self.url, {"documentId": "not-here"}, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(OpposingFiling.objects.exists())

    def test_uploading_a_copy_stores_it_in_raw_and_extracts_its_text(self):
        upload = SimpleUploadedFile(
            "Opposition served by email.docx",
            _docx_bytes("PLAINTIFF'S BRIEF IN OPPOSITION", "The rent was accepted by mistake."),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        response = self.client.post(self.url, {"file": upload, "filedOn": "2026-09-15"})
        self.assertEqual(response.status_code, 201)
        filing = response.json()["opposingFiling"]
        self.assertEqual(filing["sourceType"], "upload")
        self.assertEqual(filing["displayName"], "Opposition served by email, filed September 15, 2026")
        stored = OpposingFiling.objects.get(session=self.session)
        self.assertIn("accepted by mistake", stored.extracted_text)
        self.assertTrue(stored.storage_key.startswith(f"drafting/opposing-filings/{self.session.id}/"))
        self.assertTrue(get_document_storage(RAW).exists(stored.storage_key))

        # Removing it removes the stored copy too.
        key = stored.storage_key
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["opposingFiling"])
        self.assertFalse(get_document_storage(RAW).exists(key))

    def test_an_unreadable_upload_is_refused(self):
        upload = SimpleUploadedFile("blank.docx", _docx_bytes(""), content_type="application/octet-stream")
        response = self.client.post(self.url, {"file": upload})
        self.assertEqual(response.status_code, 400)
        self.assertIn("No readable text", response.json()["error"])

    def test_patch_changes_how_the_draft_names_the_filing(self):
        self.client.put(self.url, {"documentId": self._document_id("2026-09-12")}, content_type="application/json")
        response = self.client.patch(
            self.url,
            {"description": "Plaintiff's Memorandum Contra", "filedOn": "2026-09-13"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["opposingFiling"]["displayName"], "Plaintiff's Memorandum Contra, filed September 13, 2026"
        )
        response = self.client.patch(self.url, {"filedOn": "9/13/2026"}, content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_generation_waits_for_a_required_filing(self):
        response = self.client.post(
            f"/api/drafting-sessions/{self.session.id}/drafts/",
            {},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.json()["opposingFilingRequired"])

    def test_another_users_session_is_not_found(self):
        other = User.objects.create_user("other", password="pw")
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.url).status_code, 404)


class _RecordingClient:
    def __init__(self):
        self.prompts = []

    def complete(self, *, system, user, model=None, reasoning_level=None):
        self.prompts.append(user)
        return "Plaintiff's first argument fails."


@override_settings(AI_DRAFTING_ENABLED=True)
class OpposingFilingPromptTests(TestCase):
    def test_the_section_prompt_carries_the_filing_and_the_authors_directions(self):
        user = User.objects.create_user("advocate", password="pw")
        matter = Matter.objects.create(
            external_id="MANUAL-REPLY-2",
            client_name="Jane Tenant",
            source_system="Manual",
            summary="Reply to opposition.",
            raw_payload={
                "created_by_user_id": user.id,
                "documents": [{"id": "opp-1", "title": "Opposition.pdf", "text": "Plaintiff says the notice was proper."}],
            },
        )
        template = DocumentTemplate.objects.create(title="Reply", slug="reply-prompt-test", kind="brief")
        TemplateBlock.objects.create(
            template=template,
            key="reply-argument",
            label="Reply argument",
            block_type="argument",
            order=10,
            body="Answer the opposition.",
            ai_latitude="generate",
            ai_fill_mode="constrained_generation",
            ai_instructions=["Answer the arguments in the order the opposition makes them."],
        )
        session = DraftingSession.objects.create(mode="draft_from_template", matter=matter, template=template)
        [choice], _problem = opposing_filing.case_file_choices(session)
        opposing_filing.choose_case_document(
            session, choice["documentId"], user=user, description="Plaintiff's Brief in Opposition"
        )

        recorder = _RecordingClient()
        sections = ConstrainedDraftingService(llm_client=recorder).compose_document(
            regeneration_context(session), ["reply-argument"]
        )
        self.assertEqual(sections[0]["body"], "Plaintiff's first argument fails.")
        [prompt] = recorder.prompts
        self.assertIn("This document answers: Plaintiff's Brief in Opposition.", prompt)
        self.assertIn("Plaintiff says the notice was proper.", prompt)
        self.assertIn("- Answer the arguments in the order the opposition makes them.", prompt)

    def test_a_document_that_answers_nothing_says_so(self):
        self.assertIn("does not answer a particular filing", responding_to_prompt(None))

    def test_a_long_filing_is_capped_and_the_cap_is_stated(self):
        text = "word " * (opposing_filing.PROMPT_TEXT_LIMIT // 2)
        rendered = responding_to_prompt(
            {"description": "The opposition", "text": text[: opposing_filing.PROMPT_TEXT_LIMIT], "note": "Only the first 30,000 characters of the filing are included; it is longer."}
        )
        self.assertIn("Only the first 30,000 characters", rendered)
