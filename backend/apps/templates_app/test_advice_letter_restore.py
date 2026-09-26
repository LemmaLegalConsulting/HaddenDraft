"""Reopening a saved advice letter by URL reads it; it never reassembles it.

Assembly replaces section text with the catalog's when a section is new to
the letter, so a reopened letter that went through assembly on load could lose
an advocate's edits. The read endpoint returns the letter as saved.
"""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.drafting.models import DraftDocument, DraftingSession
from apps.matters.models import Matter
from apps.matters.route_aliases import sync_matter_route_alias
from apps.templates_app.models import AdviceLetterSection


@override_settings(AI_DRAFTING_ENABLED=False)
class AdviceLetterRestoreTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(username="advocate", email="a@example.org", password="pw")
        self.client.force_login(self.user)
        self.matter = Matter.objects.create(
            external_id="MID-1",
            client_name="Maria Alvarez",
            matter_type="Eviction",
            jurisdiction="Cleveland Municipal Court",
            raw_payload={"case_number": "26-0222"},
        )
        sync_matter_route_alias(self.matter)
        self.other = Matter.objects.create(
            external_id="MID-2", client_name="Other", matter_type="Eviction", jurisdiction="X", raw_payload={"case_number": "26-0333"}
        )
        sync_matter_route_alias(self.other)
        AdviceLetterSection.objects.create(slug="letter-opening", title="Opening", role="intro", body="Thank you for asking.")
        AdviceLetterSection.objects.create(slug="letter-closing", title="Closing", role="closing", body="I have closed your file.")
        AdviceLetterSection.objects.create(slug="seal", title="Sealing", topic="Records", region="CLE", body="You may be able to seal.")
        created = self.client.post(
            "/api/advice-letters/drafts/",
            data=json.dumps({"matterId": "MID-1", "sectionSlugs": ["seal"], "goal": "Explain sealing", "region": "CLE"}),
            content_type="application/json",
        ).json()
        self.draft_id = created["draft"]["id"]
        self.url = f"/api/advice-letters/drafts/{self.draft_id}/"

    def test_reopening_returns_the_letter_and_its_choices_as_saved(self):
        response = self.client.get(self.url, {"caseKey": "26-0222"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["draft"]["id"], self.draft_id)
        self.assertEqual(payload["advice"]["sectionSlugs"], ["seal"])
        self.assertEqual(payload["advice"]["goal"], "Explain sealing")
        self.assertIn("filename", payload["letterFields"])

    def test_reopening_changes_nothing(self):
        before = DraftDocument.objects.get(id=self.draft_id)
        self.client.get(self.url)
        after = DraftDocument.objects.get(id=self.draft_id)
        self.assertEqual((after.revision, after.updated_at), (before.revision, before.updated_at))
        self.assertEqual(after.components.count(), before.components.count())

    def test_a_letter_on_another_case_answers_as_missing(self):
        self.assertEqual(self.client.get(self.url, {"caseKey": "26-0333"}).status_code, 404)

    def test_a_drafting_document_is_not_an_advice_letter(self):
        session = DraftingSession.objects.create(mode="draft_from_template", matter=self.matter)
        other = DraftDocument.objects.create(session=session, title="Answer", sections=[], plain_text="")
        self.assertEqual(self.client.get(f"/api/advice-letters/drafts/{other.id}/").status_code, 404)

    def test_reassembly_against_an_old_revision_is_refused(self):
        draft = DraftDocument.objects.get(id=self.draft_id)
        response = self.client.post(
            "/api/advice-letters/drafts/",
            data=json.dumps({"matterId": "MID-1", "draftId": self.draft_id, "sectionSlugs": ["seal"], "revision": draft.revision - 1}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["conflict"], "draft")

    def test_the_case_list_links_each_letter(self):
        response = self.client.get("/api/drafting-sessions/", {"caseKey": "26-0222", "workspace": "advice-letters"}).json()
        self.assertEqual(response["total"], 1)
        self.assertEqual(response["sessions"][0]["draftId"], self.draft_id)


class TemplateFillRouteTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(username="advocate", email="a@example.org", password="pw")
        self.client.force_login(self.user)
        self.matter = Matter.objects.create(external_id="MID-1", client_name="A", matter_type="E", jurisdiction="X", raw_payload={"case_number": "26-0222"})
        sync_matter_route_alias(self.matter)
        other = Matter.objects.create(external_id="MID-2", client_name="B", matter_type="E", jurisdiction="X", raw_payload={"case_number": "26-0333"})
        sync_matter_route_alias(other)
        self.session = DraftingSession.objects.create(mode="template_fill", matter=self.matter, fill_state={"title": "Motion", "fields": [], "answers": {}, "revision": 0})

    def test_a_fill_session_opens_on_its_own_case_only(self):
        url = f"/api/template-fill/sessions/{self.session.id}/"
        self.assertEqual(self.client.get(url, {"caseKey": "26-0222"}).status_code, 200)
        self.assertEqual(self.client.get(url, {"caseKey": "26-0333"}).status_code, 404)
