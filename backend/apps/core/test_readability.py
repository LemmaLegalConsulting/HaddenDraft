from django.test import TestCase

from apps.validation.readability import (
    check_readability,
    compute_metrics,
    count_syllables,
    strip_template_tokens,
)


PLAIN = (
    "You can ask the Court to seal this case. You can do this without a lawyer. "
    "It costs money to file. Court staff can help you."
)
DENSE = (
    "Notwithstanding the aforementioned habitability considerations, the premises "
    "shall be vacated by the tenant subsequent to the adjudication of the detainer "
    "action, and restitution was granted to the plaintiff by the magistrate."
)


class ReadabilityMetricTests(TestCase):
    def test_syllable_counting_handles_silent_e(self):
        self.assertEqual(count_syllables("move"), 1)
        self.assertEqual(count_syllables("notice"), 2)
        self.assertEqual(count_syllables("habitability"), 6)

    def test_several_formulas_are_reported_side_by_side(self):
        """No single score is authoritative, so all of them are surfaced."""
        metrics = compute_metrics(PLAIN)

        for key in ("flesch_kincaid_grade", "smog_index", "flesch_reading_ease", "gunning_fog"):
            self.assertIn(key, metrics)

    def test_dense_prose_scores_worse_than_plain_prose(self):
        self.assertGreater(
            compute_metrics(DENSE)["flesch_kincaid_grade"],
            compute_metrics(PLAIN)["flesch_kincaid_grade"],
        )

    def test_template_bindings_are_not_scored_as_prose(self):
        """An unrendered binding would otherwise inflate the difficulty."""
        text = "Call {{ advocate_phone }} before [DATE] about ____."

        self.assertNotIn("advocate_phone", strip_template_tokens(text))
        self.assertNotIn("[DATE]", strip_template_tokens(text))


class PlainLanguageRuleTests(TestCase):
    def test_plain_text_passes(self):
        self.assertTrue(check_readability(PLAIN).passed)

    def test_dense_text_reports_the_metric_and_the_sentence(self):
        report = check_readability(DENSE)

        self.assertFalse(report.passed)
        rules = {finding.rule for finding in report.findings}
        self.assertIn("flesch_kincaid_grade", rules)
        self.assertIn("sentence_length", rules)

    def test_a_banned_word_is_reported_with_its_replacement(self):
        report = check_readability("Please vacate the premises.")

        messages = " ".join(finding.message for finding in report.findings)
        self.assertIn('Use "move" instead of "vacate"', messages)
        self.assertIn('Use "home" instead of "premises"', messages)

    def test_jargon_is_allowed_when_the_letter_defines_it(self):
        undefined = check_readability("You must file objections about possession.")
        defined = check_readability('You can ask the court for "possession" (the right to live there).')

        undefined_terms = {finding.excerpt for finding in undefined.findings if finding.rule == "define_or_avoid"}
        defined_terms = {finding.excerpt for finding in defined.findings if finding.rule == "define_or_avoid"}
        self.assertIn("possession", undefined_terms)
        self.assertNotIn("possession", defined_terms)

    def test_an_overlong_letter_is_flagged_against_its_page_target(self):
        report = check_readability("You must go to your hearing. " * 260, kind="advice")

        self.assertTrue(any(finding.rule == "length" for finding in report.findings))

    def test_empty_text_does_not_crash(self):
        report = check_readability("")

        self.assertEqual(report.sentences, 0)
        self.assertEqual(report.metrics, {})
