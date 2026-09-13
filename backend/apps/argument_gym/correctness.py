"""Evidence-bound correctness tests inside the Opponent/Judge/Coach roles.

The tests decide what may be contested.  Opponent may raise only a challenge
about a supplied target, Judge may rule only on that challenge and its supplied
evidence, and Coach may remediate only a sustained or reserved ruling.
"""

import hashlib
import re

from apps.argument_gym import ingestion
from apps.argument_gym.pipeline import Stage, _unit_payload, clean, choice, dumps, known


MUST_FIX = "must_fix"
REVIEW = "review"
PASS = "pass"
DISPOSITIONS = {MUST_FIX, REVIEW, PASS}
RECORD_STATES = {"supported", "contradicted", "not_found", "not_verifiable"}
AUTHORITY_STATES = {"supported", "overstated", "inapplicable", "contradicted", "unverifiable"}


def candidate_id(check_id, target_id):
    return f"{check_id}:{target_id}"


def stable_fingerprint(check_id, target_id):
    """Identity is the named test and target, never generated criticism prose."""
    return hashlib.sha256(f"{check_id}\0{target_id}".encode("utf-8")).hexdigest()


def _sentences(text):
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", str(text or "")) if part.strip()]


def _fallback_record_targets(units):
    targets = []
    for unit in units:
        if unit.get("type") != ingestion.ASSERTED_FACT:
            continue
        for index, sentence in enumerate(_sentences(unit.get("text")), start=1):
            # The fallback does not pretend it can reliably separate compound
            # claims.  Ambiguous candidates are excluded, as the contract says.
            if re.search(r"\b(and|or|but|because|therefore|thus)\b", sentence, re.I):
                continue
            targets.append(
                {
                    "targetId": f"{unit['id']}:fact{index}",
                    "unitId": unit["id"],
                    "claim": sentence[:600],
                    "recordVerifiable": True,
                    "atomic": True,
                    "material": True,
                    "materialBecause": "Presented in the brief's statement of facts.",
                    "citation": "",
                }
            )
    return targets


def record_target_stage(units, argument_map, *, jurisdiction, llm_client=None):
    facts = [unit for unit in units if unit.get("type") == ingestion.ASSERTED_FACT]
    unit_ids = {unit["id"] for unit in facts}

    def parse(payload):
        reported = payload.get("targets")
        if not isinstance(reported, list):
            return []
        targets = []
        seen = set()
        for item in reported:
            if not isinstance(item, dict) or not known(item.get("unitId"), unit_ids):
                continue
            if not all(item.get(key) is True for key in ("recordVerifiable", "atomic", "material")):
                continue
            claim = clean(item.get("claim"), limit=600)
            if not claim:
                continue
            target_id = clean(item.get("targetId"), limit=160) or f"{item['unitId']}:fact{len(targets) + 1}"
            if target_id in seen:
                continue
            seen.add(target_id)
            targets.append(
                {
                    "targetId": target_id,
                    "unitId": item["unitId"],
                    "claim": claim,
                    "recordVerifiable": True,
                    "atomic": True,
                    "material": True,
                    "materialBecause": clean(item.get("materialBecause"), limit=400),
                    "citation": clean(item.get("citation"), limit=250),
                }
            )
        return targets

    return Stage("record_targets", llm_client=llm_client).run(
        prompt_key="argument_gym.record_targets",
        context={
            "jurisdiction": jurisdiction,
            "argument_map": dumps(argument_map),
            "fact_units": dumps(_unit_payload(facts)),
        },
        parse=parse,
        fallback=lambda: _fallback_record_targets(facts),
        temperature=0.1,
    )


def _record_disposition(state, coverage):
    if state == "supported":
        return PASS
    if state == "contradicted":
        return MUST_FIX
    if state == "not_found":
        return MUST_FIX if coverage.get("exhaustive") else REVIEW
    return REVIEW


