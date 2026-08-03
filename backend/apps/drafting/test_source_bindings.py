from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings

from apps.ai.services import drafting_ai
from apps.drafting.models import DraftingSession
from apps.drafting.services import create_draft, regenerate_draft_block
from apps.drafting.source_bindings import classify_source_result
from apps.matters.models import Matter, MatterFact
from apps.templates_app.models import DocumentTemplate, TemplateBlock
from apps.validation.services import validate_document


LEGAL_AUTHORITY = {
    "id": "ohio-rc-1923",
    "title": "Ohio Rev. Code 1923.04",
    "citation": "R.C. 1923.04",
    "snippet": "Notice to leave the premises must be served three days before filing.",
    "sourceKind": "rag",
    "purpose": "legal_authority",
}
EXAMPLE_BRIEF = {
    "id": "prior-answer-2019",
    "title": "Answer filed in a prior eviction case",
    "snippet": "The tenant denies each allegation of the complaint.",
    "sourceKind": "sharepoint",
    "purpose": "example_language",
}


@override_settings(AI_DRAFTING_ENABLED=False, ENABLE_DEMO_MATTERS=True)
class SourceBindingTests(TestCase):
    """Sources are bound to the component that used them, typed by what they support."""

    def setUp(self):
        self.matter = Matter.objects.create(
            external_id="LS-BINDINGS",
            client_name="Jane Tenant",
            matter_type="Eviction",
            jurisdiction="Cleveland Housing Court",
            summary="Tenant disputes the notice.",
            source_system="Demo",
        )
        self.fact = MatterFact.objects.create(
            matter=self.matter,
            slug="notice-defect",
            title="Notice served late",
            text="The three-day notice was served the same day the case was filed.",
            source_label="LegalServer",
        )
        self.template = DocumentTemplate.objects.create(
            title="Answer and Counterclaims",
            slug="answer-bindings-test",
            kind="answer_counterclaims",
        )
        TemplateBlock.objects.create(
            template=self.template,
            key="facts",
            label="Statement of facts",
            block_type="facts",
            order=10,
            body="",
            required=True,
        )
        TemplateBlock.objects.create(
            template=self.template,
            key="notice-defense",
            label="Notice defense",
            block_type="argument",
            order=20,
            body="The notice was defective and the case must be dismissed.",
            required=True,
            ai_fill_mode="constrained_generation",
        )
        self.session = DraftingSession.objects.create(
            mode="draft_from_template",
            matter=self.matter,
            template=self.template,
            selected_fact_ids=[self.fact.id],
            selected_block_keys=["facts", "notice-defense"],
            selected_source_results=[LEGAL_AUTHORITY],
        )

    def _bindings(self, draft, key):
        return list(draft.components.get(stable_key=key).current_version.source_bindings.all())

    def test_purpose_and_source_kind_decide_what_a_source_can_support(self):
        self.assertEqual(classify_source_result(LEGAL_AUTHORITY), ("legal_authority", "direct"))
        self.assertEqual(classify_source_result(EXAMPLE_BRIEF), ("example_language", "style_only"))
        self.assertEqual(
            classify_source_result({"title": "Local rule 4", "sourceKind": "court_rules"}),
            ("procedural_rule", "direct"),
        )
        self.assertEqual(
            classify_source_result({"title": "Intake summary", "sourceKind": "sharepoint"}),
            ("background_reference", "background"),
        )

    def test_facts_sections_bind_the_record_and_argument_sections_bind_authority(self):
        draft = create_draft(self.session)

        facts_binding = self._bindings(draft, "facts")[0]
        self.assertEqual(facts_binding.role, "record_evidence")
        self.assertEqual(facts_binding.support_type, "direct")
        self.assertEqual(facts_binding.locator["factId"], self.fact.id)

        authority = self._bindings(draft, "notice-defense")[0]
        self.assertEqual(authority.role, "legal_authority")
        self.assertEqual(authority.citation, "R.C. 1923.04")
        self.assertEqual(authority.source_kind, "rag")

    def test_a_regenerated_component_binds_sources_to_its_new_version(self):
        draft = create_draft(self.session)

        with patch.object(drafting_ai, "regenerate_section", return_value="Rewritten notice defense."):
            regenerate_draft_block(draft, "notice-defense", "Add the service date.")

        component = draft.components.get(stable_key="notice-defense")
        versions = list(component.versions.order_by("sequence"))
        self.assertEqual(len(versions), 2)
        self.assertTrue(all(version.source_bindings.exists() for version in versions))

    def test_bindings_are_not_duplicated_when_generation_runs_again(self):
        draft = create_draft(self.session)
        before = len(self._bindings(draft, "notice-defense"))

        create_draft(self.session, template=self.template)

        self.assertEqual(len(self._bindings(draft, "notice-defense")), before)

    def test_example_language_alone_is_flagged_as_support_for_a_legal_assertion(self):
        self.session.selected_source_results = [EXAMPLE_BRIEF]
        self.session.save(update_fields=["selected_source_results"])
        draft = create_draft(self.session)

        findings = validate_document(draft, include_docx=False)

        example_findings = [finding for finding in findings if finding["ruleCode"] == "W700"]
        self.assertEqual(len(example_findings), 1)
        self.assertEqual(example_findings[0]["location"]["blockKey"], "notice-defense")
        self.assertIn("not authority", example_findings[0]["message"])

    def test_legal_authority_support_clears_the_source_integrity_rules(self):
        draft = create_draft(self.session)

        findings = validate_document(draft, include_docx=False)

        self.assertEqual([finding for finding in findings if finding["category"] == "source_integrity"], [])

    def test_an_unsupported_legal_assertion_is_flagged_when_nothing_is_bound(self):
        self.session.selected_source_results = []
        self.session.save(update_fields=["selected_source_results"])
        draft = create_draft(self.session)

        findings = validate_document(draft, include_docx=False)

        self.assertEqual(
            [finding["location"]["blockKey"] for finding in findings if finding["ruleCode"] == "W710"],
            ["notice-defense"],
        )
