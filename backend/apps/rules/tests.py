from datetime import date

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from apps.facts.models import ExtractedFact
from apps.facts.services import build_fact_snapshot
from apps.issues.models import CandidateIssue
from apps.issues.services import approve_candidate_issue, reject_candidate_issue
from apps.rules.engine import RuleEvaluationError, eval_node, evaluate_table
from apps.rules.models import DecisionRuleRow, DecisionTable, RuleRunLog
from apps.rules.services import run_decision_table_for_case


class RuleEngineTests(TestCase):
    def test_supported_operators(self):
        facts = {
            "string": {"value": "alpha"},
            "number": {"value": 5},
            "list": {"value": ["a", "b"]},
            "date": {"value": "2026-06-01"},
            "none": {"value": None},
        }

        cases = [
            ({"field": "string.value", "op": "equals", "value": "alpha"}, True),
            ({"field": "string.value", "op": "not_equals", "value": "beta"}, True),
            ({"field": "string.value", "op": "in", "value": ["alpha", "beta"]}, True),
            ({"field": "string.value", "op": "not_in", "value": ["beta"]}, True),
            ({"field": "string.value", "op": "exists"}, True),
            ({"field": "missing.value", "op": "missing"}, True),
            ({"field": "number.value", "op": "greater_than", "value": 4}, True),
            ({"field": "number.value", "op": "greater_than_or_equal", "value": 5}, True),
            ({"field": "number.value", "op": "less_than", "value": 6}, True),
            ({"field": "number.value", "op": "less_than_or_equal", "value": 5}, True),
            ({"field": "number.value", "op": "between", "value": [4, 6]}, True),
            ({"field": "list.value", "op": "contains", "value": "b"}, True),
            ({"field": "date.value", "op": "date_before", "value": "2026-06-02"}, True),
            ({"field": "date.value", "op": "date_after", "value": date(2026, 5, 31)}, True),
            ({"field": "none.value", "op": "exists"}, True),
        ]

        for condition, expected in cases:
            with self.subTest(condition=condition):
                self.assertEqual(eval_node(condition, facts), expected)

    def test_nested_all_any_not(self):
        node = {
            "all": [
                {"field": "eviction.ground", "op": "equals", "value": "nonpayment"},
                {
                    "any": [
                        {"field": "notice.exists", "op": "equals", "value": False},
                        {"field": "notice.days_between_service_and_filing", "op": "less_than", "value": 3},
                    ]
                },
                {"not": {"field": "case.dismissed", "op": "equals", "value": True}},
            ]
        }
        facts = {
            "eviction": {"ground": "nonpayment"},
            "notice": {"days_between_service_and_filing": 2},
            "case": {"dismissed": False},
        }

        self.assertTrue(eval_node(node, facts))

    def test_collect_first_unique_and_priority_hit_policies(self):
        rows = [
            {"row_id": "a", "priority": 20, "outputs": {"candidate_issue": "a"}},
            {"row_id": "b", "priority": 10, "outputs": {"candidate_issue": "b"}},
        ]

        collect_table = self.make_table("collect_table", "collect", rows)
        self.assertEqual([match["row_id"] for match in evaluate_table(collect_table, {"x": {"value": 1}})], ["b", "a"])

        first_table = self.make_table("first_table", "first", rows)
        self.assertEqual([match["row_id"] for match in evaluate_table(first_table, {"x": {"value": 1}})], ["b"])

        priority_table = self.make_table("priority_table", "priority", rows)
        self.assertEqual([match["row_id"] for match in evaluate_table(priority_table, {"x": {"value": 1}})], ["b"])

        unique_table = self.make_table("unique_table", "unique", rows)
        with self.assertRaises(RuleEvaluationError):
            evaluate_table(unique_table, {"x": {"value": 1}})

    def make_table(self, key, hit_policy, rows):
        table = DecisionTable.objects.create(
            key=key,
            title=key,
            workflow_type="eviction_answer",
            version=1,
            status="published",
            hit_policy=hit_policy,
        )
        for row in rows:
            DecisionRuleRow.objects.create(
                table=table,
                row_id=row["row_id"],
                label=row["row_id"],
                priority=row["priority"],
                conditions={"field": "x.value", "op": "equals", "value": 1},
                outputs=row["outputs"],
            )
        return table


