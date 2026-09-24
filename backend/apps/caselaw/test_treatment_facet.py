from django.test import SimpleTestCase

from apps.caselaw.catalog import apply_filters, facet_counts


class TreatmentFacetTests(SimpleTestCase):
    """The Treatment facet shows treatment, not dispositions or publication states."""

    ROWS = [{"treatment_status": value} for value in (
        "unchecked", "unchecked", "reviewed", "checked", "good law", "positive",
        "published", "affirmed", "reversed and remanded", "something new",
    )]

    def test_values_group_by_the_reviewed_vocabulary(self):
        counts = {item["value"]: item["count"] for item in facet_counts(self.ROWS, {})["treatmentStatus"]}

        self.assertEqual(counts["Treatment not checked"], 2)
        self.assertEqual(counts["Treatment checked"], 2)
        self.assertEqual(counts["Checked and good law"], 2)
        # A disposition is not negative treatment, and is not guessed into it.
        self.assertEqual(counts["Not a treatment value (disposition or publication state)"], 3)
        # A value the vocabulary does not list keeps its own wording.
        self.assertEqual(counts["something new"], 1)

    def test_choosing_a_group_selects_every_value_in_it(self):
        chosen = apply_filters(self.ROWS, {"treatmentStatus": ["Checked and good law"]})

        self.assertEqual(sorted(row["treatment_status"] for row in chosen), ["good law", "positive"])
