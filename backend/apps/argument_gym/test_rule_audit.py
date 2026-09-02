"""Auditing invoked rules, and applying an advocate's own checklist."""

import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.test.utils import override_settings

from apps.argument_gym import ingestion
from apps.argument_gym.checklist import apply_checklist
from apps.argument_gym.models import GymChecklist, GymDocument, GymWorkspace
from apps.argument_gym.rule_audit import challenges_from_audit, run_rule_audit
from apps.argument_gym.tests import StubRegistry
from apps.rules.models import CourtProfile, LegalRuleProfile


NOTICE_BRIEF = """
III. ARGUMENT

The landlord served the notice to leave the premises on June 1, 2026, and filed
the complaint on June 2, 2026. The notice omitted the statutory language
required by R.C. 1923.04.
"""

THIN_BRIEF = "The complaint should be dismissed under R.C. 1923.04."


def make_profile(**overrides):
    defaults = {
        "slug": "rc-1923-04-notice",
        "name": "Notice to leave the premises",
        "citation": "R.C. 1923.04",
        "jurisdiction": "Ohio",
        "citation_patterns": [r"R\.?\s*C\.?\s*1923\.04"],
        "aliases": ["three-day notice"],
        "elements": [
            {
                "id": "notice_served",
                "label": "A notice was served",
                "requirement": "The brief says the notice was served.",
                "severity": "error",
                "needsRecordSupport": True,
                "patterns": [r"serv(ed|ice) .{0,40}notice"],
                "origin": "profile",
            },
            {
                "id": "service_method",
                "label": "The notice was served by a permitted method",
                "requirement": "The brief names how the notice was delivered.",
                "severity": "error",
                "needsRecordSupport": True,
                "patterns": [r"(certified|ordinary) mail", "posted on the"],
                "origin": "profile",
            },
        ],
    }
    return LegalRuleProfile(**{**defaults, **overrides})


@override_settings(AI_DRAFTING_ENABLED=False)
class RuleAuditTests(TestCase):
    def test_an_element_the_brief_pleads_is_separated_from_one_it_does_not(self):
        audits, _traces = run_rule_audit(NOTICE_BRIEF, [], profiles=[make_profile()])
        elements = {element["id"]: element for element in audits[0]["elements"]}
        self.assertEqual(elements["notice_served"]["pled"], "yes")
        self.assertEqual(elements["service_method"]["pled"], "no")
        self.assertTrue(elements["service_method"]["unmet"])

    def test_pleading_an_element_is_not_the_same_as_supporting_it(self):
        audits, _traces = run_rule_audit(NOTICE_BRIEF, [], profiles=[make_profile()])
        served = next(item for item in audits[0]["elements"] if item["id"] == "notice_served")
        self.assertEqual(served["pled"], "yes")
        self.assertEqual(served["supported"], "nothing_supplied")
        self.assertTrue(served["unmet"])

    def test_a_case_material_that_shares_the_element_terms_counts_as_partial_support(self):
        excerpts = [
            {
                "id": "matter:1",
                "title": "Notice",
                "text": "This notice to leave the premises was served on the tenant by certified mail.",
            }
        ]
        audits, _traces = run_rule_audit(NOTICE_BRIEF, excerpts, profiles=[make_profile()])
        served = next(item for item in audits[0]["elements"] if item["id"] == "notice_served")
        self.assertEqual(served["supported"], "partial")
        self.assertEqual(served["materialIds"], ["matter:1"])

    def test_an_element_with_no_pattern_is_unknown_rather_than_missing(self):
        profile = make_profile(
            elements=[{"id": "x", "label": "Something a reader must judge", "severity": "error", "patterns": []}]
        )
        audits, _traces = run_rule_audit(NOTICE_BRIEF, [], profiles=[profile])
        # "partial" is the honest report: nothing here could decide it either way.
        self.assertEqual(audits[0]["elements"][0]["pled"], "partial")

    def test_an_unverified_element_list_can_only_warn(self):
        audits, _traces = run_rule_audit(NOTICE_BRIEF, [], profiles=[make_profile()])
        self.assertTrue(all(element["severity"] == "warning" for element in audits[0]["elements"]))

    def test_a_verified_element_list_reports_at_the_severity_it_declares(self):
        profile = make_profile(verification=CourtProfile.VERIFIED, source="R.C. 1923.04")
        audits, _traces = run_rule_audit(NOTICE_BRIEF, [], profiles=[profile])
        self.assertTrue(any(element["severity"] == "error" for element in audits[0]["elements"]))

    def test_the_audit_says_which_words_invoked_the_rule(self):
        audits, _traces = run_rule_audit(NOTICE_BRIEF, [], profiles=[make_profile()])
        self.assertEqual(audits[0]["invokedBy"], "citation")
        self.assertIn("1923.04", audits[0]["matched"])
        self.assertIn("R.C. 1923.04", audits[0]["excerpt"])

    def test_a_rule_the_brief_never_invoked_is_not_audited(self):
        audits, _traces = run_rule_audit("A brief about something else.", [], profiles=[make_profile()])
        self.assertEqual(audits, [])

    def test_the_verdict_counts_what_the_brief_did_not_carry(self):
        audits, _traces = run_rule_audit(THIN_BRIEF, [], profiles=[make_profile()])
        self.assertEqual(audits[0]["unmetCount"], 2)
        self.assertIn("2 of 2 elements are not carried", audits[0]["verdict"])

    def test_unmet_elements_become_challenges_that_say_why_they_matter(self):
        audits, _traces = run_rule_audit(THIN_BRIEF, [], profiles=[make_profile()])
        attacks = challenges_from_audit(audits)
        self.assertTrue(attacks)
        self.assertIn("R.C. 1923.04", attacks[0]["whyItMatters"])
        self.assertIn("has taken on this element", attacks[0]["whyItMatters"])
        self.assertIn("unverified element list", attacks[0]["whyItMatters"])

    def test_a_brief_that_carries_every_element_produces_no_challenges(self):
        profile = make_profile(
            elements=[
                {
                    "id": "notice_served",
                    "label": "A notice was served",
                    "severity": "error",
                    "needsRecordSupport": False,
                    "patterns": [r"serv(ed|ice) .{0,40}notice"],
                    "origin": "profile",
                }
            ]
        )
        audits, _traces = run_rule_audit(NOTICE_BRIEF, [], profiles=[profile])
        self.assertEqual(audits[0]["unmetCount"], 0)
        self.assertEqual(challenges_from_audit(audits), [])


