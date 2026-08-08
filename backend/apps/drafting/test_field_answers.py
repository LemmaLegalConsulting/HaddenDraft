import json

from django.test import TestCase
from django.test.utils import override_settings

from apps.drafting.field_answers import resolve_field_requests
from apps.drafting.models import DraftingSession
from apps.drafting.services import create_or_update_plan
from apps.matters.models import Matter, MatterFact
from apps.templates_app.field_questions import template_field_requests
from apps.templates_app.models import DocumentTemplate, TemplateBlock


class StubClient:
    """Stands in for the model, recording what it was asked."""

    def __init__(self, payload):
        self.payload = payload
        self.prompts = []

    def complete(self, *, system, user, model=None, reasoning_level=None, **kwargs):
        self.prompts.append(user)
        return json.dumps(self.payload)


def build_case():
    matter = Matter.objects.create(
        external_id="CASE-FIELD-ANSWERS",
        client_name="Jane Tenant",
        matter_type="Eviction",
        jurisdiction="Cleveland Housing Court",
        summary="No heat since the furnace failed.",
    )
    MatterFact.objects.create(
        matter=matter,
        slug="intake-notes",
        title="Intake notes",
        text="Jane rents 1234 Euclid Ave., Apt. 3, Cleveland, OH 44115 and lives there with her two children.",
        source_label="Typed intake notes",
    )
    template = DocumentTemplate.objects.create(
        slug="heat-motion", title="Emergency Motion for Heat", kind="motion"
    )
    TemplateBlock.objects.create(
        template=template,
        key="facts",
        label="Relevant Facts",
        block_type="facts",
        order=10,
        ai_fill_mode="revision_on_request",
        ai_instructions=["describe occupants"],
        body=(
            "Defendant lives at {{ fields.premises_address }} with "
            "{{ fields.describe_occupants }}. The hearing is set for "
            "{{ fields.hearing_date }}."
        ),
    )
    session = DraftingSession.objects.create(
        mode="draft_from_template",
        matter=matter,
        template=template,
        selected_template_ids=[template.id],
    )
    return matter, template, session


class ResolveFieldRequestTests(TestCase):
    def test_record_answers_are_returned_with_their_basis(self):
        _matter, template, session = build_case()
        client = StubClient(
            {
                "fields": [
                    {
                        "key": "premises_address",
                        "answered_from_record": True,
                        "value": "1234 Euclid Ave., Apt. 3, Cleveland, OH 44115",
                        "basis": "Intake notes give the rental address",
                    },
                    {
                        "key": "hearing_date",
                        "answered_from_record": False,
                        "value": "",
                        "question": "What date is the first cause hearing set for?",
                    },
                ]
            }
        )

        resolved = resolve_field_requests(
            session,
            template,
            template_field_requests(template),
            facts=list(session.matter.facts.all()),
            client=client,
        )

        self.assertEqual(resolved["premises_address"]["value"], "1234 Euclid Ave., Apt. 3, Cleveland, OH 44115")
        self.assertEqual(resolved["premises_address"]["basis"], "Intake notes give the rental address")
        self.assertEqual(resolved["hearing_date"]["value"], "")
        self.assertEqual(resolved["hearing_date"]["question"], "What date is the first cause hearing set for?")

    def test_a_value_without_a_record_answer_is_not_kept(self):
        _matter, template, session = build_case()
        client = StubClient(
            {
                "fields": [
                    {
                        "key": "hearing_date",
                        "answered_from_record": False,
                        "value": "August 1, 2026",
                        "question": "What date is the hearing?",
                    }
                ]
            }
        )

        resolved = resolve_field_requests(
            session,
            template,
            template_field_requests(template),
            facts=list(session.matter.facts.all()),
            client=client,
        )

        self.assertEqual(resolved["hearing_date"]["value"], "")

    def test_the_model_sees_the_template_sentence_around_each_blank(self):
        _matter, template, session = build_case()
        client = StubClient({"fields": []})

        resolve_field_requests(
            session,
            template,
            template_field_requests(template),
            facts=list(session.matter.facts.all()),
            client=client,
        )

        prompt = client.prompts[0]
        self.assertIn("kind: narrative", prompt)
        self.assertIn("Defendant lives at ____", prompt)
        self.assertIn("Jane rents 1234 Euclid Ave.", prompt)

    def test_a_disabled_model_leaves_the_template_questions_alone(self):
        _matter, template, session = build_case()

        resolved = resolve_field_requests(
            session,
            template,
            template_field_requests(template),
            facts=list(session.matter.facts.all()),
            client=StubClient({"fields": [{"key": "hearing_date", "value": "nope"}]}),
            enabled=False,
        )

        self.assertEqual(resolved, {})


@override_settings(AI_DRAFTING_ENABLED=False)
class PlanQuestionShapeTests(TestCase):
    def test_plan_questions_separate_drafting_directions_from_facts(self):
        _matter, template, session = build_case()

        session = create_or_update_plan(session, {"selectedTemplateIds": [template.id]})
        questions = {item["field"]: item for item in session.missing_information if item["field"].startswith("fields.")}

        self.assertTrue(questions["fields.describe_occupants"]["ai_completable"])
        self.assertEqual(questions["fields.describe_occupants"]["question"], "Describe occupants.")
        self.assertFalse(questions["fields.hearing_date"]["ai_completable"])
        self.assertIn("____", questions["fields.hearing_date"]["context"])
