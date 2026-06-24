from django.utils import timezone

from apps.issues.models import CandidateIssue


def approve_candidate_issue(issue_id, user):
    issue = CandidateIssue.objects.get(id=issue_id)
    issue.status = "approved"
    issue.reviewed_by = user
    issue.reviewed_at = timezone.now()
    issue.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    return issue


def reject_candidate_issue(issue_id, user, reason=""):
    issue = CandidateIssue.objects.get(id=issue_id)
    issue.status = "rejected"
    issue.rejection_reason = reason
    issue.reviewed_by = user
    issue.reviewed_at = timezone.now()
    issue.save(update_fields=["status", "rejection_reason", "reviewed_by", "reviewed_at"])
    return issue
