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
    def test_caption_layout_does_not_hide_unbalanced_parentheses_in_prose(self):
        caption = "IN THE EXAMPLE COURT\n\n)\n\n)\n\n)\n\nCASE NO. 123\n"
        self.assertNotIn("parenthesis", messages(check_language(caption, include=("grammar",))))
        for prose in ("The notice (was defective.", "The notice was defective)."):
            self.assertIn("parenthesis", messages(check_language(caption + prose, include=("grammar",))))

    def test_address_and_pinpoint_fragments_are_not_lowercase_sentences(self):
        for text in ("lawyer@example.org", "c/o Agent Example", "at 12-14; Record Exhibit 3.", "at ¶17-21."):
            self.assertNotIn("sentence start", [f["target"] for f in check_language(text, include=("grammar",))])
        self.assertIn("sentence start", [f["target"] for f in check_language("at trial the witness testified.", include=("grammar",))])

    def test_a_citation_is_not_a_sentence_that_forgot_its_capital(self):
        """Every one of these came from a real Cleveland filing.

        A period inside a citation is not a sentence end, and splitting on it
        manufactures a lowercase "sentence" that starts mid-case-name. Across
        fifteen real briefs this produced seventy-one findings and not one of
        them was an error.
        """
        for citation in (
            "The rule is settled. Professional Invests. of Am., Inc. v. McCormick, 14 Ohio Misc.2d 1 (1984).",
            "See Surgical Servs. Assoc. v. Naples, 125 Ohio App.3d 394 (1998). Although that was not an eviction.",
            "The claim failed. Hous. Auth. of City of Raleigh, 595 F.Supp. 2d 1 (E.D.N.C. 2009).",
            "It was dismissed. Bd. of Commissioners, 2019-Ohio-3729, 144 N.E.3d 1010, ¶33 (11th Dist.).",
        ):
            self.assertNotIn(
                "sentence start", [f["target"] for f in check_language(citation, include=("grammar",))], citation
            )

    def test_a_subsection_heading_is_not_a_sentence_that_forgot_its_capital(self):
        text = "The service was not perfected under the Civil Rules.\n\na. R.C. 1923.06 service requirements\n"
        self.assertNotIn("sentence start", [f["target"] for f in check_language(text, include=("grammar",))])

    def test_a_genuinely_lowercase_sentence_is_still_reported(self):
        text = "Inclusive Communities promulgated a three-step burden shifting framework. under the first step, the plaintiff must show causation."
        self.assertIn("sentence start", [f["target"] for f in check_language(text, include=("grammar",))])

    def test_a_drafting_note_does_not_split_the_sentence_it_interrupts(self):
        """The placeholder check already reports the note; this must not report it twice."""
        text = "On October 11, 2022, Pine Creek [from who? confirm this] received an email about the abatement."
        self.assertNotIn("sentence start", [f["target"] for f in check_language(text, include=("grammar",))])

    def test_an_enumerator_is_not_a_closing_parenthesis_with_nothing_opened(self):
        text = 'The movant must prove: 1) no genuine issue of fact, 2) entitlement as a matter of law, and 3) one conclusion.'
        self.assertNotIn("parenthesis", messages(check_language(text, include=("grammar",))))

    def test_an_enumerator_inside_a_parenthetical_still_closes_it(self):
        """Stripping "A)" as an enumerator would leave "(Attached as Appendix" unclosed."""
        text = "Smith v. Jones, No. CV-17-875960 (Apr. 20, 2017) (Attached as Appendix A). The rule is settled."
        self.assertNotIn("parenthesis", messages(check_language(text, include=("grammar",))))

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
        # The finding names the passage: a count of unbalanced delimiters is
        # not something an advocate can act on.
        self.assertIn("An opening parenthesis is never closed.", messages(findings))
        self.assertIn("The notice (served on June 1", messages(findings))

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