def record_opponent_stage(targets, excerpts, coverage, *, jurisdiction, llm_client=None):
    target_ids = {target["targetId"] for target in targets}
    material_ids = {excerpt["id"] for excerpt in excerpts}

    def parse(payload):
        reported = payload.get("challenges")
        if not isinstance(reported, list):
            return []
        candidates = []
        for item in reported:
            if not isinstance(item, dict) or not known(item.get("targetId"), target_ids):
                continue
            target = next(target for target in targets if target["targetId"] == item["targetId"])
            state = choice(item.get("evidenceState"), RECORD_STATES, "not_verifiable")
            refs = [value for value in item.get("evidenceRefs") or [] if known(value, material_ids)]
            disposition = _record_disposition(state, coverage)
            # A contradiction without an identified contradictory passage has
            # not carried the Opponent's burden.
            quote = clean(item.get("evidenceQuote"), limit=700)
            if state == "contradicted" and (not refs or not quote):
                disposition = REVIEW
            check_id = "cited_record_support" if target.get("citation") else "uncited_material_fact"
            candidates.append(
                {
                    "candidateId": candidate_id(check_id, target["targetId"]),
                    "checkId": check_id,
                    "issueCode": {
                        "supported": "record_support_confirmed",
                        "contradicted": "contradicted_record_fact",
                        "not_found": "record_support_not_found",
                        "not_verifiable": "record_claim_not_verifiable",
                    }[state],
                    "targetId": target["targetId"],
                    "unitId": target["unitId"],
                    "claim": target["claim"],
                    "problem": clean(item.get("challenge"), limit=1200),
                    "reason": clean(item.get("reason"), limit=800),
                    "briefEvidence": [target["unitId"]],
                    "externalEvidence": refs,
                    "evidenceQuote": quote,
                    "evidenceState": state,
                    "proposedDisposition": disposition,
                    "coverage": coverage,
                }
            )
        return candidates

    return Stage("opponent:record_support", llm_client=llm_client).run(
        prompt_key="argument_gym.record_opponent",
        context={
            "jurisdiction": jurisdiction,
            "targets": dumps(targets),
            "record_excerpts": dumps(excerpts),
            "record_coverage": dumps(coverage),
        },
        parse=parse,
        fallback=lambda: [],
        temperature=0.1,
    )


def authority_targets(argument_map):
    targets = []
    for claim in argument_map:
        proposition = clean(claim.get("proposition"), limit=600)
        for citation in claim.get("citedAuthority") or []:
            normalized = re.sub(r"[^a-z0-9]+", "-", citation.casefold()).strip("-")[:60]
            target_id = f"{claim['unitId']}:authority:{normalized or 'citation'}"
            targets.append(
                {
                    "targetId": target_id,
                    "unitId": claim["unitId"],
                    "proposition": proposition,
                    "citation": citation,
                }
            )
    return targets


def authority_queries(targets, jurisdiction):
    return [
        {
            "query": f'"{target["citation"]}" {jurisdiction}'.strip(),
            "targets": [target["unitId"]],
            "purpose": f'Resolve the cited authority {target["citation"]} and retrieve its relevant source text.',
        }
        for target in targets
    ]


