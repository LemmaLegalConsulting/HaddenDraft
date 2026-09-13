from django.test import SimpleTestCase

from apps.sources.reported_decisions import _ohio_location, _reporter_citations


class ReportedDecisionRoutingTests(SimpleTestCase):
    def test_ohio_webcite_with_district_has_predictable_official_location(self):
        self.assertEqual(
            _ohio_location({
                "citation": "Pinewood Gardens v. Whiteside, 2014-Ohio-2305 (2d Dist.)",
                "proposition": "The Second District applied the rule.",
            }),
            ("2", "2014", "2014-Ohio-2305"),
        )

    def test_cap_route_extracts_reporter_citation_from_full_case_cite(self):
        self.assertIn(
            "110 Ohio App. 3d 70",
            _reporter_citations("Sherman v. Pearson, 110 Ohio App. 3d 70, 673 N.E.2d 643 (1996)"),
        )
