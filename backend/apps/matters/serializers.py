from apps.sources.connectors.legalserver import _display_value


def _first_display(raw_payload, *keys):
    for key in keys:
        value = _display_value(raw_payload.get(key))
        if value:
            return value
    return ""


def readable_summary(matter):
    summary = matter.summary or ""
    stripped = summary.strip()
    if stripped.startswith("[") or stripped.startswith("{"):
        return _first_display(
            matter.raw_payload or {},
            "case_title",
            "pro_bono_opportunity_summary",
            "case_summary",
            "description",
        )
    return summary


def matter_details(matter):
    raw = matter.raw_payload or {}
    details = [
        ("Case number", _first_display(raw, "case_number", "matter_identification_number", "case_id") or matter.external_id),
        ("Status", matter.posture or _first_display(raw, "case_status", "case_disposition")),
        ("Opened", _first_display(raw, "date_opened", "intake_date", "created_at")),
        ("Legal problem", matter.matter_type),
        ("County", matter.jurisdiction or _first_display(raw, "county_of_dispute", "county_of_residence")),
    ]
    assignments = []
    for assignment in raw.get("assignments") or []:
        if not isinstance(assignment, dict):
            continue
        user = assignment.get("user") if isinstance(assignment.get("user"), dict) else {}
        name = _display_value(user.get("user_name")) or _display_value(assignment.get("name"))
        assignment_type = _display_value(assignment.get("type"))
        if name:
            assignments.append(f"{name}{f' ({assignment_type})' if assignment_type else ''}")
    if assignments:
        details.append(("Assignments", "; ".join(assignments[:4])))
    return [{"label": label, "value": value} for label, value in details if value]


def fact_to_dict(fact):
    return {
        "id": fact.id,
        "slug": fact.slug,
        "title": fact.title,
        "text": fact.text,
        "source": fact.source_label,
        "confidence": fact.confidence,
        "aiSuggested": fact.ai_suggested,
        "selectedByDefault": fact.selected_by_default,
    }


def triage_rubric_to_dict(rubric):
    return {
        "id": rubric.id,
        "slug": rubric.slug,
        "name": rubric.name,
        "description": rubric.description,
        "standard": rubric.standard,
        "criteria": rubric.criteria,
        "active": rubric.active,
    }


def triage_assessment_to_dict(assessment):
    return {
        "id": assessment.id,
        "matterId": assessment.matter.external_id,
        "rubric": triage_rubric_to_dict(assessment.rubric),
        "caseType": assessment.case_type,
        "priority": assessment.priority,
        "priorityLabel": assessment.priority_label,
        "confidence": assessment.confidence,
        "summary": assessment.summary,
        "reasoning": assessment.reasoning,
        "matchedCriteria": assessment.matched_criteria,
        "missingInformation": assessment.missing_information,
        "evidence": assessment.evidence,
        "createdAt": assessment.created_at.isoformat(),
    }


def matter_to_dict(matter, include_facts=False):
    data = {
        "id": matter.external_id,
        "databaseId": matter.id,
        "client": matter.client_name,
        "matter": matter.matter_type,
        "jurisdiction": matter.jurisdiction,
        "posture": matter.posture,
        "risk": matter.risk,
        "summary": readable_summary(matter),
        "details": matter_details(matter),
        "sourceSystem": matter.source_system,
    }
    if include_facts:
        data["facts"] = [fact_to_dict(fact) for fact in matter.facts.all()]
    return data
