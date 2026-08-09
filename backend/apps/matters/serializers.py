from datetime import datetime, time

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

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
        ("Client or household", matter.client_name),
        ("Case title", _first_display(raw, "case_title")),
        ("Case number", _first_display(raw, "case_number", "matter_identification_number", "case_id") or matter.external_id),
        ("Status", matter.posture or _first_display(raw, "case_status", "case_disposition")),
        ("Opened", _first_display(raw, "date_opened", "intake_date", "created_at")),
        ("Legal problem", matter.matter_type),
        ("Court or county", matter.jurisdiction or _first_display(raw, "county_of_dispute", "county_of_residence")),
        ("Priority or risk", matter.risk),
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


def matter_case_number(matter):
    raw = matter.raw_payload or {}
    return _first_display(raw, "case_number", "matter_identification_number", "case_id") or matter.external_id


def _parse_payload_date(value):
    if not value:
        return None
    parsed = parse_datetime(str(value))
    if parsed:
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed
    parsed_date = parse_date(str(value))
    if parsed_date:
        return timezone.make_aware(datetime.combine(parsed_date, time.min))
    return None


# A disposition that means the case is no longer being worked. LegalServer
# spells the open ones "Open" and "Pending"; anything here is finished, and a
# close date settles it regardless of what the disposition says.
CLOSED_DISPOSITIONS = {"closed", "rejected", "withdrawn", "transferred", "denied"}


def matter_opened_at(matter):
    raw = matter.raw_payload or {}
    for key in ("date_opened", "intake_date", "created_at"):
        parsed = _parse_payload_date(_display_value(raw.get(key)) or _raw_date_value(raw.get(key)))
        if parsed:
            return parsed.isoformat()
    return matter.created_at.isoformat() if matter.created_at else ""


def matter_closed_at(matter):
    raw = matter.raw_payload or {}
    for key in ("date_closed", "close_date"):
        parsed = _parse_payload_date(_raw_date_value(raw.get(key)) or _display_value(raw.get(key)))
        if parsed:
            return parsed.isoformat()
    return ""


def _raw_date_value(value):
    """LegalServer wraps dates as {"raw_value": ..., "text_value": "N/A"}."""
    if isinstance(value, dict):
        return value.get("raw_value") or ""
    return ""


def matter_is_open(matter):
    """Whether a case is still being worked.

    A case with no disposition at all is open: quick cases carry none, and a
    LegalServer matter that has not been dispositioned has not been closed.
    """
    if matter_closed_at(matter):
        return False
    raw = matter.raw_payload or {}
    disposition = _first_display(raw, "case_disposition", "case_status").strip().casefold()
    return disposition not in CLOSED_DISPOSITIONS


def matter_case_status(matter):
    raw = matter.raw_payload or {}
    return _first_display(raw, "case_disposition", "case_status") or ("Open" if matter_is_open(matter) else "Closed")


def matter_last_activity_at(matter):
    raw = matter.raw_payload or {}
    for key in (
        "last_activity_at",
        "last_activity_date",
        "last_case_activity_date",
        "last_note_date",
        "date_last_modified",
        "updated_at",
    ):
        parsed = _parse_payload_date(_display_value(raw.get(key)))
        if parsed:
            return parsed.isoformat()
    # A quick case carries no LegalServer activity dates, and sorting it to the
    # bottom would bury the case an advocate created a minute ago; the row's own
    # timestamp is the last thing that happened to it. A LegalServer matter that
    # reports no activity date gets none: our sync time says when we last
    # fetched the case, not when anyone last worked it.
    if matter.source_system.casefold() == "legalserver":
        return ""
    return matter.updated_at.isoformat() if matter.updated_at else ""


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


def matter_assigned_to_viewer(matter, *, viewer=None, viewer_identifier=""):
    """Whether the signed-in advocate is on this case.

    A quick case has no LegalServer assignments, so the person who created it is
    the one working it; filtering to "assigned to me" must not hide their own
    notes-and-files cases.
    """
    raw = matter.raw_payload or {}
    viewer_id = getattr(viewer, "id", None)
    if viewer_id is not None and raw.get("created_by_user_id") == viewer_id:
        return True
    if not viewer_identifier:
        return False
    # Imported here because services imports this module for serialization.
    from apps.matters.services import payload_matches_legalserver_identifier

    return payload_matches_legalserver_identifier(raw, viewer_identifier)


def matter_to_dict(matter, include_facts=False, *, legalserver_client=None, viewer=None, viewer_identifier=""):
    raw = matter.raw_payload or {}
    title = _first_display(raw, "case_title") or matter.client_name
    data = {
        "id": matter.external_id,
        "databaseId": matter.id,
        "title": title,
        "client": matter.client_name,
        "caseNumber": matter_case_number(matter),
        "matter": matter.matter_type,
        "jurisdiction": matter.jurisdiction,
        "posture": matter.posture,
        "risk": matter.risk,
        "summary": readable_summary(matter),
        "details": matter_details(matter),
        "lastActivityAt": matter_last_activity_at(matter),
        "openedAt": matter_opened_at(matter),
        "closedAt": matter_closed_at(matter),
        "isOpen": matter_is_open(matter),
        "caseStatus": matter_case_status(matter),
        "legalProblemCode": _first_display(raw, "legal_problem_code") or matter.matter_type,
        "legalProblemCategory": _first_display(raw, "legal_problem_category"),
        "sourceSystem": matter.source_system,
    }
    if viewer is not None or viewer_identifier:
        data["assignedToViewer"] = matter_assigned_to_viewer(
            matter, viewer=viewer, viewer_identifier=viewer_identifier
        )
    if matter.source_system.casefold() == "legalserver":
        if legalserver_client is None:
            from apps.sources.connectors.legalserver import LegalServerClient

            legalserver_client = LegalServerClient()
        profile_url = getattr(legalserver_client, "matter_profile_url", None)
        profile_payload = {**raw}
        profile_payload.setdefault("case_number", matter_case_number(matter))
        data["legalserverUrl"] = profile_url(profile_payload) if profile_url else ""
    if include_facts:
        data["facts"] = [fact_to_dict(fact) for fact in matter.facts.all()]
    return data
