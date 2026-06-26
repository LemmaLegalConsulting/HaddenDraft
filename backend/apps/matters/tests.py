import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.matters.models import Matter, MatterFact, TriageAssessment, TriageRubric
from apps.sources.models import UserSourceIdentity


class FakeLegalServerClient:
    configured = True
    user_filter_param = "assigned_user_email"

    def __init__(self):
        self.calls = []

    def search_matters(self, *, query="", user_email="", limit=50):
        self.calls.append({"query": query, "user_email": user_email, "limit": limit})
        return [
            {
                "id": "LS-REAL-1",
                "client_name": "Real Client",
                "matter_type": "Eviction defense",
                "court": "Housing Court",
                "assignments": [{"user": {"user_name": "quinten"}}],
            }
        ]

    def get_matter(self, matter_id):
        return {
            "id": matter_id,
            "client_name": "Direct Match",
            "matter_type": "Conditions",
            "court": "Housing Court",
        }


@override_settings(ENABLE_DEMO_MATTERS=False)
class CaseConnectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="quinten@lemmalegal.com",
            email="quinten@lemmalegal.com",
            password="password",
        )
        self.client.force_login(self.user)

    @patch("apps.matters.services.LegalServerClient")
    def test_unconnected_user_sees_no_cases_instead_of_demo_seed(self, client_class):
        fake_client = FakeLegalServerClient()
        client_class.return_value = fake_client

        response = self.client.get("/api/cases/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["cases"], [])
        self.assertFalse(payload["legalserver"]["connected"])
        self.assertEqual(payload["legalserver"]["syncError"], "not_connected")
        self.assertEqual(payload["legalserver"]["suggestedIdentifier"], "quinten@lemmalegal.com")
        self.assertFalse(Matter.objects.exists())
        self.assertEqual(fake_client.calls, [])

    @patch("apps.matters.services.LegalServerClient")
    def test_unconnected_user_sees_their_manual_cases(self, client_class):
        fake_client = FakeLegalServerClient()
        client_class.return_value = fake_client
        manual = Matter.objects.create(
            external_id="MANUAL-1",
            client_name="Manual Client",
            matter_type="Eviction defense",
            jurisdiction="Housing Court",
            source_system="Manual",
            raw_payload={"created_by_user_id": self.user.id},
        )

        response = self.client.get("/api/cases/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([case["id"] for case in payload["cases"]], [manual.external_id])
        self.assertEqual(payload["cases"][0]["sourceSystem"], "Manual")
        self.assertEqual(fake_client.calls, [])

    @patch("apps.matters.services.LegalServerClient")
    def test_connected_user_filters_legalserver_by_saved_identifier(self, client_class):
        fake_client = FakeLegalServerClient()
        client_class.return_value = fake_client
        UserSourceIdentity.objects.create(
            user=self.user,
            provider="legalserver",
            identifier="quinten@lemmalegal.com",
        )

        response = self.client.get("/api/cases/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["cases"][0]["id"], "LS-REAL-1")
        self.assertTrue(payload["legalserver"]["connected"])
        self.assertEqual(fake_client.calls[0]["user_email"], "")

    @patch("apps.matters.services.LegalServerClient")
    def test_case_search_does_not_limit_to_primary_assignment(self, client_class):
        fake_client = FakeLegalServerClient()
        client_class.return_value = fake_client
        UserSourceIdentity.objects.create(
            user=self.user,
            provider="legalserver",
            identifier="quinten@lemmalegal.com",
        )

        response = self.client.get("/api/cases/?q=Acme")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["cases"][0]["id"], "LS-REAL-1")
        self.assertEqual(fake_client.calls[0]["query"], "Acme")
        self.assertEqual(fake_client.calls[0]["user_email"], "")

    def test_user_can_connect_legalserver_identifier_without_admin(self):
        response = self.client.post(
            "/api/legalserver/account/",
            data=json.dumps({"identifier": "quinten@lemmalegal.com"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["legalserver"]["connected"])
        identity = UserSourceIdentity.objects.get(user=self.user, provider="legalserver")
        self.assertEqual(identity.identifier, "quinten@lemmalegal.com")

    def test_case_document_context_summarizes_and_searches_case_notes(self):
        matter = Matter.objects.create(
            external_id="LS-DOC-1",
            client_name="Document Client",
            matter_type="Eviction",
            jurisdiction="Housing Court",
            source_system="Manual",
            raw_payload={
                "created_by_user_id": self.user.id,
                "case_notes": [
                    "Tenant has a disability and asked for more time to gather records. Landlord received the request.",
                    "Tenant paid April rent by money order.",
                ]
            },
        )

        list_response = self.client.get(f"/api/cases/{matter.external_id}/documents/")

        self.assertEqual(list_response.status_code, 200)
        documents = list_response.json()["documents"]
        self.assertEqual(documents[0]["kind"], "case_note")

        context_response = self.client.post(
            f"/api/cases/{matter.external_id}/documents/{documents[0]['id']}/context/",
            data=json.dumps({"level": "search", "query": "disability records"}),
            content_type="application/json",
        )

        self.assertEqual(context_response.status_code, 200)
        payload = context_response.json()
        self.assertIn("disability", payload["summary"])
        self.assertEqual(payload["chunks"][0]["index"], 1)

    def test_case_fact_recommendations_select_relevant_and_default_facts(self):
        matter = Matter.objects.create(
            external_id="LS-FACT-1",
            client_name="Fact Client",
            matter_type="Eviction",
            jurisdiction="Housing Court",
            summary="Tenant disputes rent and reported mold repairs.",
            source_system="Manual",
            raw_payload={"created_by_user_id": self.user.id},
        )
        rent = MatterFact.objects.create(
            matter=matter,
            slug="rent-dispute",
            title="Rent dispute",
            text="Tenant disputes rent.",
            source_label="LegalServer",
            selected_by_default=False,
        )
        default = MatterFact.objects.create(
            matter=matter,
            slug="default-note",
            title="Default note",
            text="Selected by default.",
            source_label="LegalServer",
            selected_by_default=True,
        )
        MatterFact.objects.create(
            matter=matter,
            slug="unrelated",
            title="Unrelated",
            text="Not relevant.",
            source_label="LegalServer",
            selected_by_default=False,
        )

        response = self.client.post(f"/api/cases/{matter.external_id}/facts/recommend/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()["factIds"]), {rent.id, default.id})

    def test_user_can_add_typed_case_fact(self):
        matter = Matter.objects.create(
            external_id="LS-FACT-2",
            client_name="Fact Client",
            matter_type="Eviction",
            jurisdiction="Housing Court",
            source_system="Manual",
            raw_payload={"created_by_user_id": self.user.id},
        )

        response = self.client.post(
            f"/api/cases/{matter.external_id}/facts/",
            data=json.dumps({
                "title": "New payment",
                "text": "Client paid $500 after the ledger was printed.",
                "source": "Client call",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        created = response.json()["created"][0]
        self.assertEqual(created["title"], "New payment")
        self.assertEqual(created["source"], "Client call")
        self.assertTrue(MatterFact.objects.filter(matter=matter, slug="new-payment").exists())

    def test_user_can_add_case_fact_from_uploaded_text_document(self):
        matter = Matter.objects.create(
            external_id="LS-FACT-3",
            client_name="Fact Client",
            matter_type="Eviction",
            jurisdiction="Housing Court",
            source_system="Manual",
            raw_payload={"created_by_user_id": self.user.id},
        )

        response = self.client.post(
            f"/api/cases/{matter.external_id}/facts/",
            data={
                "title": "Uploaded repairs",
                "file": SimpleUploadedFile(
                    "repairs.txt",
                    b"Tenant texted landlord about no heat on January 5.",
                    content_type="text/plain",
                ),
            },
        )

        self.assertEqual(response.status_code, 201)
        created = response.json()["created"][0]
        self.assertEqual(created["title"], "Uploaded repairs")
        self.assertIn("no heat", created["text"])

    def test_triage_rubrics_seeds_default_cleveland_rtc_standard(self):
        TriageRubric.objects.all().delete()

        response = self.client.get("/api/triage/rubrics/")

        self.assertEqual(response.status_code, 200)
        rubrics = response.json()["rubrics"]
        self.assertEqual(rubrics[0]["slug"], "cleveland-rtc-priority")
        self.assertIn("Cleveland", rubrics[0]["standard"])

    @override_settings(AI_DRAFTING_ENABLED=False)
    def test_user_can_run_triage_for_manual_case_with_fallback(self):
        matter = Matter.objects.create(
            external_id="MANUAL-TRIAGE-1",
            client_name="Triage Client",
            matter_type="Eviction defense",
            jurisdiction="Cleveland Municipal Court Housing Division",
            summary="Tenant has an eviction hearing tomorrow and has two children in the home.",
            source_system="Manual",
            raw_payload={"created_by_user_id": self.user.id},
        )
        MatterFact.objects.create(
            matter=matter,
            slug="voucher-risk",
            title="Voucher risk",
            text="Client has a Section 8 voucher and received a notice to leave.",
            source_label="Intake",
        )

        response = self.client.post(
            f"/api/cases/{matter.external_id}/triage/",
            data=json.dumps({"rubricSlug": "cleveland-rtc-priority"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        assessment = response.json()["assessment"]
        self.assertTrue(assessment["priority"])
        self.assertEqual(assessment["priorityLabel"], "priority_full_representation")
        self.assertEqual(assessment["rubric"]["slug"], "cleveland-rtc-priority")
        self.assertEqual(TriageAssessment.objects.get().created_by, self.user)

    @override_settings(AI_DRAFTING_ENABLED=False)
    def test_user_can_list_prior_triage_assessments(self):
        matter = Matter.objects.create(
            external_id="MANUAL-TRIAGE-2",
            client_name="Triage Client",
            matter_type="Advice",
            jurisdiction="Cuyahoga County",
            summary="Client asks about repairs.",
            source_system="Manual",
            raw_payload={"created_by_user_id": self.user.id},
        )
        self.client.post(f"/api/cases/{matter.external_id}/triage/")

        response = self.client.get(f"/api/cases/{matter.external_id}/triage/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["assessments"]), 1)

    @patch("apps.matters.services.LegalServerClient")
    def test_user_can_create_manual_case_with_notes_and_multiple_files(self, client_class):
        client_class.return_value = FakeLegalServerClient()

        response = self.client.post(
            "/api/cases/",
            data={
                "clientName": "Local Client",
                "matterType": "Eviction defense",
                "jurisdiction": "Cleveland Housing Court",
                "posture": "Pre-filing intake",
                "notes": "Client says the landlord refused repairs before filing.",
                "files": [
                    SimpleUploadedFile(
                        "notice.txt",
                        b"Three-day notice was posted on the door.",
                        content_type="text/plain",
                    ),
                    SimpleUploadedFile(
                        "ledger.txt",
                        b"Ledger does not credit the February money order.",
                        content_type="text/plain",
                    ),
                ],
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["case"]["client"], "Local Client")
        self.assertEqual(payload["case"]["sourceSystem"], "Manual")
        self.assertEqual(len(payload["created"]), 3)
        matter = Matter.objects.get(external_id=payload["case"]["id"])
        self.assertEqual(matter.raw_payload["created_by_user_id"], self.user.id)
        self.assertEqual(matter.facts.count(), 3)

        detail_response = self.client.get(f"/api/cases/{matter.external_id}/")

        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(len(detail_response.json()["case"]["facts"]), 3)

    def test_cannot_create_empty_manual_case(self):
        response = self.client.post(
            "/api/cases/",
            data=json.dumps({"clientName": "Blank Client"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Matter.objects.filter(client_name="Blank Client").exists())
