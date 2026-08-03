from django.test import TestCase

from apps.matters.client_letter_context import (
    case_reference,
    client_letter_context,
    format_address,
    matter_subject,
    salutation_name,
)
from apps.matters.models import Matter


# Shaped after a live LegalServer /api/v2/matters record.
PAYLOAD = {
    "client_full_name": "TEST TEST",
    "client_email_address": "training@legalserver.org",
    "case_number": "14-0000005",
    "legal_problem_code": "01 Bankruptcy/Debtor Relief",
    "client_address_home": {
        "street": "667 Broadway",
        "street_2": None,
        "apt_num": None,
        "city": "New York",
        "state": "NY",
        "zip": "10001",
    },
    "client_address_mailing": {"street": None, "city": None, "state": None, "zip": None},
}


class ClientLetterContextTests(TestCase):
    def setUp(self):
        self.matter = Matter.objects.create(
            external_id="LS-1",
            client_name="TEST TEST",
            matter_type="Eviction",
            jurisdiction="Cleveland Municipal Court",
            raw_payload=PAYLOAD,
        )

    def test_addressing_comes_from_the_case(self):
        """A letter greeting "[Client]" was the bug this prevents."""
        context = client_letter_context(self.matter)

        self.assertEqual(context["recipientName"], "TEST TEST")
        self.assertEqual(context["recipientAddress"], "667 Broadway\nNew York, NY 10001")
        self.assertEqual(context["recipientEmail"], "training@legalserver.org")
        self.assertEqual(context["caseNumber"], "14-0000005")

    def test_an_empty_mailing_address_falls_back_to_the_home_address(self):
        self.assertIn("667 Broadway", client_letter_context(self.matter)["recipientAddress"])

    def test_a_mailing_address_wins_when_present(self):
        self.matter.raw_payload = {
            **PAYLOAD,
            "client_address_mailing": {"street": "PO Box 5", "city": "Cleveland", "state": "OH", "zip": "44113"},
        }

        self.assertIn("PO Box 5", client_letter_context(self.matter)["recipientAddress"])

    def test_an_apartment_number_joins_the_street_line(self):
        formatted = format_address(
            {"street": "123 Main St", "apt_num": "Apt 4", "city": "Cleveland", "state": "OH", "zip": "44113"}
        )

        self.assertEqual(formatted, "123 Main St Apt 4\nCleveland, OH 44113")

    def test_a_missing_address_is_empty_rather_than_guessed(self):
        self.matter.raw_payload = {"client_full_name": "Jane Tenant"}

        self.assertEqual(client_letter_context(self.matter)["recipientAddress"], "")

    def test_the_subject_reads_as_a_sentence_fragment(self):
        """It lands mid-sentence: "help with your ___"."""
        self.assertEqual(matter_subject(self.matter, PAYLOAD), "bankruptcy/debtor relief")

    def test_an_eviction_case_is_named_plainly(self):
        payload = {**PAYLOAD, "legal_problem_code": "06 Eviction / Ejectment"}

        self.assertEqual(matter_subject(self.matter, payload), "eviction")

    def test_a_case_with_no_problem_code_falls_back_to_the_matter_type(self):
        self.assertEqual(matter_subject(self.matter, {}), "eviction")

    def test_a_case_with_nothing_recorded_says_housing_issue(self):
        bare = Matter(external_id="LS-2", client_name="X", matter_type="", jurisdiction="")

        self.assertEqual(matter_subject(bare, {}), "housing issue")

    def test_the_re_line_names_the_case_and_court(self):
        reference = case_reference(self.matter, PAYLOAD)

        self.assertIn("Case No. 14-0000005", reference)
        self.assertIn("Cleveland Municipal Court", reference)

    def test_a_shouted_name_is_title_cased_for_the_salutation(self):
        self.assertEqual(salutation_name("TEST TEST"), "Test Test")
        self.assertEqual(salutation_name("maria alvarez"), "Maria Alvarez")

    def test_a_correctly_cased_name_is_left_alone(self):
        self.assertEqual(salutation_name("Maria de la Cruz"), "Maria de la Cruz")
