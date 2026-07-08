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
