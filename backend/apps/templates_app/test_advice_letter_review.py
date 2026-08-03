import json
import tempfile
from pathlib import Path

import yaml
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase

from apps.templates_app.admin import AdviceLetterSectionAdmin, AdviceLetterSectionAdminForm
from apps.templates_app.advice_letter_library import (
    _review_defaults,
    sections_awaiting_review,
    selectable_sections,
    sync_advice_letters,
)
from apps.templates_app.models import AdviceLetterSection


class ReviewFlagTests(TestCase):
    """Everything is loaded; the flag is what marks unchecked text."""

    def test_accepted_tracked_changes_flag_the_section(self):
        defaults = _review_defaults(
            {"status": "needs_review", "source": {"tracked_changes": 82, "comments": 0}}
        )

        self.assertTrue(defaults["needs_attorney_review"])
        self.assertIn("82 tracked change(s) accepted here", defaults["review_reason"])

    def test_drafted_text_flags_the_section(self):
        defaults = _review_defaults({"status": "ai_drafted"})

        self.assertTrue(defaults["needs_attorney_review"])
        self.assertIn("drafted here", defaults["review_reason"])

    def test_a_merge_boundary_flags_the_section(self):
        defaults = _review_defaults(
            {"status": "ready", "copyedit": {"flags": [{"kind": "merge_boundary"}]}}
        )

        self.assertTrue(defaults["needs_attorney_review"])
        self.assertIn("merge boundary", defaults["review_reason"])

    def test_clean_maintained_text_is_not_flagged(self):
        defaults = _review_defaults(
            {"status": "ready", "source": {"tracked_changes": 0}, "copyedit": {"fixes": []}}
        )

        self.assertFalse(defaults["needs_attorney_review"])
        self.assertEqual(defaults["review_reason"], "")


class SectionAvailabilityTests(TestCase):
    def setUp(self):
        AdviceLetterSection.objects.create(
            slug="clean", title="Clean", body="Text.", status="ready"
        )
        AdviceLetterSection.objects.create(
            slug="flagged",
            title="Flagged",
            body="Text.",
            status="needs_review",
            needs_attorney_review=True,
            review_reason="12 tracked change(s) accepted here",
        )
        AdviceLetterSection.objects.create(
            slug="retired", title="Retired", body="Text.", status="stub"
        )

    def test_flagged_sections_are_still_offered(self):
        slugs = set(selectable_sections().values_list("slug", flat=True))

        self.assertEqual(slugs, {"clean", "flagged"})

    def test_a_retired_section_is_not_offered(self):
        self.assertNotIn("retired", set(selectable_sections().values_list("slug", flat=True)))

    def test_reviewed_only_narrows_to_approved_text(self):
        slugs = set(selectable_sections(reviewed_only=True).values_list("slug", flat=True))

        self.assertEqual(slugs, {"clean"})

    def test_the_review_queue_lists_what_needs_reading(self):
        self.assertEqual(
            set(sections_awaiting_review().values_list("slug", flat=True)), {"flagged"}
        )

    def test_review_summary_explains_itself(self):
        flagged = AdviceLetterSection.objects.get(slug="flagged")
        clean = AdviceLetterSection.objects.get(slug="clean")

        self.assertIn("tracked change", flagged.review_summary)
        self.assertEqual(clean.review_summary, "")
        self.assertTrue(clean.sendable)
        self.assertFalse(flagged.sendable)


