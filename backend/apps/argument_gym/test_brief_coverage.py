"""What a stage reads of a long brief, and what the offline stand-in may claim.

Both of these were found by running fifteen real Cleveland filings through the
pipeline rather than by reading the code, and both were invisible from inside a
short test fixture.
"""

from django.test import TestCase
from django.test.utils import override_settings

from apps.argument_gym import ingestion
from apps.argument_gym.pipeline import (
    _fallback_argument_map,
    _fallback_assessment,
    _fallback_attacks,
    _unit_payload,
    asserts_a_legal_proposition,
    dumps,
    select_units,
    unit_budget_chars,
    unit_coverage,
    unit_text_limit,
)


# Sized from the corpus: the largest real filing is 694 units and 71,450
# characters of text, so a little over a hundred characters per unit. A fixture
# built out of much longer units would exceed the budget for a reason no real
# brief does and would test the sampling rather than the default.
CORPUS_UNIT_TEXT = "The landlord violated the statute and must be held liable. " * 2


def make_units(count, *, kind=ingestion.ARGUMENT, text=CORPUS_UNIT_TEXT):
    return [
        {
            "id": f"u{index}",
            "type": kind,
            "text": text,
            "locator": {"section": f"III.{index}", "paragraph": index, "page": 1},
        }
        for index in range(count)
    ]


