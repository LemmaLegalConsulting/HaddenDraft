import json
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import TestCase
from django.test.utils import override_settings

from apps.drafting.models import DraftingSession
from apps.drafting.services import (
    advance,
    create_draft,
    fact_retrieval_plan,
    initialize_session,
    outline_for_session,
    recommend_fact_ids,
    regeneration_context,
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

    def test_template_data_survives_advance_and_draft_generation(self):
        caption = self.template.blocks.get(key="caption")
        caption.body = "{{ plaintiff }}"
        caption.save(update_fields=["body"])
        session = DraftingSession.objects.create(
            mode="draft_from_template",
            matter=self.matter,
            template=self.template,
            selected_fact_ids=[self.rent_fact.id],
            selected_block_keys=["caption"],
        )

        advance(session, {"status": "draft_review", "templateData": {"plaintiff_name": "Acme Homes"}})

        self.assertEqual(session.template_data, {"plaintiff_name": "Acme Homes"})
        self.assertEqual(regeneration_context(session).template_data, session.template_data)
        draft = create_draft(session)
        self.assertIn("Acme Homes", draft.sections[0]["body"])

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


class DraftingMigrationCompatibilityTests(TestCase):
    def test_template_data_is_in_model_and_latest_migration_state(self):
        field = DraftingSession._meta.get_field("template_data")
        self.assertEqual(field.get_default(), {})

        loader = MigrationLoader(connection)
        self.assertNotIn("drafting", loader.detect_conflicts())
        leaves = loader.graph.leaf_nodes("drafting")
        self.assertEqual(leaves, [("drafting", "0005_draftingsession_template_data")])
        state_model = loader.project_state(leaves).apps.get_model("drafting", "DraftingSession")
        self.assertEqual(state_model._meta.get_field("template_data").get_default(), {})


@override_settings(AI_DRAFTING_ENABLED=False, ENABLE_DEMO_MATTERS=False)
class DraftingFactRecommendationApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="drafter", password="password")
        self.client.force_login(self.user)
        self.matter = Matter.objects.create(
            external_id="MANUAL-DRAFT-1",
            client_name="No Facts Client",
            matter_type="Eviction defense",
            jurisdiction="Housing Court",
            source_system="Manual",
            summary="Prepare a habitability defense based on repair problems.",
            raw_payload={
                "created_by_user_id": self.user.id,
                "case_notes": [
                    {
                        "subject": "Repair history",
                        "body": "The client reported mold and a leaking ceiling on May 2. The landlord received the repair request but did not respond.",
                    }
                ],
                "documents": [
                    {
                        "id": "inspection-1",
                        "title": "Housing inspection report",
                        "source": "Case upload",
                        "text": "The inspector observed active water leaks, mold, and unrepaired ceiling damage in the apartment.",
                    }
                ],
            },
        )
        self.template = DocumentTemplate.objects.create(
            title="Conditions Motion",
            slug="conditions-motion-api-test",
            kind="motion",
        )
        TemplateBlock.objects.create(
            template=self.template,
            key="conditions",
            label="Habitability and repair conditions",
            block_type="argument",
            order=10,
            body="Conditions argument.",
            required=True,
            selection_rule={"fact_slugs": ["repair-issues"]},
        )

    def _create_session(self):
        response = self.client.post(
            "/api/drafting-sessions/",
            data=json.dumps(
                {
                    "mode": "draft_from_template",
                    "matterId": self.matter.external_id,
                    "templateId": self.template.id,
                    "templateData": {"landlord_name": "Example Landlord"},
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        return response

    def test_session_creation_accepts_and_returns_template_data(self):
        response = self._create_session()

        session = DraftingSession.objects.get(id=response.json()["session"]["id"])
        self.assertEqual(session.template_data, {"landlord_name": "Example Landlord"})
        self.assertEqual(response.json()["session"]["templateData"], session.template_data)

    def test_fact_retrieval_plan_has_progressive_patterns_for_required_slugs(self):
        session = DraftingSession.objects.create(
            mode="draft_from_template",
            matter=self.matter,
            template=self.template,
            selected_block_keys=["conditions"],
            instructions="Focus on the ignored written repair request.",
        )

        plan = fact_retrieval_plan(session)

        self.assertEqual(plan[0]["key"], "repair-issues")
        self.assertGreaterEqual(len(plan[0]["patterns"]), 3)
        self.assertIn("mold", plan[0]["terms"])

    def test_recommendation_creates_selects_and_returns_document_facts_without_duplicates(self):
        creation = self._create_session().json()
        session_id = creation["session"]["id"]
        self.assertEqual(MatterFact.objects.filter(matter=self.matter).count(), 0)

        first = self.client.post(
            f"/api/drafting-sessions/{session_id}/recommend-facts/",
            data=json.dumps({"apply": True}),
            content_type="application/json",
        )

        self.assertEqual(first.status_code, 200)
        payload = first.json()
        self.assertEqual({"factIds", "facts", "case", "session"} - set(payload), set())
        self.assertTrue(payload["factIds"])
        self.assertEqual(payload["factIds"], payload["session"]["selectedFactIds"])
        self.assertEqual(payload["case"]["id"], self.matter.external_id)
        self.assertEqual({fact["id"] for fact in payload["facts"]}, set(payload["factIds"]))
        self.assertEqual({fact["id"] for fact in payload["case"]["facts"]}, set(payload["factIds"]))
        derived = MatterFact.objects.get(id=payload["factIds"][0])
        self.assertEqual(derived.confidence, "ai_document_search")
        self.assertTrue(derived.ai_suggested)
        self.assertIn("excerpt", derived.source_label)
        count_after_first = MatterFact.objects.filter(matter=self.matter).count()

        second = self.client.post(
            f"/api/drafting-sessions/{session_id}/recommend-facts/",
            data=json.dumps({"apply": True}),
            content_type="application/json",
        )

        self.assertEqual(second.status_code, 200)
        self.assertEqual(MatterFact.objects.filter(matter=self.matter).count(), count_after_first)
        self.assertEqual(second.json()["factIds"], payload["factIds"])