class AdminReviewTests(TestCase):
    def setUp(self):
        self.admin = AdviceLetterSectionAdmin(AdviceLetterSection, AdminSite())
        self.user = get_user_model().objects.create_superuser(
            username="attorney", email="a@example.org", password="x"
        )
        self.request = RequestFactory().get("/admin/")
        self.request.user = self.user
        # Admin actions report through the message framework, which needs
        # storage that RequestFactory does not attach.
        self.request.session = {}
        self.request._messages = FallbackStorage(self.request)
        self.section = AdviceLetterSection.objects.create(
            slug="flagged",
            title="Flagged",
            body="Text.",
            status="needs_review",
            needs_attorney_review=True,
            review_reason="12 tracked change(s) accepted here",
        )

    def test_marking_reviewed_records_who_and_when(self):
        self.admin.mark_reviewed(self.request, AdviceLetterSection.objects.all())

        self.section.refresh_from_db()
        self.assertFalse(self.section.needs_attorney_review)
        self.assertEqual(self.section.reviewed_by, self.user)
        self.assertIsNotNone(self.section.reviewed_at)
        self.assertTrue(self.section.is_locally_edited)

    def test_flagging_clears_a_previous_review(self):
        self.admin.mark_reviewed(self.request, AdviceLetterSection.objects.all())
        self.admin.flag_for_review(self.request, AdviceLetterSection.objects.all())

        self.section.refresh_from_db()
        self.assertTrue(self.section.needs_attorney_review)
        self.assertIsNone(self.section.reviewed_at)

    def test_rich_admin_form_round_trips_formatting_and_spacing(self):
        state = {
            "root": {
                "children": [
                    {
                        "children": [
                            {"text": "Heading.  ", "format": 1, "type": "text"},
                            {"text": "Body.", "format": 0, "type": "text"},
                        ],
                        "type": "paragraph",
                    },
                    {"children": [], "type": "paragraph"},
                ],
                "type": "root",
            }
        }
        self.section.editor_state = state
        self.section.body = "Heading.  Body.\n"
        self.section.save()

        form = AdviceLetterSectionAdminForm(instance=self.section)
        data = {}
        for name in form.fields:
            value = form.initial.get(name, "")
            if name == "editor_state" or isinstance(value, (dict, list)):
                value = json.dumps(value)
            elif value is None:
                value = ""
            data[name] = value
        bound = AdviceLetterSectionAdminForm(instance=self.section, data=data)

        self.assertTrue(bound.is_valid(), bound.errors)
        saved = bound.save(commit=False)
        self.assertEqual(saved.editor_state, state)
        self.assertEqual(saved.body, "Heading.  Body.\n")


class LocalEditPreservationTests(TestCase):
    """An attorney's read must survive the next ingest."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        package = self.root / "advice-letters"
        package.mkdir(parents=True)
        (package / "catalog.yaml").write_text(
            yaml.safe_dump(
                {
                    "schema_version": 1,
                    "slug": "client-advice-letters",
                    "sections": [
                        {
                            "slug": "decarlo",
                            "title": "DeCarlo",
                            "body": "Maintained wording.",
                            "status": "needs_review",
                            "source": {"tracked_changes": 4},
                        }
                    ],
                }
            )
        )

    def library(self):
        return self.settings(
            CONTENT_LIBRARY_DIR=self.root, ORGANIZATION_CONTENT_LIBRARY_DIR=self.root / "private"
        )

    def test_first_sync_creates_and_flags(self):
        with self.library():
            sync_advice_letters()

        section = AdviceLetterSection.objects.get(slug="decarlo")
        self.assertTrue(section.needs_attorney_review)
        self.assertFalse(section.is_locally_edited)

    def test_a_reviewed_edit_is_not_overwritten(self):
        with self.library():
            sync_advice_letters()
            section = AdviceLetterSection.objects.get(slug="decarlo")
            section.body = "Wording an attorney corrected."
            section.needs_attorney_review = False
            section.is_locally_edited = True
            section.save()

            results = sync_advice_letters()

        section.refresh_from_db()
        self.assertEqual(section.body, "Wording an attorney corrected.")
        self.assertFalse(section.needs_attorney_review)
        self.assertIn({"slug": "decarlo", "status": "preserved"}, results)

    def test_an_untouched_section_still_refreshes(self):
        with self.library():
            sync_advice_letters()
            AdviceLetterSection.objects.filter(slug="decarlo").update(body="stale")
            sync_advice_letters()

        self.assertEqual(
            AdviceLetterSection.objects.get(slug="decarlo").body, "Maintained wording."
        )