class UnitSelectionTests(TestCase):
    def test_a_brief_that_fits_is_read_whole(self):
        units = make_units(20)
        selected, omitted = select_units(units)
        self.assertEqual(len(selected), 20)
        self.assertEqual(omitted, 0)
        self.assertIn("All 20 units", unit_coverage(units))

    def test_the_default_budget_reads_a_brief_the_size_of_a_real_one_whole(self):
        """The largest filing in the local corpus is 694 units and 71,450 characters.

        The point of the default is that a brief that size is read, not sampled,
        so nothing downstream has to reason about passages it was not given.
        """
        units = make_units(700)
        selected, omitted = select_units(units)
        self.assertEqual(omitted, 0, "a corpus-sized brief should not need sampling")
        self.assertEqual(len(selected), 700)
        self.assertIn("All 700 units", unit_coverage(units))

    def test_no_unit_of_a_real_brief_is_individually_truncated(self):
        """The longest single unit in the corpus is 1,735 characters."""
        self.assertGreater(unit_text_limit(), 1735)

    @override_settings(ARGUMENT_GYM_UNIT_BUDGET_CHARS=20_000)
    def test_a_brief_beyond_any_budget_is_sampled_across_the_document(self):
        """Sampling is the safety valve for a filing larger than the budget.

        Before it existed the first 80 units were the whole of what a stage saw,
        so the opponent read the caption, the procedural history and the opening
        facts, then attacked a brief whose argument it had not been shown.
        """
        units = make_units(700)
        selected, omitted = select_units(units)
        self.assertTrue(omitted, "this budget is meant to force sampling")
        chosen = {unit["id"] for unit in selected}
        first_quarter = [unit for unit in units[:175] if unit["id"] in chosen]
        last_quarter = [unit for unit in units[525:] if unit["id"] in chosen]
        self.assertTrue(last_quarter, "the end of the brief was never shown to the model")
        # Evenly spread rather than front-loaded.
        self.assertAlmostEqual(len(first_quarter), len(last_quarter), delta=max(2, len(first_quarter) // 4))
        self.assertIn("sampled across the whole", unit_coverage(units))

    @override_settings(ARGUMENT_GYM_UNIT_BUDGET_CHARS=20_000)
    def test_the_argument_is_kept_before_the_citations_it_cites(self):
        units = [
            *make_units(400, kind=ingestion.CITATION, text="R.C. 1923.04. "),
            *make_units(40, kind=ingestion.ARGUMENT),
        ]
        selected, _omitted = select_units(units)
        kinds = {unit["type"] for unit in selected}
        argument_ids = {unit["id"] for unit in selected if unit["type"] == ingestion.ARGUMENT}
        self.assertEqual(len(argument_ids), 40, kinds)

    @override_settings(ARGUMENT_GYM_UNIT_BUDGET_CHARS=20_000)
    def test_selection_stays_in_document_order(self):
        units = make_units(700)
        selected, _omitted = select_units(units)
        order = [int(unit["id"][1:]) for unit in selected]
        self.assertEqual(order, sorted(order))

    @override_settings(ARGUMENT_GYM_UNIT_BUDGET_CHARS=20_000)
    def test_the_budget_holds_when_the_units_are_not_all_the_same_size(self):
        """A real brief's units run from a 13-character citation to a block quote.

        Sampling by the tier's average unit overshot the budget on the real
        corpus by a few percent while passing against a fixture whose units were
        all identical, so each unit is charged as it is taken.
        """
        units = []
        for index in range(600):
            length = (13, 120, 400, 1500)[index % 4]
            units.append(
                {
                    "id": f"u{index}",
                    "type": ingestion.ARGUMENT,
                    "text": ("The landlord violated the statute. " * 50)[:length],
                    "locator": {"section": f"III.{index}", "paragraph": index, "page": 1},
                }
            )
        self.assertLessEqual(len(dumps(_unit_payload(units))), unit_budget_chars())
        # And the end of the document still survives the sampling.
        chosen = {unit["id"] for unit in select_units(units)[0]}
        self.assertTrue([unit for unit in units[450:] if unit["id"] in chosen])

    @override_settings(ARGUMENT_GYM_UNIT_BUDGET_CHARS=20_000)
    def test_the_budget_is_measured_against_what_is_actually_sent(self):
        """The payload, not an estimate of it.

        The first version of the cost function guessed eighty characters of JSON
        envelope per unit; the real figure is nearer a hundred and fifty, so a
        brief measured as fitting serialized to half again as much. A budget
        that does not mean what it says is worse than no budget.
        """
        payload = dumps(_unit_payload(make_units(700)))
        self.assertLessEqual(len(payload), unit_budget_chars())


class OfflineStandInTests(TestCase):
    """The offline stand-in can see whether a passage cites anything. That is all."""

    def test_it_does_not_call_a_recitation_an_uncited_proposition(self):
        for passage in (
            "Now comes Appellant Thomasina Thomas, by and through counsel, and respectfully moves "
            "this Court to enter summary judgment on her Administrative Appeal.",
            "Motion for Summary Judgment Standard of Review",
            "Ms. Vourliotis was never served and never waived service under the Civil Rules………………4",
            "CMHA is a public housing authority. On December 19, 2024, CMHA issued a decision to "
            "terminate Ms. Thomas's participation in the voucher program.",
        ):
            with self.subTest(passage=passage[:40]):
                self.assertFalse(asserts_a_legal_proposition(passage))

    def test_it_still_names_a_proposition_advanced_without_authority(self):
        self.assertTrue(
            asserts_a_legal_proposition(
                "Acceptance of rent after service of the notice bars the eviction as a matter of law."
            )
        )

    def test_an_uncited_recitation_produces_no_attack(self):
        units = [
            {
                "id": "u1",
                "type": ingestion.ARGUMENT,
                "text": "Now comes Appellant, by and through counsel, and respectfully moves this Court.",
                "locator": {"section": "I", "paragraph": 1, "page": 1},
            }
        ]
        attacks = _fallback_attacks(units, _fallback_argument_map(units), [], [])
        self.assertEqual([attack["category"] for attack in attacks], [])

    def test_a_run_no_model_read_does_not_report_a_clean_brief(self):
        """"No challenges" and "no review" are different, and only one is good news."""
        offline = _fallback_assessment([], opponent_method="deterministic")[0]
        self.assertEqual(offline["verdict"], "not reviewed")
        self.assertIn("No model read this brief", offline["assessment"])

        turned_off = _fallback_assessment([], opponent_method="off")[0]
        self.assertIn("turned off", turned_off["assessment"])

        read = _fallback_assessment([], opponent_method="llm")[0]
        self.assertEqual(read["verdict"], "no challenges raised")
        self.assertNotIn("No model read", read["assessment"])
