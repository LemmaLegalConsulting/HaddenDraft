"""Legal rule profiles: loading them, and telling which ones a brief invoked."""

import tempfile
from pathlib import Path

from django.test import TestCase

from apps.rules.legal_rules import (
    detect_invoked_rules,
    elements_from_decision_table,
    ensure_legal_rule_profiles,
    legal_rule_seeds,
    load_legal_rule_file,
    rule_elements,
    sync_legal_rule_seeds,
)
from apps.rules.models import CourtProfile, LegalRuleProfile


VALID = """
slug: rc-1923-04-notice
name: Notice to leave the premises
citation: R.C. 1923.04
rule_type: statute
jurisdiction: Ohio
citation_patterns: ["R\\\\.?\\\\s*C\\\\.?\\\\s*1923\\\\.04"]
aliases: [three-day notice]
elements:
  - id: notice_served
    label: A notice was served
    severity: error
    needs_record_support: true
    patterns: ["serv(ed|ice) .{0,40}notice"]
"""


def write(directory, name, body):
    path = Path(directory) / name
    path.write_text(body, encoding="utf-8")
    return path


class LoadingTests(TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()

    def test_a_profile_loads_with_its_elements(self):
        seed = load_legal_rule_file(write(self.directory, "rule.yaml", VALID))
        self.assertEqual(seed["citation"], "R.C. 1923.04")
        self.assertEqual(seed["elements"][0]["id"], "notice_served")
        self.assertTrue(seed["elements"][0]["needsRecordSupport"])

    def test_an_element_without_an_id_is_refused(self):
        body = "slug: x\nname: X\ncitation: R.C. 1\nelements:\n  - label: A notice was served\n"
        with self.assertRaisesMessage(ValueError, "every element needs an id and a label"):
            load_legal_rule_file(write(self.directory, "rule.yaml", body))

    def test_a_duplicate_element_id_is_refused(self):
        body = VALID + "  - id: notice_served\n    label: Again\n"
        with self.assertRaisesMessage(ValueError, "duplicate element id"):
            load_legal_rule_file(write(self.directory, "rule.yaml", body))

    def test_an_invalid_citation_pattern_is_refused_at_load_rather_than_at_run(self):
        body = VALID.replace('citation_patterns: ["R\\\\.?\\\\s*C\\\\.?\\\\s*1923\\\\.04"]', 'citation_patterns: ["([unclosed"]')
        with self.assertRaisesMessage(ValueError, "invalid citation pattern"):
            load_legal_rule_file(write(self.directory, "rule.yaml", body))

    def test_a_rule_with_no_elements_and_no_table_is_refused(self):
        body = "slug: x\nname: X\ncitation: R.C. 1\nelements: []\n"
        with self.assertRaisesMessage(ValueError, "declares no elements and names no decision-table row"):
            load_legal_rule_file(write(self.directory, "rule.yaml", body))


class SeedingTests(TestCase):
    def test_the_shipped_rules_load_and_are_all_marked_unverified(self):
        seeds = legal_rule_seeds()
        self.assertTrue(seeds)
        self.assertTrue(all(seed["verification"] == "unverified" for seed in seeds))

    def test_seeding_never_reverts_a_profile_edited_here(self):
        sync_legal_rule_seeds()
        profile = LegalRuleProfile.objects.get(slug="rc-1923-04-notice")
        profile.name = "Notice, as our office reads it"
        profile.is_locally_edited = True
        profile.save()
        sync_legal_rule_seeds(update_existing=True)
        profile.refresh_from_db()
        self.assertEqual(profile.name, "Notice, as our office reads it")

    def test_the_first_audit_seeds_the_rules_but_a_curated_list_is_left_alone(self):
        ensure_legal_rule_profiles()
        self.assertTrue(LegalRuleProfile.objects.exists())
        LegalRuleProfile.objects.exclude(slug="rc-1923-04-notice").delete()
        ensure_legal_rule_profiles()
        self.assertEqual(LegalRuleProfile.objects.count(), 1)


class DecisionTableElementTests(TestCase):
    """A rule the issue-selection tables already encode is not written down twice."""

    def test_a_published_row_contributes_its_missing_facts_and_condition_facts(self):
        elements = elements_from_decision_table("eviction_answer_issue_selection", "notice_defect")
        labels = [element["label"] for element in elements]
        self.assertIn("Confirm the notice service date.", labels)
        self.assertTrue(any("notice: exists" in label for label in labels))
        self.assertTrue(all(element["origin"] == "decision_table" for element in elements))

    def test_an_unknown_table_or_row_contributes_nothing_rather_than_failing(self):
        self.assertEqual(elements_from_decision_table("no-such-table", "row"), [])
        self.assertEqual(elements_from_decision_table("eviction_answer_issue_selection", "no-such-row"), [])
        self.assertEqual(elements_from_decision_table("", ""), [])

    def test_a_profile_merges_its_own_elements_with_the_tables(self):
        sync_legal_rule_seeds()
        profile = LegalRuleProfile.objects.get(slug="rc-1923-04-notice")
        origins = {element["origin"] for element in rule_elements(profile)}
        self.assertEqual(origins, {"profile", "decision_table"})


class DetectionTests(TestCase):
    def setUp(self):
        self.notice = LegalRuleProfile.objects.create(
            slug="rc-1923-04-notice",
            name="Notice to leave the premises",
            citation="R.C. 1923.04",
            jurisdiction="Ohio",
            citation_patterns=[r"R\.?\s*C\.?\s*1923\.04"],
            aliases=["three-day notice"],
            elements=[{"id": "a", "label": "A"}],
        )
        self.other_state = LegalRuleProfile.objects.create(
            slug="other-state-notice",
            name="Notice elsewhere",
            citation="Mich. Comp. Laws 600.5714",
            jurisdiction="Michigan",
            aliases=["three-day notice"],
            elements=[{"id": "a", "label": "A"}],
        )

    def test_a_citation_invokes_the_rule(self):
        invoked = detect_invoked_rules("The notice failed R.C. 1923.04.", profiles=[self.notice])
        self.assertEqual(invoked[0]["profile"], self.notice)
        self.assertEqual(invoked[0]["invokedBy"], "citation")

    def test_a_phrase_invokes_the_rule_and_is_reported_as_a_phrase(self):
        invoked = detect_invoked_rules("The three-day notice was defective.", profiles=[self.notice])
        self.assertEqual(invoked[0]["invokedBy"], "phrase")
        self.assertEqual(invoked[0]["matched"], "three-day notice")

    def test_a_citation_outranks_a_phrase_for_the_same_rule(self):
        invoked = detect_invoked_rules(
            "The three-day notice under R.C. 1923.04 was defective.", profiles=[self.notice]
        )
        self.assertEqual(invoked[0]["invokedBy"], "citation")

    def test_a_brief_that_invokes_nothing_returns_nothing(self):
        self.assertEqual(detect_invoked_rules("A brief about something else.", profiles=[self.notice]), [])

    def test_another_state_rule_is_not_invoked_by_a_shared_phrase(self):
        invoked = detect_invoked_rules("The three-day notice was defective.", jurisdiction="Cleveland, Ohio")
        self.assertEqual([item["profile"].slug for item in invoked], ["rc-1923-04-notice"])

    def test_the_excerpt_shows_where_in_the_brief_the_rule_was_invoked(self):
        invoked = detect_invoked_rules(
            "Some earlier text. The notice failed R.C. 1923.04 and must be dismissed.", profiles=[self.notice]
        )
        self.assertIn("must be dismissed", invoked[0]["excerpt"])
