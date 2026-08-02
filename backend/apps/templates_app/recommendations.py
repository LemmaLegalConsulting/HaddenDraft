import re


NEGATIVE_CONFLICT_TERMS = {"dismissal", "dismiss", "judgment", "merits"}


def _terms(value):
    return set(re.findall(r"[a-z0-9']+", (value or "").casefold()))


def _contains_phrase(haystack, needle):
    return needle.casefold() in haystack.casefold()


def _negative_conflicts(goal, negative_goal):
    goal_terms = _terms(goal)
    negative = (negative_goal or "").casefold()
    for negative_term in NEGATIVE_CONFLICT_TERMS:
        if negative_term in negative and negative_term in goal_terms:
            return True
    return False


def _fact_text(matter, facts):
    parts = [
        getattr(matter, "summary", "") or "",
        getattr(matter, "posture", "") or "",
        getattr(matter, "matter_type", "") or "",
    ]
    for fact in facts or []:
        parts.append(getattr(fact, "text", "") or (fact.get("text", "") if isinstance(fact, dict) else ""))
    return " ".join(parts)


def _trigger_hits(trigger, haystack, haystack_terms):
    """A trigger fires on its phrase, or on enough of its distinctive words.

    Triggers are written as sentences an advocate would say ("landlord accepted
    rent after serving the 3-day notice"), not as keywords, so an exact phrase
    match is rare. Requiring most of the content words keeps "accepted rent
    after the notice" matching while stopping every section that mentions rent.
    """
    if _contains_phrase(haystack, trigger):
        return 1.0
    terms = {term for term in _terms(trigger) if len(term) > 3}
    if not terms:
        return 0.0
    overlap = terms & haystack_terms
    ratio = len(overlap) / len(terms)
    return ratio if ratio >= 0.6 else 0.0


def recommend_advice_sections(
    sections,
    matter,
    *,
    goal="",
    facts=None,
    conditions=None,
    region="",
    limit=6,
    include_unreviewed=False,
):
    """Rank advice-letter sections for one tenant.

    Scores the same way template recommendation does -- explicit signals first,
    reasons recorded alongside every score -- so an advocate can see why a
    section was offered instead of being handed an opaque list.

    Sections that are not `ready` are withheld by default. A section still
    carrying tracked changes or drafted by AI should not reach a client because
    it happened to match a keyword.
    """
    conditions = {key for key, value in (conditions or {}).items() if value}
    haystack = " ".join([goal or "", _fact_text(matter, facts)])
    haystack_terms = _terms(haystack)
    region = (region or "").upper()

    scored = []
    for section in sections:
        if not include_unreviewed and getattr(section, "status", "ready") != "ready":
            continue
        if getattr(section, "role", "body") != "body":
            continue
        section_region = (getattr(section, "region", "") or "").upper()
        if region and section_region and section_region != region:
            continue

        hints = getattr(section, "selection_hints", None) or {}
        missing = [
            requirement
            for requirement in hints.get("requires", []) or []
            if requirement not in conditions
        ]

        score = 0
        reasons = []
        best_trigger = 0.0
        for trigger in hints.get("triggers", []) or []:
            hit = _trigger_hits(trigger, haystack, haystack_terms)
            if hit > best_trigger:
                best_trigger = hit
                if hit >= 1.0:
                    reasons = [f"Case facts state: {trigger}"] + reasons
                else:
                    reasons.append(f"Case facts look like: {trigger}")
        if best_trigger:
            score += int(60 * best_trigger)

        satisfied = [
            requirement
            for requirement in hints.get("requires", []) or []
            if requirement in conditions
        ]
        if satisfied:
            score += 10 * len(satisfied)
            reasons.append("Case meets: " + ", ".join(satisfied))
        if missing:
            # Offered, but ranked below anything whose preconditions are met.
            score -= 25 * len(missing)
            reasons.append("Not confirmed: " + ", ".join(missing))
        if section_region and section_region == region:
            score += 8
            reasons.append(f"Written for {section_region}.")
        if hints.get("usually_paired"):
            score += 5
            reasons.append("Usually included with any pro se advice.")

        if score <= 0 and not best_trigger:
            continue
        scored.append(
            {
                "section": section,
                "score": score,
                "reasons": reasons,
                "unmetConditions": missing,
                "summary": hints.get("summary", ""),
            }
        )

    scored.sort(key=lambda item: (-item["score"], getattr(item["section"], "title", "")))
    chosen = _drop_conflicts(scored)
    return chosen[:limit]


def _drop_conflicts(scored):
    """Keep the better of two sections that contradict each other."""
    kept = []
    excluded = set()
    for entry in scored:
        slug = getattr(entry["section"], "slug", "")
        if slug in excluded:
            continue
        kept.append(entry)
        hints = getattr(entry["section"], "selection_hints", None) or {}
        excluded.update(hints.get("excludes", []) or [])
    return kept


def recommend_templates(goal, matter, templates, *, limit=3):
    """Rank templates with explicit goal/alias matches before any AI ranking."""
    goal_text = goal or getattr(matter, "summary", "") or ""
    goal_terms = _terms(goal_text)
    jurisdiction = (getattr(matter, "jurisdiction", "") or "").casefold()
    recommendations = []
    for template in templates:
        if _negative_conflicts(goal_text, template.negative_goal):
            continue
        score = 0
        reasons = []
        aliases = template.aliases or []
        for alias in aliases:
            if _contains_phrase(goal_text, alias):
                score += 60
                reasons.append(f"Goal matches alias: {alias}")
                break
        template_goal_terms = _terms(template.goal or template.description or template.title)
        overlap = goal_terms.intersection(template_goal_terms)
        if overlap:
            score += min(30, 8 * len(overlap))
            reasons.append("Goal language matches template purpose.")
        if jurisdiction and jurisdiction in (template.jurisdiction or "").casefold():
            score += 12
            reasons.append("Jurisdiction matches the case.")
        if template.kind and template.kind.replace("_", " ") in goal_text.casefold():
            score += 8
            reasons.append("Document type matches the request.")
        if not score:
            score = 1
            reasons.append("Available active template.")
        recommendations.append({"template": template, "score": score, "reasons": reasons})
    recommendations.sort(key=lambda item: (-item["score"], item["template"].title))
    return recommendations[:limit]
