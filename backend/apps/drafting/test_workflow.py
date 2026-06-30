from types import SimpleNamespace

from django.test import TestCase

from apps.drafting.models import DraftingSession
from apps.drafting.services import (
    advance,
    initialize_session,
    outline_for_session,
    recommend_fact_ids,
    result_to_support_candidate,
    support_query_for_session,
    workflow_step_payload,
)
from apps.matters.models import Matter, MatterFact
from apps.templates_app.models import DocumentTemplate, TemplateBlock


class HumanReviewedDraftingWorkflowTests(TestCase):
    def setUp(self):
        self.matter = Matter.objects.create(
            external_id="LS-100",
            client_name="Jane Tenant",
            matter_type="Eviction",
            jurisdiction="Cleveland Housing Court",
            summary="Tenant has rent dispute and serious repair issues with mold.",
        )
        self.rent_fact = MatterFact.objects.create(
            matter=self.matter,
            slug="rent-dispute",
            title="Rent dispute",
            text="The tenant disputes the balance claimed in the complaint.",
            source_label="LegalServer",
            selected_by_default=False,
        )
        self.repair_fact = MatterFact.objects.create(
            matter=self.matter,
            slug="repair-issues",
            title="Repair issues",
            text="The tenant reported mold and leaks before the filing.",
            source_label="Client notes",
            selected_by_default=False,
        )
        self.template = DocumentTemplate.objects.create(
            title="Answer and Counterclaims",
            slug="answer-counterclaims-test",
            kind="answer_counterclaims",
        )
        TemplateBlock.objects.create(
            template=self.template,
            key="caption",
            label="Caption",
            block_type="caption",
            order=10,
            body="{{ court }}",
            required=True,
        )
        TemplateBlock.objects.create(
            template=self.template,
            key="habitability",
            label="Habitability defense",
            block_type="argument",
            order=20,
            body="Conditions defense.",
            required=False,
            ai_fill_mode="constrained_generation",
            selection_rule={"fact_slugs": ["repair-issues"]},
        )

    def test_workflow_steps_include_action_guidance(self):
        steps = workflow_step_payload()

        self.assertEqual(steps[0]["id"], "setup")
        self.assertIn("support_review", [step["id"] for step in steps])
        self.assertTrue(all(step["help"] for step in steps))

    def test_initialize_session_recommends_template_relevant_facts(self):
        session = DraftingSession.objects.create(
            mode="draft_from_template",
            matter=self.matter,
            template=self.template,
        )

        initialize_session(session)

        self.assertIn(self.repair_fact.id, session.selected_fact_ids)
        self.assertIn("habitability", session.selected_block_keys)

    def test_recommend_fact_ids_uses_selected_block_rules(self):
        session = DraftingSession.objects.create(
            mode="draft_from_template",
            matter=self.matter,
            template=self.template,
            selected_block_keys=["habitability"],
        )

        recommended = recommend_fact_ids(session)

        self.assertIn(self.repair_fact.id, recommended)

    def test_advance_maps_legacy_steps_and_validates_review_prerequisites(self):
        session = DraftingSession.objects.create(
            mode="draft_from_template",
            matter=self.matter,
            template=self.template,
            selected_block_keys=["caption"],
        )

        with self.assertRaisesMessage(ValueError, "Review and select facts"):
            advance(session, {"status": "law"})

        advance(session, {"status": "law", "selectedFactIds": [self.rent_fact.id]})

        self.assertEqual(session.status, "law_review")

    def test_support_query_uses_template_blocks_and_reviewed_facts(self):
        session = DraftingSession.objects.create(
            mode="draft_from_template",
            matter=self.matter,
            template=self.template,
            selected_fact_ids=[self.repair_fact.id],
            selected_block_keys=["habitability"],
            instructions="Focus on conditions as a defense.",
        )

        query = support_query_for_session(session)

        self.assertIn("Habitability defense", query)
        self.assertIn("mold and leaks", query)
        self.assertIn("Cleveland Housing Court", query)

    def test_support_candidates_are_purpose_labeled(self):
        legal_result = SimpleNamespace(
            id="case-1",
            title="Tenant v. Landlord",
            snippet="Habitability defense excerpt",
            source_kind="local_cases",
            source_label="Ohio Cases",
            citation="123 Ohio App. 3d 456",
            url="",
            metadata={},
        )
        example_result = SimpleNamespace(
            id="brief-1",
            title="Example answer pleading",
            snippet="Sample language",
            source_kind="sharepoint",
            source_label="SharePoint",
            citation="",
            url="",
            metadata={},
        )

        legal = result_to_support_candidate(legal_result)
        example = result_to_support_candidate(example_result)

        self.assertEqual(legal["purpose"], "legal_authority")
        self.assertTrue(legal["selectedByDefault"])
        self.assertEqual(example["purpose"], "example_language")
        self.assertTrue(example["selectedByDefault"])

    def test_outline_summarizes_reviewed_inputs(self):
        session = DraftingSession.objects.create(
            mode="draft_from_template",
            matter=self.matter,
            template=self.template,
            selected_fact_ids=[self.repair_fact.id],
            selected_source_results=[{"id": "authority-1"}],
            selected_block_keys=["habitability"],
        )

        outline = outline_for_session(session)

        self.assertEqual(outline["selectedFactCount"], 1)
        self.assertEqual(outline["selectedSupportCount"], 1)
        self.assertIn("habitability", [block["key"] for block in outline["blocks"] if block["selected"]])