def authority_opponent_stage(targets, legal_sources, *, jurisdiction, llm_client=None):
    target_ids = {target["targetId"] for target in targets}
    source_ids = {source["id"] for source in legal_sources}

    def parse(payload):
        reported = payload.get("challenges")
        if not isinstance(reported, list):
            return []
        candidates = []
        for item in reported:
            if not isinstance(item, dict) or not known(item.get("targetId"), target_ids):
                continue
            target = next(target for target in targets if target["targetId"] == item["targetId"])
            state = choice(item.get("evidenceState"), AUTHORITY_STATES, "unverifiable")
            refs = [str(value) for value in item.get("evidenceRefs") or [] if str(value) in source_ids]
            disposition = PASS if state == "supported" else REVIEW if state == "unverifiable" else MUST_FIX
            quote = clean(item.get("sourcePassage"), limit=900)
            if disposition == MUST_FIX and (not refs or not quote):
                disposition = REVIEW
            candidates.append(
                {
                    "candidateId": candidate_id("authority_support", target["targetId"]),
                    "checkId": "authority_support",
                    "issueCode": f"authority_{state}",
                    "targetId": target["targetId"],
                    "unitId": target["unitId"],
                    "claim": target["proposition"],
                    "problem": clean(item.get("challenge"), limit=1200),
                    "reason": clean(item.get("reason"), limit=800),
                    "briefEvidence": [target["unitId"]],
                    "externalEvidence": refs,
                    "evidenceQuote": quote,
                    "evidenceState": state,
                    "proposedDisposition": disposition,
                    "citation": target["citation"],
                }
            )
        return candidates

    return Stage("opponent:authority_support", llm_client=llm_client).run(
        prompt_key="argument_gym.authority_opponent",
        context={
            "jurisdiction": jurisdiction,
            "targets": dumps(targets),
            "legal_sources": dumps(legal_sources),
        },
        parse=parse,
        fallback=lambda: [
            {
                "candidateId": candidate_id("authority_support", target["targetId"]),
                "checkId": "authority_support",
                "issueCode": "authority_unverifiable",
                "targetId": target["targetId"],
                "unitId": target["unitId"],
                "claim": target["proposition"],
                "problem": f"The cited authority {target['citation']} could not be verified from retrieved source text.",
                "reason": "Unretrieved authority cannot establish a citation defect.",
                "briefEvidence": [target["unitId"]],
                "externalEvidence": [],
                "evidenceQuote": "",
                "evidenceState": "unverifiable",
                "proposedDisposition": REVIEW,
                "citation": target["citation"],
            }
            for target in targets
        ],
        temperature=0.1,
    )


def rule_candidates(audits, units):
    candidates = []
    fallback_unit = next((unit for unit in units if unit.get("type") == ingestion.ARGUMENT), units[0] if units else None)
    if not fallback_unit:
        return candidates
    for audit in audits:
        if audit.get("requiresApplicabilityReview"):
            target_id = f"{audit['slug']}:applicability"
            candidates.append(
                {
                    "candidateId": candidate_id("rule_elements", target_id),
                    "checkId": "rule_elements",
                    "issueCode": "rule_applicability_uncertain",
                    "targetId": target_id,
                    "unitId": fallback_unit["id"],
                    "claim": audit.get("matched", ""),
                    "problem": audit.get("verdict", ""),
                    "reason": "It is uncertain whether the brief invokes this rule.",
                    "briefEvidence": [fallback_unit["id"]],
                    "externalEvidence": [],
                    "evidenceQuote": "",
                    "proposedDisposition": REVIEW,
                }
            )
            continue
        for element in audit.get("elements") or []:
            target_id = f"{audit['slug']}:{element['id']}"
            uncertain = element.get("pled") == "partial" or element.get("supported") in {"partial", "nothing_supplied"}
            if not element.get("unmet"):
                disposition = PASS
                issue_code = "required_element_carried"
            elif uncertain:
                # Unknown wording or absent evidence did not establish a defect.
                # The detailed audit still reports what could not be decided.
                disposition = PASS
                issue_code = "required_element_not_established"
            elif audit.get("verification") != "verified":
                disposition = REVIEW
                issue_code = "required_element_uncertain"
            else:
                disposition = MUST_FIX
                issue_code = "missing_required_element"
            candidates.append(
                {
                    "candidateId": candidate_id("rule_elements", target_id),
                    "checkId": "rule_elements",
                    "issueCode": issue_code,
                    "targetId": target_id,
                    "unitId": fallback_unit["id"],
                    "claim": element.get("requirement") or element.get("label", ""),
                    "problem": element.get("explanation", ""),
                    "reason": audit.get("verdict", ""),
                    "briefEvidence": [fallback_unit["id"]] if element.get("quote") else [],
                    "externalEvidence": [audit.get("sourceUrl") or audit.get("source")]
                    if audit.get("verification") == "verified"
                    else [],
                    "evidenceQuote": element.get("quote", ""),
                    "recordMaterialIds": element.get("materialIds", []),
                    "proposedDisposition": disposition,
                }
            )
    return candidates


