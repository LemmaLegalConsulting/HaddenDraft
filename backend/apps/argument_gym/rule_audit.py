"""Auditing the elements of the rules a brief actually invoked.

Citing a rule is a commitment. A brief that names R.C. 1923.04 has undertaken to
establish what that section requires, and an opponent reads the element the brief
skipped before reading anything else. This finds the rules the brief invoked and
asks, element by element, two separate questions: is it pleaded, and is it
supported. An assertion is not support, and the audit never merges the two.

Detection and the pleading check are deterministic. The support check uses a
model where one is available and falls back to term overlap against the case
record, which is weaker and says so.
"""

import re

from apps.argument_gym.pipeline import Stage, brief_text_limit, clean, choice, dumps
from apps.rules.legal_rules import detect_invoked_rules, ensure_legal_rule_profiles, rule_elements
from apps.rules.models import CourtProfile


PLED_VALUES = {"yes", "partial", "no"}
SUPPORT_VALUES = {"yes", "partial", "no", "nothing_supplied"}
APPLICABILITY_VALUES = {"applicable", "not_applicable", "uncertain"}
UNMET_PLED = {"no", "partial"}
UNMET_SUPPORT = {"no", "partial", "nothing_supplied"}


def _terms(text):
    return {term for term in re.findall(r"[a-z0-9]{4,}", str(text or "").casefold())}


def pleading_state(element, brief_text):
    """Whether the brief appears to plead this element, from its own words."""
    patterns = element.get("patterns") or []
    if not patterns:
        # An element with no pattern cannot be decided by looking. Saying
        # "unknown" is the honest answer; saying "no" would invent a defect.
        return "unknown", ""
    for pattern in patterns:
        try:
            match = re.search(pattern, brief_text, flags=re.IGNORECASE)
        except re.error:
            continue
        if match:
            start = max(match.start() - 120, 0)
            return "yes", re.sub(r"\s+", " ", brief_text[start : match.end() + 200]).strip()
    # Maintained patterns are examples of wording, not an exhaustive account of
    # how an advocate can plead an element. A miss cannot establish absence.
    return "unknown", ""


