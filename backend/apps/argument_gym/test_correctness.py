import json
from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings

from apps.argument_gym import correctness, ingestion
from apps.argument_gym.pipeline import run_authority_research
from apps.sources.connectors.base import SourceResult


class CompleteJudgeClient:
    def complete(self, *, user, **_kwargs):
        serialized = user.split("Candidate challenges and the only evidence you may use:\n", 1)[1]
        serialized = serialized.split("\n\nReturn exactly one ruling", 1)[0]
        candidates = json.loads(serialized)
        return json.dumps(
            {
                "rulings": [
                    {
                        "candidateId": candidate["candidateId"],
                        "disposition": candidate["proposedDisposition"],
                        "reason": "The supplied evidence establishes this ruling.",
                        "evidenceRefs": candidate["briefEvidence"] + candidate["externalEvidence"],
                        "confidence": "high",
                    }
                    for candidate in candidates
                ]
            }
        )


@override_settings(AI_DRAFTING_ENABLED=False)
class CorrectnessContractTests(TestCase):
    def test_a_batch_cannot_silently_drop_or_duplicate_a_target(self):
        expected = {"a", "b"}
        self.assertTrue(correctness.complete_unique([{"id": "a"}, {"id": "b"}], "id", expected))
        self.assertFalse(correctness.complete_unique([{"id": "a"}], "id", expected))
        self.assertFalse(correctness.complete_unique([{"id": "a"}, {"id": "a"}], "id", expected))

    @override_settings(AI_DRAFTING_ENABLED=True)
    def test_empty_record_target_list_is_a_successful_test_inventory(self):
        class EmptyTargetClient:
            def complete(self, **_kwargs):
                return '{"targets": []}'

        targets, trace = correctness.record_target_stage(
            [], jurisdiction="Ohio", llm_client=EmptyTargetClient()
        )
        self.assertEqual(targets, [])
        self.assertEqual(trace["method"], "llm")

    def test_stable_identity_does_not_depend_on_generated_prose(self):
        first = correctness.stable_fingerprint("authority_support", "u4:authority:smith")
        second = correctness.stable_fingerprint("authority_support", "u4:authority:smith")
        other = correctness.stable_fingerprint("authority_support", "u4:authority:jones")
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)

    def test_authority_target_identity_survives_a_citation_mutation(self):
        clean = correctness.authority_targets(
            [{"unitId": "u4", "proposition": "The rule is mandatory.", "citedAuthority": ["Smith v. Jones"]}]
        )
        mutant = correctness.authority_targets(
            [{"unitId": "u4", "proposition": "The rule is mandatory.", "citedAuthority": ["Other v. Case"]}]
        )
        self.assertEqual(clean[0]["targetId"], mutant[0]["targetId"])
        self.assertNotEqual(clean[0]["citation"], mutant[0]["citation"])

    def test_ingested_authority_slot_survives_reporter_citation_mutation(self):
        def units(citation):
            return [
                {"id": "u4", "type": ingestion.ARGUMENT, "text": f"The rule is broad. Smith v. Jones, {citation}."},
                {"id": "u5", "type": ingestion.CITATION, "parentId": "u4", "text": citation},
            ]

        clean = correctness.authority_targets_from_units(units("18 F.3d 337, 347 (6th Cir. 1994)"))
        mutant = correctness.authority_targets_from_units(units("795 F. Supp. 2d 402 (E.D. Va. 2011)"))
        self.assertEqual(clean[0]["targetId"], mutant[0]["targetId"])
        self.assertNotEqual(clean[0]["citation"], mutant[0]["citation"])

    def test_authority_target_uses_citation_sentence_not_whole_paragraph(self):
        units = [
            {"id": "u4", "type": ingestion.ARGUMENT, "text": "Background is disputed. Smith v. Jones, 18 F.3d 337, 347 (6th Cir. 1994), holds that notice is mandatory. A different rule controls damages."},
            {"id": "u5", "type": ingestion.CITATION, "parentId": "u4", "text": "18 F.3d 337, 347 (6th Cir. 1994)"},
        ]
        target = correctness.authority_targets_from_units(units)[0]
        self.assertNotIn("different rule", target["proposition"])
        self.assertEqual(target["claimedCaseName"], "Smith v. Jones")
        self.assertEqual(target["attributionType"], "holding_or_rule")
        self.assertEqual(target["pinpoint"], "347")
        self.assertEqual(target["pinpointVerification"], "unmeasured")

    def test_date_like_ocr_fragment_is_not_an_authority(self):
        self.assertFalse(correctness.specific_authority("1 AUGUST 7"))

    def test_hybrid_extraction_prefers_full_eyecite_case_and_keeps_ohio_code(self):
        citations = ingestion._citations(
            "Smith v. Jones, 18 F.3d 337, 347 (6th Cir. 1994), applies R.C. § 1923.04."
        )
        self.assertEqual(len([value for value in citations if "18 F.3d" in value]), 1)
        self.assertTrue(any(value.startswith("Smith v. Jones") for value in citations))
        self.assertEqual(len([value for value in citations if "1923.04" in value]), 1)

    def test_authority_matcher_does_not_assume_v_has_text_on_both_sides(self):
        source = SourceResult(
            id="smith",
            title="Smith v. Jones",
            snippet="Holding",
            source_kind="local_cases",
            source_label="Cases",
            citation="18 F.3d 337",
        )
        self.assertIsInstance(
            correctness.authority_source_matches("v. Jones, 18 F.3d 337", source),
            bool,
        )

    def test_record_candidates_include_explicit_exhibit_fact_but_not_generic_argument(self):
        units = [
            {"id": "u1", "type": ingestion.ARGUMENT, "text": "Service was made by certified mail. See Exhibit 3."},
            {"id": "u2", "type": ingestion.ARGUMENT, "text": "The statute therefore requires judgment."},
        ]
        self.assertEqual(
            [unit["id"] for unit in correctness.record_candidate_units(units)],
            ["u1"],
        )

    def test_record_candidates_include_explicit_exhibit_claims_but_not_generic_argument(self):
        units = [
            {"id": "u1", "type": ingestion.ASSERTED_FACT, "text": "Notice was served."},
            {"id": "u2", "type": ingestion.ARGUMENT, "text": "Service was by certified mail. See Exhibit 3."},
            {"id": "u3", "type": ingestion.ARGUMENT, "text": "The statute therefore requires dismissal."},
        ]
        self.assertEqual(
            [unit["id"] for unit in correctness.record_candidate_units(units)],
            ["u1", "u2"],
        )

    def test_authority_resolution_is_direct_and_keeps_target_provenance(self):
        class Registry:
            def __init__(self):
                self.calls = []

            def search(self, query, **kwargs):
                self.calls.append((query, kwargs))
                return [
                    SourceResult(
                        id="smith",
                        title="Smith v. Jones",
                        snippet="The relevant holding.",
                        source_kind="local_cases",
                        source_label="Cases",
                        citation="Smith v. Jones",
                    )
                ]

        registry = Registry()
        sources, trace = run_authority_research(
            [{"targetId": "u4:authority1", "citation": "Smith v. Jones"}],
            matter=None,
            jurisdiction="Ohio",
            user=None,
            request=None,
            registry=registry,
            source_ids=["ohio-cases"],
        )
        self.assertFalse(registry.calls[0][1]["rerank"])
        self.assertEqual(sources[0]["targets"], ["u4:authority1"])
        self.assertEqual(trace[0]["targets"], ["u4:authority1"])

    @override_settings(COURTLISTENER_API_TOKEN="configured")
    def test_local_authority_match_never_calls_courtlistener_fallback(self):
        class Registry:
            def search(self, _query, **_kwargs):
                return [
                    SourceResult(
                        id="smith",
                        title="Smith v. Jones",
                        snippet="The relevant holding.",
                        source_kind="local_cases",
                        source_label="Cases",
                        citation="18 F.3d 337",
                    )
                ]

        with patch("apps.sources.courtlistener.CourtListenerCitationFallback.resolve") as external:
            run_authority_research(
                [{"targetId": "u4:authority1", "citation": "Smith v. Jones, 18 F.3d 337"}],
                matter=None,
                jurisdiction="Ohio",
                user=None,
                request=None,
                registry=Registry(),
                source_ids=["ohio-cases"],
            )
        external.assert_not_called()

    @override_settings(AI_DRAFTING_ENABLED=True)
    def test_authority_opponent_uses_small_complete_batches(self):
        class BatchClient:
            def __init__(self):
                self.batch_sizes = []

            def complete(self, *, user, **_kwargs):
                targets_text = user.split("Proposition and cited-authority targets:\n", 1)[1]
                targets = json.loads(targets_text.split("\n\nSource-specific", 1)[0])
                self.batch_sizes.append(len(targets))
                return json.dumps({"challenges": [{
                    "targetId": target["targetId"],
                    "attributionType": "holding_or_rule",
                    "evidenceState": "supported",
                    "challenge": "",
                    "reason": "The bounded source passage supports the proposition.",
                    "evidenceRefs": [target["targetId"].replace("t", "s")],
                    "sourcePassage": "The court held the rule applies.",
                } for target in targets]})

        targets = [{
            "targetId": f"t{i}", "unitId": f"u{i}", "proposition": "The rule applies.",
            "citation": f"Case {i}", "attributionType": "holding_or_rule",
        } for i in range(9)]
        sources = [{
            "id": f"s{i}", "targets": [f"t{i}"], "title": f"Case {i}",
            "citation": f"Case {i}", "snippet": "The court held the rule applies.",
        } for i in range(9)]
        client = BatchClient()
        candidates, trace = correctness.authority_opponent_stage(
            targets, sources, jurisdiction="Ohio", llm_client=client
        )
        self.assertEqual(client.batch_sizes, [4, 4, 1])
        self.assertEqual(len(candidates), 9)
        self.assertEqual(trace["batches"], 3)
        self.assertFalse(trace["unavailable"])

    def test_not_found_is_review_with_partial_record_and_may_fail_only_when_exhaustive(self):
        self.assertEqual(correctness._record_disposition("not_found", {"exhaustive": False}), correctness.REVIEW)
        self.assertEqual(correctness._record_disposition("not_found", {"exhaustive": True}), correctness.REVIEW)
        self.assertEqual(
            correctness._record_disposition("not_found", {"completeForNegativeFindings": True}),
            correctness.MUST_FIX,
        )

    def test_must_fix_without_evidence_fails_closed_to_review(self):
        candidate = {
            "checkId": "authority_support",
            "evidenceQuote": "",
            "evidenceState": "overstated",
        }
        self.assertEqual(correctness._guard_disposition(candidate, correctness.MUST_FIX, []), correctness.REVIEW)

    def test_verified_rule_with_incomplete_record_is_review_not_pass(self):
        audit = {
            "slug": "rc-5321-15-self-help", "verification": "verified",
            "source": "R.C. 5321.15", "sourceUrl": "https://codes.ohio.gov/",
            "requiresApplicabilityReview": False, "verdict": "Evidence is incomplete.",
            "elements": [{
                "id": "resulting_damage", "label": "Resulting damage",
                "requirement": "Identify damage caused by the violation.",
                "pled": "yes", "supported": "partial", "unmet": True,
                "quote": "Tenant lost access to belongings.", "materialIds": [],
                "explanation": "The supporting affidavit was not supplied.",
            }],
        }
        candidate = correctness.rule_candidates(
            [audit], [{"id": "u1", "type": ingestion.ARGUMENT, "text": "Argument"}]
        )[0]
        self.assertEqual(candidate["proposedDisposition"], correctness.REVIEW)
        self.assertFalse(candidate["userVisible"])

    @override_settings(AI_DRAFTING_ENABLED=True)
    def test_record_claim_that_cannot_be_verified_is_hidden_review(self):
        class NotVerifiableClient:
            def complete(self, **_kwargs):
                return json.dumps({"challenges": [{
                    "targetId": "u1:fact1", "evidenceState": "not_verifiable",
                    "challenge": "The supplied record does not address the call.",
                    "reason": "No relevant evidence was supplied.", "evidenceRefs": [],
                    "evidenceQuote": "",
                }]})

        candidate = correctness.record_opponent_stage(
            [{
                "targetId": "u1:fact1", "unitId": "u1", "claim": "The tenant called.",
                "citation": "", "material": True, "recordVerifiable": True,
            }],
            [],
            {"completeForNegativeFindings": False},
            jurisdiction="Ohio", llm_client=NotVerifiableClient(),
        )[0][0]
        self.assertEqual(candidate["proposedDisposition"], correctness.REVIEW)
        self.assertFalse(candidate["userVisible"])

    @override_settings(AI_DRAFTING_ENABLED=True)
    def test_authority_issue_identity_comes_from_target_not_model_wording(self):
        class AuthorityClient:
            def complete(self, **_kwargs):
                return json.dumps({"challenges": [{
                    "targetId": "u1:authority1", "evidenceState": "contradicted",
                    "attributionType": "holding_or_rule", "challenge": "Words differ.",
                    "reason": "The source does not contain the quoted language.",
                    "evidenceRefs": ["s1"], "sourcePassage": "Actual source text.",
                }]})

        candidates, _trace = correctness.authority_opponent_stage(
            [{
                "targetId": "u1:authority1", "unitId": "u1", "citation": "Case, 1 Ohio St. 1",
                "proposition": "\"Quoted language.\"", "attributionType": "quotation",
            }],
            [{"id": "s1", "targets": ["u1:authority1"], "title": "Case", "text": "Actual source text."}],
            jurisdiction="Ohio", llm_client=AuthorityClient(),
        )
        self.assertEqual(candidates[0]["issueCode"], "quotation_mismatch")

    def test_judge_cannot_make_an_opponent_candidate_more_adverse(self):
        candidate = {"checkId": "rule_elements", "proposedDisposition": correctness.PASS}
        self.assertEqual(
            correctness._guard_disposition(candidate, correctness.REVIEW, ["u1"]),
            correctness.PASS,
        )

    @override_settings(AI_DRAFTING_ENABLED=True)
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
        rulings, _traces = correctness.judge_stage(
            [candidate], jurisdiction="Ohio", llm_client=CompleteJudgeClient()
        )
        self.assertEqual(rulings[0]["disposition"], correctness.PASS)
        results = correctness.check_results(rulings)
        self.assertEqual(results["record_support"]["findings"], [])
        self.assertEqual(results["record_support"]["tests"][0]["targetId"], "u1:fact1")

    @override_settings(AI_DRAFTING_ENABLED=True)
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
        rulings, traces = correctness.judge_stage(
            candidates, jurisdiction="Ohio", llm_client=CompleteJudgeClient()
        )
        self.assertEqual(len(rulings), 11)
        self.assertTrue(all(ruling["disposition"] == correctness.MUST_FIX for ruling in rulings))
        self.assertEqual([trace["count"] for trace in traces], [8, 3])
        self.assertTrue(all(not trace["unavailable"] for trace in traces))

    @override_settings(AI_DRAFTING_ENABLED=True)
    def test_incomplete_or_unjustified_judge_batch_invalidates_the_check(self):
        class SilentJudge:
            def complete(self, **_kwargs):
                return json.dumps(
                    {
                        "rulings": [
                            {
                                "candidateId": "record_support:u1:fact1",
                                "disposition": "review",
                                "reason": "",
                                "evidenceRefs": ["u1"],
                                "confidence": "low",
                            }
                        ]
                    }
                )

        candidate = {
            "candidateId": "record_support:u1:fact1",
            "checkId": "cited_record_support",
            "issueCode": "record_support_not_found",
            "targetId": "u1:fact1",
            "unitId": "u1",
            "claim": "Notice was served.",
            "problem": "Support was not found.",
            "reason": "The record excerpt was incomplete.",
            "briefEvidence": ["u1"],
            "externalEvidence": [],
            "evidenceQuote": "",
            "proposedDisposition": correctness.REVIEW,
        }
        rulings, traces = correctness.judge_stage(
            [candidate], jurisdiction="Ohio", llm_client=SilentJudge()
        )
        self.assertEqual(rulings, [])
        self.assertTrue(traces[0]["unavailable"])
        self.assertTrue(traces[0]["checkUnavailable"])

    def test_summary_is_limited_to_test_results_not_persuasiveness(self):
        report = correctness.summary([])
        self.assertEqual(report["verdict"], "correctness review completed")
        self.assertIn("0 must-fix findings", report["assessment"])
        self.assertNotIn("persuasive", report["assessment"].casefold())

    def test_hidden_unverifiable_authority_does_not_become_attorney_review_noise(self):
        ruling = {
            "checkId": "authority_support",
            "issueCode": "authority_unverifiable",
            "targetId": "u4:authority1",
            "unitId": "u4",
            "disposition": correctness.REVIEW,
            "userVisible": False,
        }
        results = correctness.check_results([ruling])
        self.assertEqual(results["authority_support"]["findings"], [])
        self.assertIn("1 could not be verified", results["authority_support"]["summary"])
        assessment = correctness.summary([ruling], ["authority_support"])["assessment"]
        self.assertIn("0 items need attorney review", assessment)
        self.assertIn("1 could not be verified", assessment)

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

    def test_evaluation_counts_a_disappearing_target_as_instability(self):
        expected = {"checkId": "record_support", "targetId": "u2:fact1"}
        samples = [
            {
                "caseId": "record-mutation",
                "variant": "mutant",
                **expected,
                "tests": [{**expected, "disposition": "review"}],
            },
            {
                "caseId": "record-mutation",
                "variant": "mutant",
                **expected,
                "tests": [],
            },
        ]
        report = correctness.evaluate_test_runs(samples)
        self.assertEqual(report["stability"]["total"], 1)
        self.assertEqual(report["stability"]["rate"], 0.0)

    def test_record_target_cache_is_versioned_and_checksum_bound(self):
        targets = [{"targetId": "u2:fact1", "claim": "Notice was served."}]
        metadata = correctness.with_record_target_cache({"extractor": "docx"}, "abc", targets)
        self.assertEqual(correctness.cached_record_targets(metadata, "abc"), targets)
        self.assertIsNone(correctness.cached_record_targets(metadata, "changed"))
        metadata["argumentGymRecordTargets"]["version"] = "old-contract"
        self.assertIsNone(correctness.cached_record_targets(metadata, "abc"))