def _guard_disposition(candidate, disposition, evidence_refs):
    if disposition != MUST_FIX:
        return disposition
    # Judge verifies the challenge brought; it cannot promote a supported or
    # explicitly uncertain Opponent result into a new defect of its own.
    if candidate.get("proposedDisposition") != MUST_FIX:
        return candidate.get("proposedDisposition", REVIEW)
    if not evidence_refs:
        return REVIEW
    if candidate["checkId"] == "authority_support" and not candidate.get("evidenceQuote"):
        return REVIEW
    if candidate.get("evidenceState") == "contradicted" and not candidate.get("evidenceQuote"):
        return REVIEW
    return disposition


def judge_stage(candidates, *, jurisdiction, llm_client=None):
    """Adjudicate homogeneous batches; Judge cannot create or rank issues."""
    rulings = []
    traces = []
    by_check = {}
    for candidate in candidates:
        by_check.setdefault(candidate["checkId"], []).append(candidate)
    for check_id, batch in by_check.items():
        candidate_ids = {candidate["candidateId"] for candidate in batch}

        def parse(payload, *, _batch=batch, _ids=candidate_ids):
            reported = payload.get("rulings")
            if not isinstance(reported, list):
                return []
            parsed = []
            by_id = {candidate["candidateId"]: candidate for candidate in _batch}
            for item in reported:
                if not isinstance(item, dict) or not known(item.get("candidateId"), _ids):
                    continue
                candidate = by_id[item["candidateId"]]
                refs = [ref for ref in item.get("evidenceRefs") or [] if ref in candidate["briefEvidence"] + candidate["externalEvidence"]]
                disposition = choice(item.get("disposition"), DISPOSITIONS, REVIEW)
                disposition = _guard_disposition(candidate, disposition, refs)
                parsed.append(
                    {
                        **candidate,
                        "disposition": disposition,
                        "judgeReason": clean(item.get("reason"), limit=1000),
                        "evidenceRefs": refs,
                        "confidence": choice(item.get("confidence"), {"high", "medium", "low"}, "low"),
                    }
                )
            return parsed

        batch_rulings, trace = Stage(f"judge:{check_id}", llm_client=llm_client).run(
            prompt_key="argument_gym.correctness_judge",
            context={"jurisdiction": jurisdiction, "check_id": check_id, "candidates": dumps(batch)},
            parse=parse,
            fallback=lambda batch=batch: [
                {
                    **candidate,
                    "disposition": _guard_disposition(
                        candidate,
                        candidate["proposedDisposition"],
                        candidate["briefEvidence"] + candidate["externalEvidence"],
                    ),
                    "judgeReason": candidate.get("reason", ""),
                    "evidenceRefs": candidate["briefEvidence"] + candidate["externalEvidence"],
                    "confidence": "high" if candidate["proposedDisposition"] == PASS else "low",
                }
                for candidate in batch
            ],
            temperature=0.0,
        )
        rulings.extend(batch_rulings)
        traces.append(trace)
    return rulings, traces


def check_results(rulings):
    results = {}
    for ruling in rulings:
        check_id = ruling["checkId"]
        catalog_check_id = "record_support" if check_id in {"cited_record_support", "uncited_material_fact"} else check_id
        bucket = results.setdefault(catalog_check_id, {"findings": [], "tests": []})
        test = {
            "checkId": check_id,
            "issueCode": ruling["issueCode"],
            "targetId": ruling["targetId"],
            "unitId": ruling["unitId"],
            "disposition": ruling["disposition"],
            "claim": ruling.get("claim", ""),
            "problem": ruling.get("problem", ""),
            "briefEvidence": ruling.get("briefEvidence", []),
            "externalEvidence": ruling.get("externalEvidence", []),
            "reason": ruling.get("judgeReason", ""),
            "confidence": ruling.get("confidence", "low"),
        }
        bucket["tests"].append(test)
        if ruling["disposition"] != PASS:
            bucket["findings"].append(
                {
                    "ruleCode": f"{check_id}.{ruling['issueCode']}",
                    "severity": "error" if ruling["disposition"] == MUST_FIX else "warning",
                    "message": ruling.get("problem") or ruling.get("judgeReason") or ruling.get("claim"),
                    "target": {"unitId": ruling["unitId"]},
                    "details": test,
                }
            )
    for result in results.values():
        counts = {MUST_FIX: 0, REVIEW: 0, PASS: 0}
        for test in result["tests"]:
            counts[test["disposition"]] += 1
        result["summary"] = f"{counts[MUST_FIX]} must fix, {counts[REVIEW]} review, {counts[PASS]} passed"
    return results


