from django.http import JsonResponse

from apps.core.http import api_login_required, json_body, method_not_allowed
from apps.issues.models import CandidateIssue
from apps.issues.services import approve_candidate_issue, reject_candidate_issue
from apps.matters.services import matter_for_user
from apps.rules.serializers import candidate_issue_to_dict, rule_run_log_to_dict
from apps.rules.services import run_decision_table_for_case


def _matter_available(user, matter_id):
    return matter_for_user(user, matter_id) is not None


@api_login_required
def run_case_issue_selection(request, matter_id):
    if request.method != "POST":
        return method_not_allowed(["POST"])
    if not _matter_available(request.user, matter_id):
        return JsonResponse({"error": "Case not found or not available to this user"}, status=404)
    body = json_body(request)
    result = run_decision_table_for_case(
        table_key=body.get("tableKey", "eviction_answer_issue_selection"),
        case_id=matter_id,
        workflow_run_id=body.get("workflowRunId", ""),
        include_unreviewed=body.get("includeUnreviewed", True),
    )
    return JsonResponse(
        {
            "runLog": rule_run_log_to_dict(result["run_log"]),
            "candidateIssues": [candidate_issue_to_dict(issue) for issue in result["candidate_issues"]],
            "facts": result["facts"],
            "matches": result["matches"],
        },
        status=201,
    )


@api_login_required
def case_candidate_issues(request, matter_id):
    if request.method != "GET":
        return method_not_allowed(["GET"])
    if not _matter_available(request.user, matter_id):
        return JsonResponse({"error": "Case not found or not available to this user"}, status=404)
    issues = CandidateIssue.objects.filter(case_id=matter_id).order_by("-created_at", "-id")
    return JsonResponse({"candidateIssues": [candidate_issue_to_dict(issue) for issue in issues]})


@api_login_required
def candidate_issue_review(request, issue_id):
    if request.method != "POST":
        return method_not_allowed(["POST"])
    issue = CandidateIssue.objects.filter(id=issue_id).first()
    if not issue or not _matter_available(request.user, issue.case_id):
        return JsonResponse({"error": "Candidate issue not found"}, status=404)
    body = json_body(request)
    action = body.get("action")
    if action == "approve":
        issue = approve_candidate_issue(issue_id, request.user)
    elif action == "reject":
        issue = reject_candidate_issue(issue_id, request.user, reason=body.get("reason", ""))
    else:
        return JsonResponse({"error": "Unsupported issue review action."}, status=400)
    return JsonResponse({"candidateIssue": candidate_issue_to_dict(issue)})