class FactAndRuleServiceTests(TestCase):
    def setUp(self):
        self.table = DecisionTable.objects.create(
            key="test_issue_selection",
            title="Test issue selection",
            workflow_type="eviction_answer",
            version=1,
            status="published",
            hit_policy="collect",
        )
        DecisionRuleRow.objects.create(
            table=self.table,
            row_id="pending_rental_assistance",
            label="Pending rental assistance",
            conditions={
                "all": [
                    {"field": "eviction.ground", "op": "equals", "value": "nonpayment"},
                    {"field": "assistance.application_status", "op": "equals", "value": "pending"},
                ]
            },
            outputs={
                "candidate_issue": "pending_rental_assistance",
                "title": "Pending rental assistance",
                "issue_type": "defense",
                "review_required": False,
                "activate_blocks_after_approval": ["defense_pending_rental_assistance"],
            },
        )

    def test_rejected_facts_are_excluded_and_approved_only_mode_filters(self):
        ExtractedFact.objects.create(case_id="case-1", field_path="eviction.ground", value="nonpayment", review_status="approved")
        ExtractedFact.objects.create(case_id="case-1", field_path="notice.exists", value=False, review_status="rejected")
        ExtractedFact.objects.create(case_id="case-1", field_path="assistance.application_status", value="pending", review_status="needs_review")

        all_facts = build_fact_snapshot("case-1")
        approved_facts = build_fact_snapshot("case-1", include_unreviewed=False)

        self.assertEqual(all_facts["eviction"]["ground"], "nonpayment")
        self.assertNotIn("notice", all_facts)
        self.assertEqual(all_facts["assistance"]["application_status"], "pending")
        self.assertNotIn("assistance", approved_facts)

    def test_run_decision_table_creates_candidate_issue_and_log(self):
        ExtractedFact.objects.create(case_id="case-2", field_path="eviction.ground", value="nonpayment", review_status="approved")
        ExtractedFact.objects.create(case_id="case-2", field_path="assistance.application_status", value="pending", review_status="needs_review")

        result = run_decision_table_for_case(table_key="test_issue_selection", case_id="case-2", workflow_run_id="wf-1")

        issue = result["candidate_issues"][0]
        self.assertEqual(issue.issue_id, "pending_rental_assistance")
        self.assertEqual(issue.status, "needs_review")
        self.assertEqual(issue.supporting_facts, ["assistance.application_status", "eviction.ground"])
        self.assertEqual(RuleRunLog.objects.get().matched_rows, ["pending_rental_assistance"])
        self.assertEqual(CandidateIssue.objects.count(), 1)

    def test_candidate_issue_review_services(self):
        user = User.objects.create_user(username="reviewer")
        issue = CandidateIssue.objects.create(
            case_id="case-3",
            issue_id="x",
            title="X",
            issue_type="defense",
            source_table_key="test",
            source_table_version=1,
            source_row_id="row",
        )

        approve_candidate_issue(issue.id, user)
        issue.refresh_from_db()
        self.assertEqual(issue.status, "approved")

        reject_candidate_issue(issue.id, user, reason="Not supported")
        issue.refresh_from_db()
        self.assertEqual(issue.status, "rejected")
        self.assertEqual(issue.rejection_reason, "Not supported")


class SeedRuleTests(TestCase):
    def test_seed_pending_assistance_rule_matches(self):
        table = DecisionTable.objects.get(key="eviction_answer_issue_selection", version=1)
        facts = {
            "eviction": {"ground": "nonpayment"},
            "assistance": {"application_status": "pending"},
        }

        matches = evaluate_table(table, facts)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["outputs"]["candidate_issue"], "pending_rental_assistance")

    def test_run_rule_tests_command(self):
        call_command("run_rule_tests", verbosity=0)
