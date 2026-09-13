from django.test import TestCase
from django.test.utils import override_settings

from apps.argument_gym import correctness


@override_settings(AI_DRAFTING_ENABLED=False)
class CorrectnessContractTests(TestCase):
    def test_stable_identity_does_not_depend_on_generated_prose(self):
        first = correctness.stable_fingerprint("authority_support", "u4:authority:smith")
        second = correctness.stable_fingerprint("authority_support", "u4:authority:smith")
        other = correctness.stable_fingerprint("authority_support", "u4:authority:jones")
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)

    def test_not_found_is_review_with_partial_record_and_may_fail_only_when_exhaustive(self):
        self.assertEqual(correctness._record_disposition("not_found", {"exhaustive": False}), correctness.REVIEW)
        self.assertEqual(correctness._record_disposition("not_found", {"exhaustive": True}), correctness.MUST_FIX)

    def test_must_fix_without_evidence_fails_closed_to_review(self):
        candidate = {
            "checkId": "authority_support",
            "evidenceQuote": "",
            "evidenceState": "overstated",
        }
        self.assertEqual(correctness._guard_disposition(candidate, correctness.MUST_FIX, []), correctness.REVIEW)

    def test_judge_preserves_pass_and_allows_zero_visible_findings(self):
        candidate = {
            "candidateId": "record_support:u1:fact1",
            "checkId": "cited_record_support",
            "issueCode": "record_support_confirmed",
            "targetId": "u1:fact1",
            "unitId": "u1",
            "claim": "Notice was served.",
            "problem": "",
            "reason": "The cited return says notice was served.",
            "briefEvidence": ["u1"],
            "externalEvidence": ["m1"],
            "evidenceQuote": "Notice served",
            "proposedDisposition": correctness.PASS,
        }
        rulings, _traces = correctness.judge_stage([candidate], jurisdiction="Ohio")
        self.assertEqual(rulings[0]["disposition"], correctness.PASS)
        results = correctness.check_results(rulings)
        self.assertEqual(results["record_support"]["findings"], [])
        self.assertEqual(results["record_support"]["tests"][0]["targetId"], "u1:fact1")

    def test_judge_does_not_cap_verified_must_fix_results(self):
        candidates = [
            {
                "candidateId": f"authority_support:u{i}:authority:case",
                "checkId": "authority_support",
                "issueCode": "authority_overstated",
                "targetId": f"u{i}:authority:case",
                "unitId": f"u{i}",
                "claim": f"Proposition {i}",
                "problem": "The cited source is materially narrower.",
                "reason": "The source passage does not state the proposition.",
                "briefEvidence": [f"u{i}"],
                "externalEvidence": [f"s{i}"],
                "evidenceQuote": "Narrow holding.",
                "proposedDisposition": correctness.MUST_FIX,
            }
            for i in range(11)
        ]
        rulings, _traces = correctness.judge_stage(candidates, jurisdiction="Ohio")
        self.assertEqual(len(rulings), 11)
        self.assertTrue(all(ruling["disposition"] == correctness.MUST_FIX for ruling in rulings))

    def test_summary_is_limited_to_test_results_not_persuasiveness(self):
        report = correctness.summary([])
        self.assertEqual(report["verdict"], "correctness review completed")
        self.assertIn("0 must-fix findings", report["assessment"])
        self.assertNotIn("persuasive", report["assessment"].casefold())

    def test_evaluation_scores_stable_targets_instead_of_generated_comments(self):
        expected = {"checkId": "authority_support", "targetId": "u2:authority:smith"}
        samples = [
            {
                "caseId": "citation-overstatement",
                "variant": variant,
                **expected,
                "tests": [
                    {**expected, "disposition": disposition},
                    {"checkId": "rule_elements", "targetId": "r:e", "disposition": "review"},
                ],
            }
            for variant, disposition in (("clean", "pass"), ("mutant", "must_fix"), ("mutant", "must_fix"))
        ]
        report = correctness.evaluate_test_runs(samples)
        self.assertEqual(report["mutationDetection"]["rate"], 1.0)
        self.assertEqual(report["matchedSpecificity"]["rate"], 1.0)
        self.assertEqual(report["stability"]["rate"], 1.0)
        self.assertEqual(report["noise"]["additionalMustFix"], 0)
