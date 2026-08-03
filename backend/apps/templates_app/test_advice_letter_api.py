import json
import zipfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.matters.models import Matter
from apps.templates_app.models import AdviceLetterSection


class AdviceLetterApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="advocate", email="a@example.org", password="pw"
        )
        self.client.force_login(self.user)
        self.matter = Matter.objects.create(
            external_id="2026-CVG-77",
            client_name="Maria Alvarez",
            matter_type="Eviction",
            jurisdiction="Cleveland Municipal Court",
            summary="The 3-day notice names a different landlord than the complaint.",
        )
        AdviceLetterSection.objects.create(
            slug="letter-opening", title="Opening", role="intro", body="Thank you for asking Legal Aid."
        )
        AdviceLetterSection.objects.create(
            slug="letter-closing", title="Closing", role="closing", body="I have closed your file."
        )
        AdviceLetterSection.objects.create(
            slug="decarlo",
            title="DeCarlo",
            topic="Presenting Defenses",
            region="CLE",
            body="There is a legal issue with the 3-Day Notice.",
            status="needs_review",
            needs_attorney_review=True,
            review_reason="2 reviewer comment(s) dropped",
            selection_hints={
                "triggers": ["3-day notice names a different landlord than the complaint"],
                "requires": ["has_3_day_notice"],
                "summary": "Notice and complaint name different parties.",
            },
        )
        AdviceLetterSection.objects.create(
            slug="seal", title="Motion to Seal", topic="Pro se How-To", region="CLE",
            body="You can ask the Court to seal the record.",
        )

    def post(self, path, payload):
        return self.client.post(path, data=json.dumps(payload), content_type="application/json")

    def test_sections_list_reports_review_state(self):
        response = self.client.get("/api/advice-letters/sections/?region=CLE")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        slugs = {section["slug"]: section for section in data["sections"]}
        self.assertIn("decarlo", slugs)
        self.assertTrue(slugs["decarlo"]["needsReview"])
        self.assertIn("comment", slugs["decarlo"]["reviewReason"])
        self.assertEqual(data["awaitingReview"], 1)
        self.assertIn("Presenting Defenses", data["topics"])

    def test_wrapper_is_returned_separately_from_body_sections(self):
        data = self.client.get("/api/advice-letters/sections/").json()

        self.assertEqual(set(data["wrapper"]), {"intro", "closing"})
        self.assertNotIn("letter-opening", {row["slug"] for row in data["sections"]})

    def test_recommendations_explain_themselves(self):
        response = self.post(
            "/api/advice-letters/recommend/",
            {"matterId": "2026-CVG-77", "region": "CLE", "conditions": {"has_3_day_notice": True}},
        )

        self.assertEqual(response.status_code, 200)
        top = response.json()["recommendations"][0]
        self.assertEqual(top["section"]["slug"], "decarlo")
        self.assertTrue(top["needsReview"])
        self.assertTrue(any("3-day notice" in reason for reason in top["reasons"]))

    def test_recommendations_need_a_case(self):
        response = self.post("/api/advice-letters/recommend/", {"matterId": "nope"})

        self.assertEqual(response.status_code, 404)

    def test_preview_assembles_in_the_order_requested(self):
        response = self.post(
            "/api/advice-letters/preview/",
            {"matterId": "2026-CVG-77", "sectionSlugs": ["seal", "decarlo"]},
        )

        self.assertEqual(response.status_code, 200)
        letter = response.json()["letter"]
        slugs = [section["slug"] for section in letter["sections"]]
        self.assertEqual(slugs, ["letter-opening", "seal", "decarlo", "letter-closing"])
        self.assertIn("flesch_kincaid_grade", letter["readability"]["metrics"])

    def test_preview_warns_about_an_unreviewed_section(self):
        letter = self.post(
            "/api/advice-letters/preview/", {"sectionSlugs": ["decarlo"]}
        ).json()["letter"]

        self.assertTrue(any("DeCarlo" in warning for warning in letter["warnings"]))

    def test_preview_needs_at_least_one_section(self):
        response = self.post("/api/advice-letters/preview/", {"sectionSlugs": []})

        self.assertEqual(response.status_code, 400)

    def test_an_unknown_section_is_reported(self):
        response = self.post("/api/advice-letters/preview/", {"sectionSlugs": ["nope"]})

        self.assertEqual(response.status_code, 404)
        self.assertIn("nope", response.json()["error"])

    def test_export_returns_a_word_document(self):
        response = self.post(
            "/api/advice-letters/export/",
            {
                "sectionSlugs": ["seal"],
                "recipientName": "Ms. Alvarez",
                "subject": "Sealing your eviction record",
                "authorProfile": {"displayName": "Dana Ruiz", "title": "Staff Attorney"},
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("advice-letter.docx", response["Content-Disposition"])
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            document = archive.read("word/document.xml").decode("utf-8")
        self.assertIn("Ms. Alvarez", document)
        self.assertIn("seal the record", document)

    def test_endpoints_require_a_login(self):
        self.client.logout()

        self.assertIn(
            self.client.get("/api/advice-letters/sections/").status_code, {302, 401, 403}
        )
