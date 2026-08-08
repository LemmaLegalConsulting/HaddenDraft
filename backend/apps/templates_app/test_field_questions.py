from django.test import TestCase

from apps.templates_app.field_questions import (
    KIND_NARRATIVE,
    KIND_UNUSABLE,
    KIND_VALUE,
    field_keys_for_answer,
    template_field_requests,
)
from apps.templates_app.models import DocumentTemplate, TemplateBlock
from apps.templates_app.template_variables import template_field_values


class TemplateFieldRequestTests(TestCase):
    def setUp(self):
        self.template = DocumentTemplate.objects.create(
            slug="emergency-motion-for-heat",
            title="Emergency Motion for Heat",
            kind="motion",
            metadata={"fields": ["fields.landlord", "fields.see_exhibit_x_defendant"]},
        )
        TemplateBlock.objects.create(
            template=self.template,
            key="relevant-facts",
            label="Relevant Facts",
            block_type="facts",
            order=10,
            ai_fill_mode="revision_on_request",
            ai_instructions=["describe occupants", "how, when?"],
            body=(
                "Defendant has lived in the premises with {{ fields.describe_occupants }} "
                "since {{ fields.move_in_date }}. Defendant has not had adequate heat, "
                "which Defendant discovered {{ fields.how_when }}."
            ),
        )
        TemplateBlock.objects.create(
            template=self.template,
            key="signature",
            label="Signature",
            block_type="signature",
            order=20,
            body="Respectfully submitted,\n{{ fields.law_argument_32_blank }}\nAttorney for Defendant",
        )

    def requests_by_key(self):
        return {request.key: request for request in template_field_requests(self.template)}

    def test_drafting_instruction_becomes_a_direction_not_a_question(self):
        request = self.requests_by_key()["describe_occupants"]

        self.assertEqual(request.kind, KIND_NARRATIVE)
        self.assertEqual(request.question, "Describe occupants.")
        self.assertNotIn("What is the", request.question)

    def test_instruction_punctuation_survives_the_field_name(self):
        request = self.requests_by_key()["how_when"]

        self.assertEqual(request.kind, KIND_NARRATIVE)
        self.assertEqual(request.question, "How, when?")

    def test_case_fact_keeps_a_question_and_its_template_sentence(self):
        request = self.requests_by_key()["move_in_date"]

        self.assertEqual(request.kind, KIND_VALUE)
        self.assertEqual(request.question, "When did the client move into the premises?")
        self.assertIn("Defendant has lived in the premises with", request.context)
        self.assertIn("____", request.context)

    def test_conversion_debris_is_never_asked_about(self):
        requests = self.requests_by_key()

        self.assertEqual(requests["law_argument_32_blank"].kind, KIND_UNUSABLE)
        self.assertEqual(requests["see_exhibit_x_defendant"].kind, KIND_UNUSABLE)

    def test_two_bindings_of_one_fact_are_asked_once(self):
        keys = list(self.requests_by_key())

        self.assertIn("plaintiff_name", keys)
        self.assertNotIn("landlord", keys)
        self.assertEqual(field_keys_for_answer("landlord"), ["plaintiff_name", "landlord", "landlord_name", "plaintiff"])

    def test_neighbouring_bindings_read_as_values_in_the_context(self):
        request = self.requests_by_key()["describe_occupants"]

        self.assertIn("[Move In Date]", request.context)


class UnusableFieldRenderingTests(TestCase):
    def test_debris_renders_as_a_blank_line_not_a_field_name(self):
        values = template_field_values({})

        self.assertEqual(values["law_argument_32_blank"], "__________")
        self.assertEqual(values["placeholder_14_blank_1"], "__________")
        self.assertEqual(values["hearing_date"], "[Hearing Date]")
