from apps.facts.services import UNREVIEWED_STATUSES, build_fact_snapshot, get_fact_status_map
from apps.issues.models import CandidateIssue
from apps.rules.engine import evaluate_table
from apps.rules.models import DecisionTable, RuleRunLog


def latest_runnable_table(table_key: str):
    return (
        DecisionTable.objects
        .filter(key=table_key, status="published")
        .order_by("-version")
        .first()
    )


def run_decision_table_for_case(
    *,
    table_key: str,
    case_id: str,
    workflow_run_id: str = "",
    include_unreviewed: bool = True,
):
    table = latest_runnable_table(table_key)
    if not table:
        raise ValueError(f"No published decision table found for {table_key}")

    facts = build_fact_snapshot(case_id, include_unreviewed=include_unreviewed)
    fact_statuses = get_fact_status_map(case_id)
    matches = evaluate_table(table, facts)

    run_log = RuleRunLog.objects.create(
        case_id=case_id,
        workflow_run_id=workflow_run_id,
        table_key=table.key,
        table_version=table.version,
        input_snapshot=facts,
        matched_rows=[match["row_id"] for match in matches],
        outputs=[match["outputs"] for match in matches],
    )

    candidate_issues = []
    for match in matches:
        outputs = match["outputs"]
        supporting_facts = match.get("condition_fields", [])
        depends_on_unreviewed = any(fact_statuses.get(field) in UNREVIEWED_STATUSES for field in supporting_facts)
        status = "needs_review" if outputs.get("review_required", True) or depends_on_unreviewed else "candidate"
        issue = CandidateIssue.objects.create(
            case_id=case_id,
            workflow_run_id=workflow_run_id,
            issue_id=outputs["candidate_issue"],
            title=outputs.get("title", outputs["candidate_issue"]),
            issue_type=outputs.get("issue_type", "defense"),
            status=status,
            source_table_key=table.key,
            source_table_version=table.version,
            source_row_id=match["row_id"],
            outputs=outputs,
            supporting_facts=supporting_facts,
            missing_facts=outputs.get("missing_facts", []),
            explanation=match.get("explanation", ""),
        )
        candidate_issues.append(issue)

    return {
        "run_log": run_log,
        "candidate_issues": candidate_issues,
        "facts": facts,
        "matches": matches,
    }


def run_decision_test_case(test_case):
    matches = evaluate_table(test_case.table, test_case.inputs)
    actual_outputs = [match["outputs"] for match in matches]
    expected_outputs = test_case.expected_outputs
    if isinstance(expected_outputs, dict):
        expected_outputs = [expected_outputs]
    return {
        "test_case": test_case,
        "passed": actual_outputs == expected_outputs,
        "actual_outputs": actual_outputs,
        "expected_outputs": expected_outputs,
    }
