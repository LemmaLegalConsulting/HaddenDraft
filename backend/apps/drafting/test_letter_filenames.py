from datetime import date

from django.test import TestCase

from apps.drafting.letter_filenames import (
    client_slug,
    letter_filename,
    section_slug,
    sections_slug,
)


class ClientSlugTests(TestCase):
    def test_the_surname_leads_so_a_clients_letters_sort_together(self):
        self.assertEqual(client_slug("Robert Garcia"), "garcia-robert")

    def test_a_middle_name_stays_with_the_given_names(self):
        self.assertEqual(client_slug("Maria de la Cruz"), "cruz-maria-de-la")

    def test_an_already_inverted_name_is_not_inverted_again(self):
        self.assertEqual(client_slug("Garcia, Robert"), "garcia-robert")

    def test_a_single_name_is_used_as_is(self):
        self.assertEqual(client_slug("Prince"), "prince")

    def test_an_honorific_is_not_treated_as_the_surname(self):
        self.assertEqual(client_slug("Ms. Alvarez"), "alvarez")
        self.assertEqual(client_slug("Dr. Maria Alvarez"), "alvarez-maria")

    def test_a_missing_name_is_empty_rather_than_a_placeholder(self):
        self.assertEqual(client_slug(""), "")


class SectionSlugTests(TestCase):
    def test_region_and_draft_markers_are_dropped(self):
        self.assertEqual(section_slug("Motion to Seal (Cle)"), "motion-seal")
        self.assertEqual(section_slug("Rent Depositing - NEO - DRAFT"), "rent-depositing")

    def test_only_the_first_few_sections_are_named(self):
        titles = ["Security Deposit", "Nonpayment of Rent", "Getting Zoom Info", "Objections"]

        self.assertEqual(
            sections_slug(titles, limit=3), "security-deposit-nonpayment-rent-getting-zoom-info"
        )

    def test_repeated_sections_are_not_repeated_in_the_name(self):
        self.assertEqual(sections_slug(["Security Deposit", "Security Deposit"]), "security-deposit")


class LetterFilenameTests(TestCase):
    def test_the_default_names_the_date_client_and_sections(self):
        name = letter_filename(
            client_name="Robert Garcia",
            section_titles=["Security Deposit", "Nonpayment of Rent"],
            letter_date=date(2026, 8, 2),
        )

        self.assertEqual(
            name, "2026-08-02-garcia-robert-advice-letter-security-deposit-nonpayment-rent.docx"
        )

    def test_a_missing_client_does_not_leave_a_run_of_hyphens(self):
        name = letter_filename(
            client_name="", section_titles=["Security Deposit"], letter_date=date(2026, 8, 2)
        )

        self.assertEqual(name, "2026-08-02-advice-letter-security-deposit.docx")
        self.assertNotIn("--", name)

    def test_an_organization_can_file_by_case_number_instead(self):
        name = letter_filename(
            pattern="{case}-{date}-{kind}",
            case_number="2026 CVG 011123",
            letter_date=date(2026, 8, 2),
        )

        self.assertEqual(name, "2026-cvg-011123-2026-08-02-advice-letter.docx")

    def test_an_unknown_placeholder_costs_a_hyphen_not_the_download(self):
        """The pattern is organization-editable, so a typo must not raise."""
        name = letter_filename(
            pattern="{date}-{nonsense}-{client}",
            client_name="Robert Garcia",
            letter_date=date(2026, 8, 2),
        )

        self.assertEqual(name, "2026-08-02-garcia-robert.docx")

    def test_a_long_name_is_cut_on_a_word_boundary(self):
        name = letter_filename(
            client_name="Robert Garcia",
            section_titles=[
                "Denied for Subsidized Housing - Deadline to Appeal Has Passed",
                "Asking the Court to Undo an Eviction Judgment",
                "What Happens at the Hearing and After",
            ],
            letter_date=date(2026, 8, 2),
        )

        self.assertLessEqual(len(name), 130)
        self.assertFalse(name.startswith("-"))
        self.assertNotIn("--", name)

    def test_the_section_limit_is_configurable(self):
        titles = ["Security Deposit", "Nonpayment of Rent", "Objections"]

        self.assertEqual(
            letter_filename(client_name="A B", section_titles=titles, section_limit=1,
                            letter_date=date(2026, 8, 2)),
            "2026-08-02-b-a-advice-letter-security-deposit.docx",
        )
