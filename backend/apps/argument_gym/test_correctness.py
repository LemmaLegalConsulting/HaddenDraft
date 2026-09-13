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

    def test_authority_target_keeps_complete_opinion_status_parenthetical(self):
        units = [
            {"id": "u4", "type": ingestion.ARGUMENT, "text": "See Sherman v. Pearson (1996), 110 Ohio App.3d 70, 77 (J. Painter, dissenting)."},
            {"id": "u5", "type": ingestion.CITATION, "parentId": "u4", "text": "Sherman v. Pearson (1996), 110 Ohio App.3d 70, 77"},
        ]
        target = correctness.authority_targets_from_units(units)[0]
        self.assertIn("Painter, dissenting", target["proposition"])
        self.assertEqual(target["claimedOpinionStatus"], "dissent")

    def test_citation_nested_inside_another_sources_quote_is_not_a_quotation_target(self):
        units = [
            {
                "id": "u4", "type": ingestion.ARGUMENT,
                "text": 'Haney concluded: "Pursuant to R.C. 1923.081, the tenant may reserve claims."',
            },
            {
                "id": "u5", "type": ingestion.CITATION, "parentId": "u4",
                "text": "R.C. 1923.081",
            },
        ]

        target = correctness.authority_targets_from_units(units)[0]

        self.assertTrue(target["citationInsideQuotation"])
        self.assertEqual(target["attributionType"], "general_support")

    @override_settings(AI_DRAFTING_ENABLED=True)
    def test_nested_citation_is_hidden_without_model_adjudication(self):
        class ShouldNotRun:
            def complete(self, **_kwargs):
                raise AssertionError("Nested citation should not reach Opponent")

        targets = [{
            "targetId": "u4:authority1", "unitId": "u4",
            "proposition": '"Pursuant to R.C. 1923.081 ..."',
            "citation": "R.C. 1923.081", "citationInsideQuotation": True,
        }]
        sources = [{
            "id": "s1", "targets": ["u4:authority1"], "title": "R.C. 1923.081",
            "snippet": "Statutory text.",
        }]

        candidates, trace = correctness.authority_opponent_stage(
            targets, sources, jurisdiction="Ohio", llm_client=ShouldNotRun()
        )

        self.assertEqual(candidates[0]["issueCode"], "nested_authority_attribution_unmeasured")
        self.assertFalse(candidates[0]["userVisible"])
        self.assertFalse(candidates[0]["requiresJudge"])
        self.assertFalse(trace["unavailable"])

    @override_settings(AI_DRAFTING_ENABLED=True)
    def test_case_citation_always_has_a_stable_opinion_status_test(self):
        class SupportedCaseClient:
            def complete(self, **_kwargs):
                return json.dumps({"challenges": [{
                    "targetId": "u1:authority1", "attributionType": "holding_or_rule",
                    "evidenceState": "supported", "challenge": "", "reason": "Supported.",
                    "evidenceRefs": ["s1"], "sourcePassage": "The court held the rule applies.",
                    "opinionStatusState": "not_applicable",
                    "opinionStatusChallenge": "", "opinionStatusReason": "No qualifier is implicated.",
                    "opinionStatusEvidenceRefs": [], "opinionStatusPassage": "",
                }]})

        targets = [{
            "targetId": "u1:authority1", "unitId": "u1", "proposition": "The rule applies.",
            "citation": "Smith v. Jones, 18 F.3d 337", "claimedCaseName": "Smith v. Jones",
            "attributionType": "holding_or_rule",
        }]
        sources = [{
            "id": "s1", "targets": ["u1:authority1"], "title": "Smith v. Jones",
            "snippet": "The court held the rule applies.",
        }]

        candidates, _trace = correctness.authority_opponent_stage(
            targets, sources, jurisdiction="Ohio", llm_client=SupportedCaseClient()
        )

        by_target = {candidate["targetId"]: candidate for candidate in candidates}
        status = by_target["u1:authority1:opinion_status"]
        self.assertEqual(status["proposedDisposition"], correctness.PASS)
        self.assertEqual(status["issueCode"], "opinion_status_not_applicable")
        self.assertFalse(status["userVisible"])

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
    def test_one_resolved_opinion_is_reused_for_later_pinpoint_to_same_case(self):
        class Registry:
            def __init__(self):
                self.calls = 0

            def search(self, _query, **_kwargs):
                self.calls += 1
                if self.calls == 1:
                    return [SourceResult(
                        id="sherman", title="Sherman v. Pearson",
                        snippet="Opinion text.", source_kind="local_cases",
                        source_label="Cases", citation="110 Ohio App.3d 70, 673 N.E.2d 643",
                    )]
                return []

        targets = [
            {"targetId": "u1:authority1", "citation": "Sherman v. Pearson, 110 Ohio App.3d 70"},
            {"targetId": "u2:authority1", "citation": "Sherman v. Pearson, 110 Ohio App. 3d 70, 77, 673 N.E. 2d 643, 648"},
        ]
        with patch("apps.sources.courtlistener.CourtListenerCitationFallback.resolve") as external:
            sources, trace = run_authority_research(
                targets, matter=None, jurisdiction="Ohio", user=None, request=None,
                registry=Registry(), source_ids=["ohio-cases"],
            )
        external.assert_not_called()
        self.assertEqual(set(sources[0]["targets"]), {"u1:authority1", "u2:authority1"})
        self.assertTrue(all(item["augmentation"]["finalEvaluation"]["adequate"] for item in trace))

    def test_authority_identity_rejects_unrelated_search_hit(self):
        result = SourceResult(
            id="anderson", title="Anderson v. Champer", snippet="Mentions Sherman.",
            source_kind="local_cases", source_label="Cases", citation="No. 99 CVG 00424",
        )
        self.assertFalse(correctness.authority_source_matches(
            "Sherman v. Pearson, 110 Ohio App.3d 70", result
        ))

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

    @override_settings(COURTLISTENER_API_TOKEN="configured")
    def test_free_reported_sources_run_before_courtlistener(self):
        class EmptyRegistry:
            def search(self, _query, **_kwargs):
                return []

        free_result = SourceResult(
            id="cap:1", title="Smith v. Jones", snippet="The relevant holding.",
            source_kind="cap", source_label="Caselaw Access Project",
            citation="18 F.3d 337", metadata={"targetId": "u4:authority1"},
        )
        with patch(
            "apps.sources.reported_decisions.FreeReportedDecisionFallback.resolve",
            return_value=([free_result], {"method": "ohio_rod_then_cap", "resolved": 1}),
        ) as free, patch(
            "apps.sources.courtlistener.CourtListenerCitationFallback.resolve"
        ) as courtlistener:
            sources, trace = run_authority_research(
                [{"targetId": "u4:authority1", "citation": "Smith v. Jones, 18 F.3d 337", "proposition": "The relevant holding."}],
                matter=None, jurisdiction="Ohio", user=None, request=None,
                registry=EmptyRegistry(), source_ids=["ohio-cases"],
            )
        free.assert_called_once()
        courtlistener.assert_not_called()
        self.assertEqual(sources[0]["sourceKind"], "cap")
        self.assertTrue(trace[0]["augmentation"]["finalEvaluation"]["adequate"])

    @override_settings(COURTLISTENER_API_TOKEN="configured")
    def test_ohio_web_cite_without_reporter_reaches_free_fallback_only(self):
        class EmptyRegistry:
            def search(self, _query, **_kwargs):
                return []

        target = {
            "targetId": "u4:authority1",
            "citation": "Boone Coleman Constr., Inc. v. Village of Piketon, 2016-Ohio-628",
            "proposition": "The Ohio Supreme Court reviews contract interpretation de novo.",
        }
        free_result = SourceResult(
            id="ohio-rod:2016-Ohio-628",
            title="Boone Coleman Constr., Inc. v. Village of Piketon",
            snippet="We review the interpretation of a contract, a question of law, de novo.",
            source_kind="ohio_reported_decisions",
            source_label="Supreme Court of Ohio Reporter of Decisions",
            citation="2016-Ohio-628",
            metadata={"targetId": target["targetId"]},
        )
        with patch(
            "apps.sources.reported_decisions.FreeReportedDecisionFallback.resolve",
            return_value=([free_result], {"method": "ohio_rod_then_cap", "resolved": 1}),
        ) as free, patch(
            "apps.sources.courtlistener.CourtListenerCitationFallback.resolve"
        ) as courtlistener:
            sources, trace = run_authority_research(
                [target], matter=None, jurisdiction="Ohio", user=None, request=None,
                registry=EmptyRegistry(), source_ids=["ohio-cases"],
            )

        free.assert_called_once_with([target])
        courtlistener.assert_not_called()
        self.assertEqual(sources[0]["sourceKind"], "ohio_reported_decisions")
        self.assertTrue(trace[0]["augmentation"]["finalEvaluation"]["adequate"])

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

    def test_clear_missing_rule_element_gives_judge_bounded_brief_evidence(self):
        audit = {
            "slug": "rc-5321-11-notice-to-cure", "verification": "verified",
            "source": "R.C. 5321.11", "sourceUrl": "https://codes.ohio.gov/",
            "excerpt": "The landlord invokes R.C. 5321.11 but states no termination date.",
            "briefCoverage": {"reviewedChars": 200, "totalChars": 200, "truncated": False},
            "requiresApplicabilityReview": False, "verdict": "One element is absent.",
            "elements": [{
                "id": "termination_date", "label": "Termination date",
                "requirement": "State a termination date at least thirty days after receipt.",
                "pled": "no", "supported": "nothing_supplied", "unmet": True,
                "quote": "", "materialIds": [],
                "explanation": "The brief gives no termination date.",
            }],
        }
        candidate = correctness.rule_candidates(
            [audit], [{"id": "u1", "type": ingestion.ARGUMENT, "text": "Argument"}]
        )[0]
        self.assertEqual(candidate["proposedDisposition"], correctness.MUST_FIX)
        self.assertEqual(candidate["briefEvidence"], ["u1"])
        self.assertIn("states no termination date", candidate["evidenceQuote"])
        self.assertFalse(candidate["briefCoverage"]["truncated"])

    def test_phrase_only_rule_match_is_not_attorney_facing(self):
        audit = {
            "slug": "rc-1923-04-notice", "verification": "verified",
            "source": "R.C. 1923.04", "sourceUrl": "https://codes.ohio.gov/",
            "matched": "three-day notice", "verdict": "The rule was not invoked.",
            "requiresApplicabilityReview": True, "elements": [],
        }

        candidate = correctness.rule_candidates(
            [audit], [{"id": "u1", "type": ingestion.ARGUMENT, "text": "Argument"}]
        )[0]

        self.assertEqual(candidate["proposedDisposition"], correctness.REVIEW)
        self.assertFalse(candidate["userVisible"])

    def test_missing_element_in_truncated_brief_fails_closed(self):
        audit = {
            "slug": "rc-5321-11-notice-to-cure", "verification": "verified",
            "source": "R.C. 5321.11", "sourceUrl": "https://codes.ohio.gov/",
            "excerpt": "The landlord invokes R.C. 5321.11.",
            "briefCoverage": {"reviewedChars": 100, "totalChars": 200, "truncated": True},
            "requiresApplicabilityReview": False, "verdict": "One element was not found.",
            "elements": [{
                "id": "termination_date", "label": "Termination date",
                "requirement": "State a termination date at least thirty days after receipt.",
                "pled": "no", "supported": "yes", "unmet": True,
                "quote": "", "materialIds": ["record:1"],
                "explanation": "No date appeared in the reviewed portion.",
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
                    "opinionStatusState": "not_applicable",
                    "opinionStatusChallenge": "", "opinionStatusReason": "No qualifier is implicated.",
                    "opinionStatusEvidenceRefs": [], "opinionStatusPassage": "",
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

    @override_settings(AI_DRAFTING_ENABLED=True)
    def test_omitted_dissent_label_is_a_separate_authority_candidate(self):
        class AuthorityClient:
            def complete(self, **_kwargs):
                return json.dumps({"challenges": [{
                    "targetId": "u1:authority1", "evidenceState": "supported",
                    "challenge": "", "reason": "The words appear in the opinion.",
                    "evidenceRefs": ["s1"], "sourcePassage": "Quoted words.",
                    "opinionStatusState": "missing_material_qualifier",
                    "opinionStatusChallenge": "The passage is from the dissent.",
                    "opinionStatusReason": "It is not the court's holding.",
                    "opinionStatusEvidenceRefs": ["s1"],
                    "opinionStatusPassage": "PAINTER, J., dissenting.",
                }]})

        candidates, _trace = correctness.authority_opponent_stage(
            [{
                "targetId": "u1:authority1", "unitId": "u1",
                "citation": "Sherman v. Pearson, 110 Ohio App.3d 70",
                "proposition": "Sherman held that the claim was permissive.",
                "attributionType": "holding_or_rule", "claimedOpinionStatus": "",
            }],
            [{"id": "s1", "targets": ["u1:authority1"], "title": "Sherman v. Pearson", "snippet": "PAINTER, J., dissenting."}],
            jurisdiction="Ohio", llm_client=AuthorityClient(),
        )
        status = next(item for item in candidates if item["targetId"].endswith(":opinion_status"))
        self.assertEqual(status["issueCode"], "opinion_status_omitted")
        self.assertEqual(status["proposedDisposition"], correctness.MUST_FIX)

    @override_settings(AI_DRAFTING_ENABLED=True)
    def test_adverse_authority_passage_must_exist_in_supplied_source(self):
        class HallucinatingClient:
            def complete(self, **_kwargs):
                return json.dumps({"challenges": [{
                    "targetId": "u1:authority1", "evidenceState": "contradicted",
                    "challenge": "The source says the opposite.", "reason": "Mismatch.",
                    "evidenceRefs": ["s1"],
                    "sourcePassage": "This invented passage is nowhere in the source.",
                }]})

        candidates, _trace = correctness.authority_opponent_stage(
            [{"targetId": "u1:authority1", "unitId": "u1", "citation": "Case, 1 Ohio St. 1", "proposition": "Rule.", "attributionType": "holding_or_rule"}],
            [{"id": "s1", "targets": ["u1:authority1"], "title": "Case", "snippet": "The actual opinion discusses a different subject."}],
            jurisdiction="Ohio", llm_client=HallucinatingClient(),
        )
        self.assertEqual(candidates[0]["proposedDisposition"], correctness.REVIEW)
        self.assertEqual(candidates[0]["evidenceQuote"], "")

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
            def __init__(self):
                self.calls = 0

            def complete(self, **_kwargs):
                self.calls += 1
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
        client = SilentJudge()
        rulings, traces = correctness.judge_stage([candidate], jurisdiction="Ohio", llm_client=client)
        self.assertEqual(rulings, [])
        self.assertEqual(client.calls, 2)
        self.assertTrue(traces[0]["unavailable"])
        self.assertTrue(traces[0]["checkUnavailable"])

    @override_settings(AI_DRAFTING_ENABLED=True)
    def test_incomplete_judge_batch_is_retried_as_a_whole(self):
        class FlakyJudge:
            def __init__(self):
                self.calls = 0

            def complete(self, *, user, **_kwargs):
                self.calls += 1
                if self.calls == 1:
                    return '{"rulings": []}'
                serialized = user.split(
                    "Candidate challenges and the only evidence you may use:\n", 1
                )[1].split("\n\nReturn exactly one ruling", 1)[0]
                candidate = json.loads(serialized)[0]
                return json.dumps({"rulings": [{
                    "candidateId": candidate["candidateId"],
                    "disposition": "review",
                    "reason": "The supplied evidence leaves a concrete concern.",
                    "evidenceRefs": ["u1"],
                    "confidence": "medium",
                }]})

        candidate = {
            "candidateId": "record_support:u1:fact1", "checkId": "cited_record_support",
            "issueCode": "record_support_not_found", "targetId": "u1:fact1", "unitId": "u1",
            "claim": "Notice was served.", "problem": "Support was not found.",
            "reason": "The record excerpt was incomplete.", "briefEvidence": ["u1"],
            "externalEvidence": [], "evidenceQuote": "", "proposedDisposition": correctness.REVIEW,
        }
        client = FlakyJudge()

        rulings, traces = correctness.judge_stage([candidate], jurisdiction="Ohio", llm_client=client)

        self.assertEqual(client.calls, 2)
        self.assertEqual(rulings[0]["disposition"], correctness.REVIEW)
        self.assertFalse(traces[0]["unavailable"])
        self.assertEqual(len(traces[0]["trace"]), 2)

    @override_settings(AI_DRAFTING_ENABLED=True)
    def test_judge_accepts_documented_courtroom_disposition_labels(self):
        class CourtroomJudge:
            def complete(self, **_kwargs):
                return json.dumps({"rulings": [{
                    "candidateId": "rule_elements:test:element",
                    "disposition": "sustained",
                    "reason": "The complete brief clearly omits the required element.",
                    "evidenceRefs": ["u1", "rule-source"],
                    "confidence": "high",
                }]})

        candidate = {
            "candidateId": "rule_elements:test:element", "checkId": "rule_elements",
            "issueCode": "missing_required_element", "targetId": "test:element", "unitId": "u1",
            "claim": "Plead the element.", "problem": "The element is absent.",
            "reason": "The complete brief was reviewed.", "briefEvidence": ["u1"],
            "externalEvidence": ["rule-source"], "evidenceQuote": "Relevant argument.",
            "proposedDisposition": correctness.MUST_FIX,
        }

        rulings, traces = correctness.judge_stage(
            [candidate], jurisdiction="Ohio", llm_client=CourtroomJudge()
        )

        self.assertEqual(rulings[0]["disposition"], correctness.MUST_FIX)
        self.assertFalse(traces[0]["unavailable"])

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
