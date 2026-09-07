"""Form-of-pleading checks: the things a reader can verify by looking."""

from django.test import TestCase

from apps.validation.pleading_form import check_pleading_form


ANSWER = """
IN THE TEST COURT
Case No. CV-24-1

ANSWER

1. Defendant admits the allegation in paragraph 1.
2. Defendant denies the allegation in paragraph 2.
3. Defendant lacks knowledge sufficient to answer paragraph 3.

WHEREFORE, Defendant respectfully requests that the complaint be dismissed.

Respectfully submitted,
Jane Advocate
June 1, 2026
"""


def codes(findings):
    return [finding["ruleCode"] for finding in findings]


def targets(findings):
    return [finding["target"] for finding in findings]


class PleadingFormTests(TestCase):
    def test_signature_lines_are_exempt_only_with_local_signature_context(self):
        for text in ("Respectfully submitted,________", "Respectfully submitted,\n\n________\nJane Advocate",
                     "________\nAttorney for Respondent", "________\nAlex Example (1234567)"):
            with self.subTest(text=text):
                self.assertNotIn("E1040", codes(check_pleading_form(text)))
        for text in ("Monthly rent is ________.", "Date: ________", "Name: ________",
                     "Respectfully submitted,\nJane Advocate\n\nRent: ________"):
            with self.subTest(text=text):
                self.assertIn("E1040", codes(check_pleading_form(text)))

    def test_bracketed_quotations_are_distinct_from_author_instructions(self):
        self.assertNotIn("E1040", codes(check_pleading_form('The witness said "[We were] at home."')))
        for marker in ("[NAME OF ORDINANCE]", "[Add this section]", "[INSERT DATE]", "[ADD]", "[EXAMPLES]"):
            self.assertIn("E1040", codes(check_pleading_form(marker)))

    def test_relief_can_be_requested_without_the_word_respectfully(self):
        for text in ("Plaintiff seeks partial summary judgment.", "Defendant moves this Court to dismiss.",
                     "Petitioner requests an injunction."):
            self.assertNotIn("prayer_for_relief", targets(check_pleading_form(text, pleading_type="motion")))
        self.assertIn("prayer_for_relief", targets(check_pleading_form("Judgment was entered last year.", pleading_type="motion")))

    def test_a_conventional_answer_produces_no_findings(self):
        self.assertEqual(check_pleading_form(ANSWER, pleading_type="answer", document_id=1), [])

    def test_an_answer_without_numbered_paragraphs_is_flagged(self):
        text = ANSWER.replace("1. Defendant", "Defendant").replace("2. Defendant", "Defendant").replace(
            "3. Defendant", "Defendant"
        )
        findings = check_pleading_form(text, pleading_type="answer", document_id=1)
        self.assertIn("numbered paragraphs", targets(findings))

    def test_numbering_that_skips_is_reported_with_both_numbers(self):
        text = ANSWER.replace("3. Defendant", "7. Defendant")
        findings = check_pleading_form(text, pleading_type="answer", document_id=1)
        message = " ".join(finding["message"] for finding in findings)
        self.assertIn("jumps from 2 to 7", message)

    def test_numbering_that_restarts_is_a_new_count_not_a_gap(self):
        text = ANSWER + "\n\nFIRST AFFIRMATIVE DEFENSE\n\n1. The notice was defective.\n2. Service was improper.\n"
        findings = check_pleading_form(text, pleading_type="answer", document_id=1)
        self.assertEqual(findings, [])

    def test_a_filing_that_asks_for_nothing_is_flagged(self):
        text = ANSWER.replace("WHEREFORE, Defendant respectfully requests that the complaint be dismissed.", "")
        self.assertIn("prayer_for_relief", targets(check_pleading_form(text, pleading_type="answer", document_id=1)))

    def test_an_unsigned_filing_is_flagged(self):
        text = ANSWER.replace("Respectfully submitted,", "")
        self.assertIn("signature_block", targets(check_pleading_form(text, pleading_type="answer", document_id=1)))

    def test_a_placeholder_left_in_the_text_is_an_error(self):
        text = ANSWER.replace("Jane Advocate", "[ATTORNEY NAME]")
        findings = check_pleading_form(text, pleading_type="answer", document_id=1)
        self.assertIn("E1040", codes(findings))
        self.assertIn("[ATTORNEY NAME]", " ".join(finding["message"] for finding in findings))

    def test_a_blank_line_placeholder_is_caught_too(self):
        text = ANSWER + "\nMonthly rent: ________"
        self.assertIn("E1040", codes(check_pleading_form(text, pleading_type="answer", document_id=1)))

    def test_an_exhibit_referred_to_but_not_attached_is_reported(self):
        text = ANSWER + "\n\nSee Exhibit B, the rent ledger."
        findings = check_pleading_form(
            text, pleading_type="answer", document_id=1, attached_labels=["Exhibit A"]
        )
        self.assertIn("Exhibit B", " ".join(finding["message"] for finding in findings))

    def test_an_exhibit_that_is_attached_is_not_reported(self):
        text = ANSWER + "\n\nSee Exhibit A, the lease."
        findings = check_pleading_form(
            text, pleading_type="answer", document_id=1, attached_labels=["Exhibit A"]
        )
        self.assertEqual(findings, [])

    def test_nothing_attached_means_references_are_not_checked_rather_than_all_failed(self):
        text = ANSWER + "\n\nSee Exhibit A and Exhibit B."
        findings = check_pleading_form(text, pleading_type="answer", document_id=1, attached_labels=[])
        self.assertNotIn("exhibit references", targets(findings))

    def test_a_check_scoped_to_another_pleading_type_does_not_run(self):
        # A motion is not pleaded in numbered paragraphs.
        findings = check_pleading_form(
            "MOTION TO DISMISS\n\nThe notice was defective.\n\nWHEREFORE, Defendant respectfully requests dismissal.\n\nRespectfully submitted,",
            pleading_type="motion",
            document_id=1,
        )
        self.assertNotIn("numbered paragraphs", targets(findings))
