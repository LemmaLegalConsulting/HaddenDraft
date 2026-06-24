def candidate_issue_to_dict(issue):
    return {
        "id": issue.id,
        "caseId": issue.case_id,
        "workflowRunId": issue.workflow_run_id,
        "issueId": issue.issue_id,
        "title": issue.title,
        "issueType": issue.issue_type,
        "status": issue.status,
        "sourceTableKey": issue.source_table_key,
        "sourceTableVersion": issue.source_table_version,
        "sourceRowId": issue.source_row_id,
        "outputs": issue.outputs,
        "supportingFacts": issue.supporting_facts,
        "missingFacts": issue.missing_facts,
        "explanation": issue.explanation,
        "createdAt": issue.created_at.isoformat(),
        "reviewedAt": issue.reviewed_at.isoformat() if issue.reviewed_at else None,
    }


def rule_run_log_to_dict(run_log):
    return {
        "id": run_log.id,
        "caseId": run_log.case_id,
        "workflowRunId": run_log.workflow_run_id,
        "tableKey": run_log.table_key,
        "tableVersion": run_log.table_version,
        "matchedRows": run_log.matched_rows,
        "outputs": run_log.outputs,
        "createdAt": run_log.created_at.isoformat(),
    }
