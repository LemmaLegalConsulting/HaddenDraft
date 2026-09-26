from django.test import SimpleTestCase

from apps.exporting.authorities import collect_authorities


def authorities(*paragraphs):
    registry, marks = collect_authorities(list(paragraphs))
    return registry, marks


class CaseCitationTests(SimpleTestCase):
    def test_parallel_cites_pinpoints_and_parenthetical_make_one_entry(self):
        registry, marks = authorities(
            "See Dresher v. Burt, 75 Ohio St.3d 280, 293, 662 N.E.2d 264 (1996). The rule is settled."
        )
        [authority] = registry.ordered()
        self.assertEqual(authority.category, "cases")
        # The signal is not part of the name and the pinpoint is not part of the entry.
        self.assertEqual(authority.long_cite, "Dresher v. Burt, 75 Ohio St.3d 280, 662 N.E.2d 264 (1996)")
        self.assertEqual(authority.long_cite[slice(*authority.italic)], "Dresher v. Burt")
        [occurrence] = marks[0]
        self.assertTrue(occurrence.first)
        text = "See Dresher v. Burt, 75 Ohio St.3d 280, 293, 662 N.E.2d 264 (1996). The rule is settled."
        # The TA field goes after the closing parenthesis, and the name is known.
        self.assertEqual(text[occurrence.end - 1], ")")
        self.assertEqual(text[slice(*occurrence.name_span)], "Dresher v. Burt")

    def test_ohio_docket_form_and_older_year_form_keep_their_shape(self):
        registry, _marks = authorities(
            "Rowan v. McLaughlin, 8th Dist. Cuyahoga No. 85665, 2005-Ohio-3473, ¶ 6.",
            "Rispo Realty v. Parma (1990), 55 Ohio St.3d 101, 102-103.",
        )
        self.assertEqual(
            [authority.long_cite for authority in registry.ordered()],
            [
                "Rowan v. McLaughlin, 8th Dist. Cuyahoga No. 85665, 2005-Ohio-3473",
                "Rispo Realty v. Parma (1990), 55 Ohio St.3d 101",
            ],
        )

    def test_later_citations_of_the_same_case_are_marked_under_the_first(self):
        registry, marks = authorities(
            "Cuyahoga Metro. Hous. Auth. v. Younger, 93 Ohio App.3d 819, 824, 639 N.E.2d 1253 (8th Dist.1994).",
            "The notice must state the grounds. Younger, 639 N.E.2d at 1256.",
            "The same court said so again. Younger, 93 Ohio App.3d 819, 825.",
        )
        [authority] = registry.ordered()
        self.assertEqual(authority.occurrences, 3)
        self.assertEqual([len(paragraph) for paragraph in marks], [1, 1, 1])
        self.assertFalse(marks[1][0].first)
        self.assertEqual(marks[1][0].key, authority.key)

    def test_explanatory_parenthetical_is_not_part_of_the_entry(self):
        registry, _marks = authorities(
            "Lucas Metro. Hous. Auth. v. Kincade, 6th Dist. Lucas No. L-94-211, 1995 WL 112963 "
            "(overruled on other grounds by Sabrina J. v. Robbin C., 6th Dist. Lucas No. L-00-1374, 2001 WL 85157)."
        )
        entries = [authority.long_cite for authority in registry.ordered()]
        self.assertEqual(
            entries,
            [
                "Lucas Metro. Hous. Auth. v. Kincade, 6th Dist. Lucas No. L-94-211, 1995 WL 112963",
                "Sabrina J. v. Robbin C., 6th Dist. Lucas No. L-00-1374, 2001 WL 85157",
            ],
        )

    def test_case_name_after_another_citations_parenthetical(self):
        registry, _marks = authorities(
            "Associated Estates Realty Corp. v. Samsa, 2004-Ohio-6635 (8th Dist.) and "
            "K & D Mgt. v. Masten, 2013-Ohio-2905 (8th Dist.)."
        )
        self.assertEqual(
            [authority.long_cite for authority in registry.ordered()],
            [
                "Associated Estates Realty Corp. v. Samsa, 2004-Ohio-6635 (8th Dist.)",
                "K & D Mgt. v. Masten, 2013-Ohio-2905 (8th Dist.)",
            ],
        )

    def test_a_citation_without_a_findable_name_is_marked_and_reported(self):
        registry, marks = authorities("As the court held, 55 Ohio St.3d 101 controls.")
        [authority] = registry.ordered()
        self.assertFalse(authority.name_found)
        self.assertEqual(len(marks[0]), 1)
        self.assertIn("55 Ohio St.3d 101", registry.report()["unmarked"][0]["text"])


class StatuteAndRuleTests(SimpleTestCase):
    def test_subdivisions_collapse_to_one_entry_per_section(self):
        registry, _marks = authorities(
            "R.C. 5321.04(A)(2) and R.C. 5321.04(B) both apply, as does R.C. 1.47.",
            "Civ.R. 56(C) and Civ. R. 56(E) govern; see also Loc.App.R. 16(A) and App.R. 13.",
            "The notice violated 24 C.F.R. § 247.4(a)(2) and Cleveland Cod.Ord. 375.08.",
        )
        by_category = {
            category: [authority.long_cite for authority in items]
            for category, items in registry.by_category().items()
        }
        self.assertEqual(by_category["statutes"], ["Cleveland Cod.Ord. 375.08", "R.C. 1.47", "R.C. 5321.04"])
        self.assertEqual(by_category["rules"], ["App.R. 13", "Civ.R. 56", "Loc.App.R. 16"])
        self.assertEqual(by_category["regulations"], ["24 C.F.R. 247.4"])


class UnmarkedReportTests(SimpleTestCase):
    def test_references_that_name_no_authority_are_counted_not_listed(self):
        registry, _marks = authorities("Id. at 5.", "Id.", "See supra.")
        unmarked = registry.report()["unmarked"]
        self.assertEqual(len(unmarked), 1)
        self.assertEqual(unmarked[0]["count"], 3)

    def test_docket_only_decision_is_reported_rather_than_dropped(self):
        registry, marks = authorities(
            "AAPK Constr. LLC v. Jonathon Pool, et al., Cleveland M.C. Hous. Div. Case No. 2025-CVG-014827, "
            "Judgment Entry, at ¶ 10."
        )
        self.assertEqual(registry.ordered(), [])
        self.assertEqual(marks, [[]])
        [item] = registry.report()["unmarked"]
        self.assertTrue(item["text"].startswith("AAPK Constr. LLC v. Jonathon Pool"))
        self.assertIn("docket number", item["reason"])

    def test_page_numbers_are_reported_unmeasured(self):
        registry, _marks = authorities("R.C. 1923.04.")
        self.assertEqual(registry.report()["pageNumbers"], "unmeasured")
