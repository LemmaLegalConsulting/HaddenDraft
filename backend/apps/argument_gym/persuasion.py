"""The persuasive communication suite: whether the brief lands, not whether it is right.

Correctness and completeness ask whether a brief is defensible. This asks the
separate question a judge answers first without meaning to: can this be read.
A brief can state the controlling rule, carry every element, and still lose
because the real dispute is not named until page nine, because four authorities
are summarized where one synthesized rule belongs, or because every point is
argued at the same volume so none of them is emphasized.

Twelve dimensions, each a check the author can turn on by itself, answered in
**one** model call. They are not independent: what belongs in the roadmap depends
on what the emphasis should be, and whether the concision is a problem depends on
which passages matter. Twelve separate calls would answer each of them without
the others in view, and cost twelve times as much to do it worse.

Every dimension the author selected is reported, including the ones that come
back well done -- a suite that only lists problems cannot be told apart from a
suite that failed to run. Without a model, every dimension reports itself
*not assessed*, because a judgment call is the one thing a deterministic
fallback cannot fake, and silence here would read as a pass.
"""

from apps.argument_gym import checks as check_catalog
from apps.argument_gym.pipeline import SEVERITY_PREFIX, Stage, _unit_payload, clean, choice, dumps, unit_coverage


STRONG = "strong"
ADEQUATE = "adequate"
WEAK = "weak"
NOT_ASSESSED = "not_assessed"
VERDICTS = {STRONG, ADEQUATE, WEAK}

VERDICT_LABELS = {
    STRONG: "Working",
    ADEQUATE: "Adequate",
    WEAK: "Needs work",
    NOT_ASSESSED: "Not assessed",
}
# A judgment about how a brief reads is a nudge, never a defect: it is the kind
# of finding an advocate is entitled to disagree with. Nothing here is an error.
VERDICT_SEVERITY = {STRONG: "info", ADEQUATE: "info", WEAK: "warning", NOT_ASSESSED: "info"}
# E/W/I1200-1299 belongs to this suite; each dimension keeps its own code so a
# finding stays identifiable across runs.
BASE_RULE_CODE = 1200


def _rule_code(dimension_id, severity):
    slugs = [f"{check_catalog.PERSUASION_PREFIX}{slug}" for slug, _label, _q in check_catalog.PERSUASION_DIMENSIONS]
    offset = slugs.index(dimension_id) if dimension_id in slugs else 99
    return f"{SEVERITY_PREFIX[severity]}{BASE_RULE_CODE + offset}"


def _finding(dimension, result, document_id):
    verdict = result["verdict"]
    severity = VERDICT_SEVERITY[verdict]
    return {
        "findingId": f"persuasion-{document_id}-{dimension['id']}",
        "ruleCode": _rule_code(dimension["id"], severity),
        "severity": severity,
        "outcome": "review" if verdict in {WEAK, NOT_ASSESSED} else "pass",
        "category": "persuasion",
        "target": dimension["label"],
        "location": {
            "view": "json",
            "blockKey": None,
            "sectionLabel": None,
            "lineStart": None,
            "lineEnd": None,
            "excerpt": result.get("quote", ""),
        },
        "message": result["finding"],
        "action": {
            "type": "human_review",
            "label": "Read the passage and decide; this is a judgment about how the brief reads.",
            "payload": {},
        },
        # Even a dimension that reads well is a reading, not a measurement.
        "manualReview": verdict != STRONG,
        "details": {
            "verdict": verdict,
            "verdictLabel": VERDICT_LABELS[verdict],
            "question": dimension["question"],
            "quote": result.get("quote", ""),
            "suggestion": result.get("suggestion", ""),
        },
    }


def _not_assessed(dimensions):
    return [
        {
            "id": dimension["id"],
            "verdict": NOT_ASSESSED,
            "finding": (
                "No model was available for this run, so this was not assessed. "
                "A test that did not run is not a pass."
            ),
            "quote": "",
            "suggestion": "",
        }
        for dimension in dimensions
    ]


def persuasion_stage(dimensions, units, *, brief_title, jurisdiction, matter_summary, argument_map, llm_client=None):
    """One call that answers every selected dimension with the others in view."""
    wanted = {dimension["id"] for dimension in dimensions}

    def parse(payload):
        reported = payload.get("dimensions")
        if not isinstance(reported, list):
            return []
        cleaned = []
        seen = set()
        for item in reported:
            if not isinstance(item, dict) or item.get("id") not in wanted or item["id"] in seen:
                continue
            finding = clean(item.get("finding"), limit=900)
            if not finding:
                continue
            seen.add(item["id"])
            cleaned.append(
                {
                    "id": item["id"],
                    # An unrecognized verdict must not become a passing one.
                    "verdict": choice(item.get("verdict"), VERDICTS, WEAK),
                    "finding": finding,
                    "quote": clean(item.get("quote"), limit=600),
                    "suggestion": clean(item.get("suggestion"), limit=600),
                }
            )
        return cleaned

    return Stage("persuasion", llm_client=llm_client).run(
        prompt_key="argument_gym.persuasion",
        context={
            "brief_title": brief_title,
            "jurisdiction": jurisdiction or "the filing jurisdiction",
            "matter_summary": matter_summary,
            "argument_map": dumps(argument_map),
            "brief_coverage": unit_coverage(units),
            "brief_units": dumps(_unit_payload(units)),
            "dimensions": dumps(dimensions),
        },
        parse=parse,
        fallback=lambda: _not_assessed(dimensions),
        temperature=0.2,
    )


def run_persuasion_review(
    selected_ids,
    units,
    *,
    document_id,
    brief_title,
    jurisdiction="",
    matter_summary="",
    argument_map=(),
    llm_client=None,
):
    """Every selected dimension, keyed by its check id so it joins the other findings.

    The result goes into the run's `check_results` under each dimension's own
    check id, which is what makes a persuasion finding attributable to the test
    the author switched on, exactly like a grammar finding.
    """
    dimensions = check_catalog.persuasion_dimensions(selected_ids)
    if not dimensions:
        return {}, {"stage": "persuasion", "method": "off", "count": 0, "trace": []}

    reported, trace = persuasion_stage(
        dimensions,
        units,
        brief_title=brief_title,
        jurisdiction=jurisdiction,
        matter_summary=matter_summary,
        argument_map=list(argument_map),
        llm_client=llm_client,
    )
    by_id = {item["id"]: item for item in reported}
    results = {}
    for dimension in dimensions:
        # A dimension the model skipped is reported as unassessed rather than
        # dropped: the author selected it, so the run owes them an answer about
        # it either way.
        result = by_id.get(dimension["id"]) or _not_assessed([dimension])[0]
        results[dimension["id"]] = {
            "summary": VERDICT_LABELS[result["verdict"]],
            "findings": [_finding(dimension, result, document_id)],
        }
    return results, trace
