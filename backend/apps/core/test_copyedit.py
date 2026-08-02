from django.test import TestCase

from apps.validation.copyedit import copyedit_line, copyedit_lines


class MechanicalFixTests(TestCase):
    """Whitespace and punctuation damage is repaired without asking."""

    def test_non_breaking_spaces_become_ordinary_spaces(self):
        result = copyedit_line("Your landlord has thirty (30) days after you move out.")

        self.assertNotIn(" ", result.text)
        self.assertIn("(30) days after you", result.text)
        self.assertEqual(result.fixes[0]["kind"], "non_breaking_space")

    def test_double_spaces_collapse(self):
        result = copyedit_line("Issue with the notice.  There is a problem.")

        self.assertIn("notice. There is", result.text)

    def test_space_before_punctuation_is_removed(self):
        result = copyedit_line("Call the court , then call us .")

        self.assertIn("court, then", result.text)
        self.assertTrue(result.text.endswith("us."))

    def test_missing_space_after_a_comma_is_added(self):
        result = copyedit_line("Bring your lease,receipts and photos.")

        self.assertIn("lease, receipts", result.text)

    def test_missing_space_after_a_sentence_period_is_added(self):
        result = copyedit_line("Go to the hearing.Bring your papers.")

        self.assertIn("hearing. Bring", result.text)

    def test_legal_citations_are_not_broken_apart(self):
        """"R.C. 5321.04" must survive the missing-space repair."""
        for citation in (
            "This is required by R.C. 5321.04 and Civ.R. 5(B)(4).",
            "See 24 C.F.R. 247.4(a)(2) for the rule.",
            "Ask Mr. Smith about the notice.",
        ):
            result = copyedit_line(citation)
            self.assertEqual(result.text, citation, citation)

    def test_wording_is_never_changed(self):
        original = "You can ask the Court to seal the record of this case."

        self.assertEqual(copyedit_line(original).text, original)


class JudgementFlagTests(TestCase):
    """Anything needing a decision is reported, not silently changed."""

    def test_a_merge_boundary_is_flagged_for_a_human(self):
        result = copyedit_line(
            "explain why they are not all the deposit to you", touched_by_edit=True
        )

        self.assertEqual([flag["kind"] for flag in result.flags], ["merge_boundary"])
        # The broken wording is left exactly as the editor left it.
        self.assertIn("not all the deposit", result.text)

    def test_prose_missing_its_final_period_is_flagged(self):
        result = copyedit_line(
            "You must give your landlord a mailing address where they can reach you"
        )

        self.assertIn("missing_terminal_punctuation", [flag["kind"] for flag in result.flags])

    def test_a_list_item_is_not_expected_to_end_in_a_period(self):
        result = copyedit_line("- Receipts for your security deposit or rent payments")

        self.assertEqual(result.flags, [])

    def test_a_run_in_heading_is_not_expected_to_end_in_a_period(self):
        result = copyedit_line("If the Court Does NOT Grant a Continuance")

        self.assertEqual(result.flags, [])

    def test_a_doubled_word_is_flagged(self):
        result = copyedit_line("You must must go to the hearing on time please.")

        self.assertIn("doubled_word", [flag["kind"] for flag in result.flags])


class SectionLevelTests(TestCase):
    def test_a_quotation_spanning_lines_is_not_reported_as_unbalanced(self):
        """A courtroom script opens on one line and closes several later."""
        lines = [
            "When the judge calls your case, say:",
            "“The 3-Day Notice is from one company.",
            "But the Complaint was filed by another.",
            "Please dismiss this eviction.”",
        ]

        _text, report = copyedit_lines(lines)

        self.assertEqual([flag["kind"] for flag in report.flags], [])

    def test_a_genuinely_unbalanced_quote_is_reported(self):
        _text, report = copyedit_lines(["“The notice is not conspicuous.", "Ask for dismissal."])

        self.assertIn("unbalanced_marks", [flag["kind"] for flag in report.flags])

    def test_parenthesised_numbers_are_not_read_as_enumerations(self):
        """"(216) 664-4295" and "one (1) day" are balanced, not stray brackets."""
        _text, report = copyedit_lines(
            ["Call them at (216) 664-4295 at least one (1) day before the hearing."]
        )

        self.assertEqual([flag["kind"] for flag in report.flags], [])

    def test_enumerations_in_prose_are_not_read_as_brackets(self):
        _text, report = copyedit_lines(
            ["You may want to 1) complain to the City or 2) start a rent deposit."]
        )

        self.assertEqual([flag["kind"] for flag in report.flags], [])

    def test_only_the_edited_paragraph_is_flagged(self):
        _text, report = copyedit_lines(
            ["Untouched paragraph here.", "Edited paragraph here."], touched={1}
        )

        merge_flags = [flag for flag in report.flags if flag["kind"] == "merge_boundary"]
        self.assertEqual(len(merge_flags), 1)
        self.assertIn("Edited paragraph", merge_flags[0]["excerpt"])
