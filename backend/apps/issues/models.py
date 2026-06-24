from django.conf import settings
from django.db import models


class CandidateIssue(models.Model):
    ISSUE_TYPE_CHOICES = [
        ("defense", "Defense"),
        ("counterclaim", "Counterclaim"),
        ("denial", "Denial"),
        ("review_gate", "Review gate"),
        ("missing_fact", "Missing fact"),
    ]
    STATUS_CHOICES = [
        ("candidate", "Candidate"),
        ("needs_review", "Needs review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("inserted", "Inserted into draft"),
    ]

    case_id = models.CharField(max_length=255)
    workflow_run_id = models.CharField(max_length=255, blank=True)
    issue_id = models.SlugField()
    title = models.CharField(max_length=255)
    issue_type = models.CharField(max_length=50, choices=ISSUE_TYPE_CHOICES)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="candidate")
    source_table_key = models.SlugField()
    source_table_version = models.PositiveIntegerField()
    source_row_id = models.SlugField()
    outputs = models.JSONField(default=dict, blank=True)
    supporting_facts = models.JSONField(default=list, blank=True)
    missing_facts = models.JSONField(default=list, blank=True)
    explanation = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["case_id", "created_at", "id"]
        indexes = [
            models.Index(fields=["case_id", "status"]),
            models.Index(fields=["source_table_key", "source_table_version"]),
        ]

    def __str__(self):
        return f"{self.case_id}: {self.title}"
