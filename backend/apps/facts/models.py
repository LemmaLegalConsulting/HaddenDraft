from django.conf import settings
from django.db import models


class ExtractedFact(models.Model):
    REVIEW_STATUS_CHOICES = [
        ("unreviewed", "Unreviewed"),
        ("needs_review", "Needs review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("corrected", "Corrected"),
    ]
    SOURCE_CHOICES = [
        ("llm", "LLM"),
        ("legalserver", "LegalServer"),
        ("user", "User"),
        ("parser", "Parser"),
        ("deterministic", "Deterministic"),
    ]

    case_id = models.CharField(max_length=255)
    field_path = models.CharField(max_length=255)
    value = models.JSONField(null=True, blank=True)
    source = models.CharField(max_length=50, choices=SOURCE_CHOICES, default="llm")
    confidence = models.FloatField(null=True, blank=True)
    review_status = models.CharField(max_length=50, choices=REVIEW_STATUS_CHOICES, default="unreviewed")
    evidence = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["case_id", "field_path", "id"]
        indexes = [
            models.Index(fields=["case_id", "field_path"]),
            models.Index(fields=["case_id", "review_status"]),
        ]

    def __str__(self):
        return f"{self.case_id}: {self.field_path}"
