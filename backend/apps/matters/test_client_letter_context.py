from django.test import TestCase

from apps.matters.client_letter_context import (
    case_reference,
    client_letter_context,
    format_address,
    letter_template_fields,
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

    def test_a_filing_category_is_not_printed_verbatim(self):
        """"help with your private landlord/tenant" is what this prevents."""
        bare = Matter(external_id="LS-3", client_name="X", matter_type="", jurisdiction="")
        payload = {"legal_problem_code": "62 Private Landlord/Tenant"}

        self.assertEqual(matter_subject(bare, payload), "housing matter")

    def test_an_eviction_case_is_named_plainly(self):
        payload = {**PAYLOAD, "legal_problem_code": "06 Eviction / Ejectment"}

        self.assertEqual(matter_subject(self.matter, payload), "eviction")

    def test_a_forcible_entry_and_detainer_case_is_an_eviction(self):
        bare = Matter(external_id="LS-4", client_name="X", matter_type="", jurisdiction="")

        self.assertEqual(
            matter_subject(bare, {"legal_problem_code": "Forcible Entry and Detainer"}), "eviction"
        )

    def test_a_case_with_no_problem_code_falls_back_to_the_matter_type(self):
        self.assertEqual(matter_subject(self.matter, {}), "eviction")

    def test_a_non_housing_case_says_legal_matter(self):
        bare = Matter(external_id="LS-5", client_name="X", matter_type="", jurisdiction="")

        self.assertEqual(
            matter_subject(bare, {"legal_problem_code": "01 Bankruptcy/Debtor Relief"}),
            "legal matter",
        )

    def test_a_case_with_nothing_recorded_still_completes_the_sentence(self):
        bare = Matter(external_id="LS-2", client_name="X", matter_type="", jurisdiction="")

        self.assertEqual(matter_subject(bare, {}), "legal matter")

    def test_the_re_line_names_the_case_and_court(self):
        reference = case_reference(self.matter, PAYLOAD)

        self.assertIn("Case No. 14-0000005", reference)
        self.assertIn("Cleveland Municipal Court", reference)

    def test_a_name_is_never_re_cased(self):
        """Restyling a name mangles the ones that are deliberately unusual."""
        for name in ("TEST TEST", "maria alvarez", "DeCarlo", "McDONALD", "van der Berg", "O'Brien"):
            self.assertEqual(salutation_name(name), name)

    def test_only_stray_whitespace_is_tidied(self):
        self.assertEqual(salutation_name("  Maria   Alvarez \n"), "Maria Alvarez")
        self.assertEqual(salutation_name(""), "")

    def test_letter_template_fields_use_named_legalserver_fields_only(self):
        self.matter.raw_payload = {
            **PAYLOAD,
            "custom_fields": {
                "Plaintiff Name": "Example Homes LLC",
                "Filing Date": "July 12, 2026",
                "Magistrate Name": "Alex Judge",
            },
        }

        fields, sources = letter_template_fields(self.matter)

        self.assertEqual(fields["plaintiff_name"], "Example Homes LLC")
        self.assertEqual(fields["filing_date"], "July 12, 2026")
        self.assertEqual(fields["magistrate"], "Alex Judge")
        self.assertEqual(sources["filing_date"], "LegalServer field: Filing Date")

    def test_letter_template_fields_leave_unknown_facts_out(self):
        fields, _sources = letter_template_fields(self.matter)

        self.assertNotIn("filing_date", fields)
        self.assertNotIn("plaintiff_name", fields)