@override_settings(AI_DRAFTING_ENABLED=False)
class ChecklistApplicationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("advocate", password="secret")
        self.workspace = GymWorkspace.objects.create(owner=self.user, title="Answer", jurisdiction="Ohio")
        self.ingested = ingestion.ingest_upload(NOTICE_BRIEF.encode("utf-8"), filename="answer.txt")
        self.brief = GymDocument.objects.create(
            workspace=self.workspace,
            role=GymDocument.BRIEF_UNDER_TEST,
            source_type=GymDocument.UPLOAD,
            title="Answer",
            extracted_text=self.ingested["text"],
            extraction_metadata=self.ingested["metadata"],
        )

    def _apply(self, items, materials=()):
        checklist = GymChecklist.objects.create(owner=self.user, title="Mine", items=items)
        return apply_checklist(
            checklist,
            brief_text=self.brief.extracted_text,
            brief_units=self.brief.structure_units,
            workspace=self.workspace,
            materials=list(materials),
            matter_summary="No case record was provided.",
            jurisdiction="Ohio",
            registry=StubRegistry(),
        )

    def test_every_item_gets_an_answer(self):
        applied = self._apply(
            [{"id": "i1", "text": "The notice date appears in the brief."}, {"id": "i2", "text": "Each authority is cited."}]
        )
        self.assertEqual(len(applied["results"]), 2)
        self.assertEqual([result["itemId"] for result in applied["results"]], ["i1", "i2"])

    def test_without_a_model_an_item_is_reported_as_needing_review_not_as_passing(self):
        applied = self._apply([{"id": "i1", "text": "The notice date appears in the brief."}])
        result = applied["results"][0]
        self.assertEqual(result["outcome"], "needs_review")
        self.assertEqual(result["method"], "deterministic")
        self.assertIn("nothing here read", result["finding"])

    def test_the_lookups_an_item_made_are_reported(self):
        applied = self._apply([{"id": "i1", "text": "notice served on the tenant"}])
        self.assertTrue(applied["lookups"])
        self.assertEqual(applied["lookups"][0]["tool"], "quote_brief")
        self.assertTrue(applied["results"][0]["evidence"])

    def test_a_blank_item_is_dropped_rather_than_answered(self):
        applied = self._apply([{"id": "i1", "text": "  "}])
        self.assertEqual(applied["results"], [])

    def test_an_item_can_read_the_case_record_through_the_sessions_own_access(self):
        from apps.argument_gym import record

        GymDocument.objects.create(
            workspace=self.workspace,
            role=GymDocument.CASE_RECORD,
            source_type=GymDocument.UPLOAD,
            title="Notice",
            extracted_text="The notice to leave the premises was served by certified mail on June 1, 2026.",
        )
        materials = record.included_materials(self.workspace)
        applied = self._apply([{"id": "i1", "text": "certified mail service"}], materials=materials)
        tools_used = {call["tool"] for call in applied["lookups"]}
        self.assertIn("quote_brief", tools_used)


class ChecklistToolTests(TestCase):
    """The lookups are read-only and bounded, and refuse what they do not know."""

    def setUp(self):
        from apps.argument_gym.checklist import ChecklistTools

        self.user = User.objects.create_user("advocate", password="secret")
        workspace = GymWorkspace.objects.create(owner=self.user, title="Answer", jurisdiction="Ohio")
        ingested = ingestion.ingest_upload(NOTICE_BRIEF.encode("utf-8"), filename="answer.txt")
        self.tools = ChecklistTools(
            brief_units=ingested["metadata"]["units"],
            workspace=workspace,
            materials=[],
            registry=StubRegistry(),
        )

    def test_an_unknown_tool_is_refused(self):
        self.assertIn("error", self.tools.run("delete_everything", {"query": "x"}))

    def test_a_lookup_without_a_query_is_refused(self):
        self.assertIn("error", self.tools.run("quote_brief", {}))

    def test_quoting_the_brief_returns_the_passages_that_match(self):
        result = self.tools.run("quote_brief", {"query": "statutory language"})
        self.assertTrue(result["passages"])
        self.assertIn("statutory language", result["passages"][0]["text"])

    def test_searching_the_law_goes_through_the_existing_retrieval(self):
        result = self.tools.run("search_law", {"query": "notice defect"})
        self.assertTrue(result["sources"])
        self.assertIn("citation", result["sources"][0])

    def test_every_lookup_is_logged_with_what_it_asked(self):
        self.tools.run("quote_brief", {"query": "notice"})
        self.tools.run("search_law", {"query": "notice defect"})
        self.assertEqual([call["tool"] for call in self.tools.calls], ["quote_brief", "search_law"])
        self.assertEqual(self.tools.calls[0]["query"], "notice")
