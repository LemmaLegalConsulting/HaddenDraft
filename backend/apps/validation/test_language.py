"""Grammar, confused words, and passive voice -- and what they refuse to flag."""

from django.test import TestCase

from apps.validation.language import check_language


def messages(findings):
    return " ".join(finding["message"] for finding in findings)


def codes(findings):
    return [finding["ruleCode"] for finding in findings]


class ConfusedWordTests(TestCase):
    def test_a_word_legal_writing_gets_wrong_is_corrected(self):
        findings = check_language("The court entered judgement for the plaintiff.", include=("confused_words",))
        self.assertIn("W1100", codes(findings))
        self.assertIn('"judgment"', messages(findings))

    def test_the_correct_spelling_is_not_flagged(self):
        self.assertEqual(check_language("The court entered judgment.", include=("confused_words",)), [])

    def test_a_repeated_typo_is_one_correction_not_many(self):
        findings = check_language("judgement, judgement, judgement", include=("confused_words",))
        self.assertEqual(len(findings), 1)

    def test_legal_terms_of_art_are_never_flagged(self):
        text = (
            "Plaintiff seeks replevin and forcible entry and detainer relief, and pleads estoppel, "
            "laches, res judicata, and a writ of restitution under the escrow statute."
        )
        self.assertEqual(check_language(text, include=("confused_words", "confusable_pairs")), [])

    def test_two_easily_confused_words_together_are_raised_as_something_to_check(self):
        findings = check_language(
            "The principal argument rests on a principle of contract law.", include=("confusable_pairs",)
        )
        self.assertIn("I1110", codes(findings))
        self.assertIn("Check that each is the word meant", messages(findings))

    def test_one_word_of_a_pair_on_its_own_is_left_alone(self):
        self.assertEqual(
            check_language("The principal owed on the note is $900.", include=("confusable_pairs",)), []
        )


class GrammarTests(TestCase):
    def test_a_doubled_word_is_reported(self):
        findings = check_language("The the notice was defective.", include=("grammar",))
        self.assertIn("appears twice", messages(findings))

    def test_a_missing_space_after_a_sentence_is_reported(self):
        findings = check_language("The notice was defective.Service was improper.", include=("grammar",))
        self.assertIn("No space after the period", messages(findings))

    def test_a_citation_full_of_periods_is_not_a_missing_space(self):
        findings = check_language(
            "See Smith v. Jones, 12 Ohio App.3d 4 (1983).Accord R.C. 1923.04.", include=("grammar",)
        )
        self.assertNotIn("No space after the period", messages(findings))

    def test_an_unclosed_parenthesis_is_reported(self):
        findings = check_language("The notice (served on June 1 was defective.", include=("grammar",))
        self.assertIn("unclosed opening parenthesis", messages(findings))

    def test_an_unclosed_quotation_is_reported(self):
        findings = check_language('The notice said "vacate the premises within three days.', include=("grammar",))
        self.assertIn("unclosed", messages(findings))

    def test_a_citation_signal_opening_a_sentence_is_not_a_slip(self):
        findings = check_language(
            "The notice was defective. see Smith v. Jones for the controlling rule here.", include=("grammar",)
        )
        self.assertNotIn("sentence start", [finding["target"] for finding in findings])


class PassiveVoiceTests(TestCase):
    def test_a_phrase_the_court_expects_is_never_reported(self):
        text = "Respectfully submitted. The motion should be granted. The complaint was filed on June 1."
        self.assertEqual(check_language(text, include=("passive_voice",)), [])

    def test_an_ordinary_passive_is_a_nudge_not_an_error(self):
        findings = check_language("The furnace was repaired by the landlord.", include=("passive_voice",))
        self.assertEqual([finding["severity"] for finding in findings], ["info"])
        self.assertIn("I1130", codes(findings))

    def test_a_session_can_add_a_phrase_this_court_expects(self):
        text = "The furnace was repaired by the landlord."
        self.assertTrue(check_language(text, include=("passive_voice",)))
        self.assertEqual(
            check_language(text, include=("passive_voice",), accepted_passive=["was repaired"]),
            [],
        )

    def test_the_report_is_bounded_rather_than_one_finding_per_sentence(self):
        text = " ".join(["The furnace was repaired by the landlord."] * 40)
        self.assertLessEqual(len(check_language(text, include=("passive_voice",))), 12)


class SelectionTests(TestCase):
    def test_only_the_selected_checks_run(self):
        text = "The the court entered judgement. The furnace was repaired by the landlord."
        grammar_only = check_language(text, include=("grammar",))
        self.assertTrue(grammar_only)
        self.assertNotIn("W1100", codes(grammar_only))
        self.assertNotIn("I1130", codes(grammar_only))