def summary(rulings, selected_checks=()):
    must_fix = sum(ruling["disposition"] == MUST_FIX for ruling in rulings)
    review = sum(ruling["disposition"] == REVIEW for ruling in rulings)
    by_check = {
        check_id: {MUST_FIX: 0, REVIEW: 0, PASS: 0}
        for check_id in selected_checks
    }
    for ruling in rulings:
        check_id = "record_support" if ruling["checkId"] in {"cited_record_support", "uncited_material_fact"} else ruling["checkId"]
        counts = by_check.setdefault(check_id, {MUST_FIX: 0, REVIEW: 0, PASS: 0})
        counts[ruling["disposition"]] += 1
    labels = {
        "rule_elements": "Rule elements",
        "record_support": "Record support",
        "authority_support": "Authority support",
    }
    lines = []
    for check_id, counts in by_check.items():
        if counts[MUST_FIX] or counts[REVIEW]:
            lines.append(f"{labels.get(check_id, check_id)}: {counts[MUST_FIX]} failure, {counts[REVIEW]} review")
        elif not counts[PASS]:
            lines.append(f"{labels.get(check_id, check_id)}: no eligible targets")
        else:
            lines.append(f"{labels.get(check_id, check_id)}: passed")
    assessment = (
        f"Correctness review completed. {must_fix} must-fix finding{'s' if must_fix != 1 else ''}; "
        f"{review} item{'s' if review != 1 else ''} need attorney review. " + " ".join(lines)
    )
    return {"verdict": "correctness review completed", "assessment": assessment.strip()}


def evaluate_test_runs(samples):
    """Score held-out correctness runs by stable test target, not prose.

    Each sample supplies ``caseId``, ``variant`` (``clean`` or ``mutant``), an
    expected ``checkId`` and ``targetId``, and the persisted ``tests`` from one
    repetition. The caller is responsible for freezing prompts/code and keeping
    development fixtures out of the held-out set.
    """
    mutation = []
    specificity = []
    noise = []
    repeated = {}
    for sample in samples:
        expected = (sample.get("checkId"), sample.get("targetId"))
        tests = sample.get("tests") or []
        by_target = {(test.get("checkId"), test.get("targetId")): test.get("disposition") for test in tests}
        detected = by_target.get(expected) == MUST_FIX
        if sample.get("variant") == "mutant":
            mutation.append(detected)
        elif sample.get("variant") == "clean":
            specificity.append(not detected)
        extra = sum(
            disposition == MUST_FIX and key != expected
            for key, disposition in by_target.items()
        )
        noise.append(extra)
        for key, disposition in by_target.items():
            group = (sample.get("caseId"), sample.get("variant"), *key)
            repeated.setdefault(group, []).append(disposition)
    stability_groups = [values for values in repeated.values() if len(values) > 1]
    stable = [len(set(values)) == 1 for values in stability_groups]

    def rate(values):
        return sum(values) / len(values) if values else None

    return {
        "mutationDetection": {"passed": sum(mutation), "total": len(mutation), "rate": rate(mutation)},
        "matchedSpecificity": {"passed": sum(specificity), "total": len(specificity), "rate": rate(specificity)},
        "stability": {"passed": sum(stable), "total": len(stable), "rate": rate(stable)},
        "noise": {
            "additionalMustFix": sum(noise),
            "runs": len(noise),
            "meanPerRun": sum(noise) / len(noise) if noise else None,
        },
    }
