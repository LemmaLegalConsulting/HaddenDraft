import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from apps.drafting.components import (
    component_history,
    record_sections,
    sections_from_components,
    sync_components,
)
from apps.drafting.models import DocumentComponent, DraftDocument, DraftingSession
from apps.drafting.services import create_draft, regenerate_draft_block
from apps.matters.models import Matter, MatterFact
from apps.templates_app.models import DocumentTemplate, TemplateBlock


@override_settings(AI_DRAFTING_ENABLED=False, ENABLE_DEMO_MATTERS=True)
class DocumentComponentTests(TestCase):
    """Sections are projected onto durable components with their own history."""

    def setUp(self):
        self.matter = Matter.objects.create(
            external_id="LS-COMPONENTS",
            client_name="Jane Tenant",
            matter_type="Eviction",
            jurisdiction="Cleveland Housing Court",
            summary="Tenant disputes rent and reports mold.",
            source_system="Demo",
        )
        MatterFact.objects.create(
            matter=self.matter,
            slug="repair-issues",
            title="Repair issues",
            text="The tenant reported mold before the filing.",
            source_label="Client notes",
        )
        self.template = DocumentTemplate.objects.create(
            title="Answer and Counterclaims",
            slug="answer-components-test",
            kind="answer_counterclaims",
        )
        TemplateBlock.objects.create(
            template=self.template,
            key="caption",
            label="Caption",
            block_type="caption",
            order=10,
            body="IN THE HOUSING COURT",
            required=True,
        )
        TemplateBlock.objects.create(
            template=self.template,
            key="habitability",
            label="Habitability defense",
            block_type="argument",
            order=20,
            body="Conditions defense.",
            required=True,
        )
        self.session = DraftingSession.objects.create(
            mode="draft_from_template",
            matter=self.matter,
            template=self.template,
            selected_block_keys=["caption", "habitability"],
        )

    def test_generated_draft_records_one_component_per_section(self):
        draft = create_draft(self.session)

        components = list(draft.components.order_by("position"))

        self.assertEqual([component.stable_key for component in components], ["caption", "habitability"])
        self.assertEqual([component.component_type for component in components], ["caption", "argument"])
        self.assertTrue(all(component.current_version.sequence == 1 for component in components))

    def test_components_project_back_to_the_section_shape(self):
        draft = create_draft(self.session)

        self.assertEqual(sections_from_components(draft), draft.sections)

    def test_regenerating_a_block_versions_only_that_component(self):
        draft = create_draft(self.session)
        original_body = next(
            section["body"] for section in draft.sections if section["key"] == "habitability"
        )

        regenerate_draft_block(draft, "habitability", "Emphasize the mold reports.")

        habitability = draft.components.get(stable_key="habitability")
        caption = draft.components.get(stable_key="caption")
        self.assertEqual(caption.versions.count(), 1)
        self.assertEqual([version.sequence for version in habitability.versions.order_by("sequence")], [1, 2])
        first, second = habitability.versions.order_by("sequence")
        self.assertEqual(first.body, original_body)
        self.assertEqual(second.origin, "ai")
        self.assertEqual(second.instruction, "Emphasize the mold reports.")

    def test_unchanged_sections_do_not_accumulate_versions(self):
        draft = create_draft(self.session)

        sync_components(draft)
        record_sections(draft, draft.sections)

        self.assertEqual(
            [component.versions.count() for component in draft.components.all()],
            [1, 1],
        )

    def test_reviewer_edits_are_recorded_as_human_versions(self):
        draft = create_draft(self.session)
        edited = [
            {**section, "body": "Reviewer rewrote this."} if section["key"] == "habitability" else section
            for section in draft.sections
        ]

        record_sections(draft, edited, origin="human")

        latest = draft.components.get(stable_key="habitability").current_version
        self.assertEqual(latest.origin, "human")
        self.assertEqual(latest.body, "Reviewer rewrote this.")
        self.assertIn("Reviewer rewrote this.", draft.plain_text)

    def test_dropped_sections_are_retired_but_keep_their_history(self):
        draft = create_draft(self.session)

        record_sections(draft, [section for section in draft.sections if section["key"] == "caption"])

        retired = DocumentComponent.objects.get(document=draft, stable_key="habitability")
        self.assertIsNotNone(retired.removed_at)
        self.assertEqual(retired.versions.count(), 1)
        self.assertEqual([section["key"] for section in sections_from_components(draft)], ["caption"])

    def test_repeated_section_keys_stay_separate_components(self):
        draft = create_draft(self.session)
        duplicated = [*draft.sections, {"key": "caption", "label": "Second caption", "body": "Later caption."}]

        record_sections(draft, duplicated)

        self.assertEqual(
            list(draft.components.filter(removed_at__isnull=True).values_list("stable_key", flat=True)),
            ["caption", "habitability", "caption-2"],
        )

    def test_documents_written_before_this_layer_are_backfilled_on_demand(self):
        legacy = DraftDocument.objects.create(
            session=self.session,
            template=self.template,
            title="Legacy draft",
            sections=[{"key": "caption", "label": "Caption", "body": "Older text."}],
            plain_text="CAPTION\nOlder text.",
        )

        history = component_history(legacy)

        self.assertEqual([item["stableKey"] for item in history], ["caption"])
        self.assertEqual(history[0]["versions"][0]["body"], "Older text.")

    def test_component_history_endpoint_exposes_versions_for_review(self):
        draft = create_draft(self.session)
        regenerate_draft_block(draft, "habitability", "Tighten the argument.")
        User.objects.create_user("reviewer", password="reviewer-pass")
        self.client.login(username="reviewer", password="reviewer-pass")

        response = self.client.get(reverse("api_draft_components", args=[draft.id]))

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)["components"]
        habitability = next(item for item in payload if item["stableKey"] == "habitability")
        self.assertEqual(habitability["currentVersionSequence"], 2)
        self.assertEqual([version["origin"] for version in habitability["versions"]], ["template", "ai"])

    def test_draft_patch_api_records_the_replaced_text(self):
        draft = create_draft(self.session)
        User.objects.create_user("editor", password="editor-pass")
        self.client.login(username="editor", password="editor-pass")
        edited = [
            {**section, "body": "Edited in the browser."} if section["key"] == "caption" else section
            for section in draft.sections
        ]

        response = self.client.patch(
            reverse("api_draft_detail", args=[draft.id]),
            data=json.dumps({"sections": edited}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        caption = DraftDocument.objects.get(id=draft.id).components.get(stable_key="caption")
        self.assertEqual(caption.versions.count(), 2)
        self.assertEqual(caption.current_version.origin, "human")
        self.assertEqual(caption.versions.order_by("sequence").first().body, "IN THE HOUSING COURT")