def support_state(element, excerpts):
    """Weak deterministic support check: does any material share this element's words."""
    if not element.get("needsRecordSupport"):
        return "not_required", []
    if not excerpts:
        return "nothing_supplied", []
    element_terms = _terms(f"{element['label']} {element.get('requirement', '')}")
    if not element_terms:
        return "nothing_supplied", []
    matched = [
        excerpt["id"]
        for excerpt in excerpts
        if len(element_terms & _terms(excerpt["text"])) >= max(2, len(element_terms) // 8)
    ]
    return ("partial" if matched else "no"), matched


def _fallback_audit(elements, brief_text, excerpts):
    results = []
    for element in elements:
        pled, quote = pleading_state(element, brief_text)
        supported, material_ids = support_state(element, excerpts)
        if supported == "not_required":
            supported = "yes" if pled == "yes" else "nothing_supplied"
        results.append(
            {
                "id": element["id"],
                "applicability": "uncertain" if element.get("requiredWhen") else "applicable",
                "pled": "yes" if pled == "yes" else ("no" if pled == "no" else "partial"),
                "supported": supported,
                "explanation": (
                    "Read from the brief's own wording and term overlap with the case record. "
                    "No model was available, so this is weaker than a reading."
                ),
                "quote": quote,
                "materialIds": material_ids,
            }
        )
    return results


def audit_rule(rule, elements, brief_text, excerpts, *, jurisdiction, llm_client=None):
    """Audit one invoked rule's elements against the brief and the record."""
    element_ids = {element["id"] for element in elements}

    def parse(payload):
        reported = payload.get("elements")
        if not isinstance(reported, list):
            return []
        cleaned = []
        material_ids = {excerpt["id"] for excerpt in excerpts}
        for item in reported:
            if not isinstance(item, dict) or item.get("id") not in element_ids:
                continue
            element = next(element for element in elements if element["id"] == item["id"])
            cleaned.append(
                {
                    "id": item["id"],
                    "applicability": choice(
                        item.get("applicability"),
                        APPLICABILITY_VALUES,
                        "uncertain" if element.get("requiredWhen") else "applicable",
                    ),
                    "pled": choice(item.get("pled"), PLED_VALUES, "partial"),
                    "supported": choice(item.get("supported"), SUPPORT_VALUES, "nothing_supplied"),
                    "explanation": clean(item.get("explanation"), limit=800),
                    "quote": clean(item.get("quote"), limit=600),
                    "materialIds": [value for value in item.get("materialIds") or [] if value in material_ids],
                }
            )
        return cleaned

    profile = rule["profile"]
    return Stage(f"rule_elements:{profile.slug}", llm_client=llm_client).run(
        prompt_key="argument_gym.rule_elements",
        context={
            "jurisdiction": jurisdiction or "the filing jurisdiction",
            "rule_citation": profile.citation,
            "rule_name": profile.name,
            "rule_summary": profile.summary or "No summary is recorded for this rule.",
            "invoked_by": "a citation" if rule["invokedBy"] == "citation" else "a phrase, without citing the rule",
            "matched": rule["matched"],
            # The whole brief, not its first twelve thousand characters: an
            # element pleaded in section V of a seventy-page brief was reported
            # unpleaded because the audit never saw section V.
            "brief_excerpts": brief_text[: brief_text_limit()],
            "record_excerpts": dumps(excerpts),
            "elements": dumps(
                [
                    {
                        "id": element["id"],
                        "label": element["label"],
                        "requirement": element.get("requirement", ""),
                        "needsRecordSupport": element.get("needsRecordSupport", False),
                        "requiredWhen": element.get("requiredWhen", ""),
                    }
                    for element in elements
                ]
            ),
        },
        parse=parse,
        fallback=lambda: _fallback_audit(elements, brief_text, excerpts),
        temperature=0.1,
    )


def element_severity(element, profile):
    """An unverified element list can only warn; its elements were not checked."""
    declared = element.get("severity", "error")
    if profile.verification != CourtProfile.VERIFIED and declared == "error":
        return "warning"
    return declared


def run_rule_audit(brief_text, excerpts, *, jurisdiction="", llm_client=None, profiles=None):
    """Every rule this brief invoked, with each element's pleading and support state."""
    if profiles is None:
        ensure_legal_rule_profiles()
    invoked = detect_invoked_rules(brief_text, profiles=profiles, jurisdiction=jurisdiction)
    audits = []
    traces = []
    for rule in invoked:
        profile = rule["profile"]
        elements = rule_elements(profile)
        if not elements:
            continue
        # A rule matched only by a phrase has not been invoked, and auditing it
        # is worse than not auditing it: "security deposit" in a recitation of
        # the facts produced a full R.C. 5321.16 audit whose every element came
        # back "nothing supplied", which reads as a defect in a claim the brief
        # never made. The match is still reported -- the advocate may have meant
        # to invoke the rule -- but as a question, not as an audit.
        if rule["invokedBy"] == "phrase":
            audits.append(_unaudited(rule, profile, elements))
            continue
        results, trace = audit_rule(
            rule, elements, brief_text, excerpts, jurisdiction=jurisdiction, llm_client=llm_client
        )
        traces.append(trace)
        by_id = {result["id"]: result for result in results}
        audited = []
        for element in elements:
            result = by_id.get(element["id"], {})
            applicability = result.get(
                "applicability", "uncertain" if element.get("requiredWhen") else "applicable"
            )
            pled = result.get("pled", "partial")
            supported = result.get("supported", "nothing_supplied")
            unmet = applicability == "applicable" and (
                pled in UNMET_PLED or (element.get("needsRecordSupport") and supported in UNMET_SUPPORT)
            )
            audited.append(
                {
                    **element,
                    "pled": pled,
                    "applicability": applicability,
                    "supported": supported,
                    "explanation": result.get("explanation", ""),
                    "quote": result.get("quote", ""),
                    "materialIds": result.get("materialIds", []),
                    "unmet": unmet,
                    "severity": element_severity(element, profile),
                }
            )
        unmet_count = sum(1 for element in audited if element["unmet"])
        audits.append(
            {
                **_identity(rule, profile),
                "audited": True,
                "requiresApplicabilityReview": False,
                "elements": audited,
                "unmetCount": unmet_count,
                "verdict": (
                    "Every element on file is pleaded and supported."
                    if not unmet_count
                    else f"{unmet_count} of {len(audited)} elements need review; unavailable evidence or unrecognized wording does not establish a defect."
                ),
            }
        )
    return audits, traces


def _identity(rule, profile):
    return {
        "slug": profile.slug,
        "name": profile.name,
        "citation": profile.citation,
        "label": profile.label(),
        "summary": profile.summary,
        "verification": profile.verification,
        "source": profile.source,
        "sourceUrl": profile.source_url,
        "invokedBy": rule["invokedBy"],
        "matched": rule["matched"],
        "excerpt": rule["excerpt"],
    }


def _unaudited(rule, profile, elements):
    """A rule the brief used the words of, listed without any verdict about it."""
    return {
        **_identity(rule, profile),
        "audited": False,
        "requiresApplicabilityReview": True,
        # The elements are worth seeing -- they are what the rule would require --
        # but nothing was decided about any of them, so none carries a state.
        "elements": [{**element, "pled": "", "supported": "", "unmet": False, "explanation": "", "quote": "", "materialIds": []} for element in elements],
        "unmetCount": 0,
        "verdict": (
            f"The brief uses the phrase \u201c{rule['matched']}\u201d without citing {profile.citation}. "
            "Nothing was audited: if you are not invoking this rule, there is nothing here to answer."
        ),
    }


def challenges_from_audit(audits, *, limit=4):
    """Turn unmet elements into the same kind of challenge everything else produces.

    A missing element is the cheapest thing an opponent argues, so it belongs in
    the ranked cards, the prep sheet, and the revision plan rather than in a
    separate report nobody reads twice.
    """
    attacks = []
    for audit in audits:
        if audit.get("requiresApplicabilityReview"):
            continue
        for element in audit["elements"]:
            if not element["unmet"]:
                continue
            # Missing input and an inconclusive pattern check remain visible in
            # the audit, but must not become adverse assertions about the brief.
            if element["pled"] == "partial":
                continue
            if element["pled"] == "yes" and element["supported"] in {"nothing_supplied", "partial"}:
                continue
            if element["pled"] == "no":
                problem = f"the brief does not plead it at all"
            elif element["supported"] in {"no", "nothing_supplied"}:
                problem = "the brief asserts it without support in the record"
            else:
                problem = "the brief carries it only partly"
            note = (
                ""
                if audit["verification"] == CourtProfile.VERIFIED
                else " (from an unverified element list, so confirm the element before relying on this)"
            )
            attacks.append(
                {
                    "elementId": element["id"],
                    "ruleSlug": audit["slug"],
                    "severity": element["severity"],
                    "argument": (
                        f"{audit['label']} requires {element['label'].lower()}, and {problem}. "
                        f"{element.get('explanation', '')}"
                    ).strip(),
                    "whyItMatters": (
                        f"The brief invoked {audit['citation']}, so it has taken on this element. "
                        f"An element left open is decided against the party that had to establish it{note}."
                    ),
                    "quote": element.get("quote", ""),
                    "materialIds": element.get("materialIds", []),
                }
            )
    order = {"error": 0, "warning": 1, "info": 2}
    attacks.sort(key=lambda item: order.get(item["severity"], 1))
    return attacks[:limit]
