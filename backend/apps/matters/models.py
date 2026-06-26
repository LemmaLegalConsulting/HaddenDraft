from django.db import models
from django.conf import settings


class Matter(models.Model):
    external_id = models.CharField(max_length=80, unique=True)
    client_name = models.CharField(max_length=255)
    matter_type = models.CharField(max_length=255)
    jurisdiction = models.CharField(max_length=255)
    posture = models.CharField(max_length=255, blank=True)
    risk = models.CharField(max_length=120, blank=True)
    summary = models.TextField(blank=True)
    source_system = models.CharField(max_length=120, default="LegalServer")
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["client_name"]

    def __str__(self):
        return f"{self.external_id} - {self.client_name}"


class MatterFact(models.Model):
    matter = models.ForeignKey(Matter, related_name="facts", on_delete=models.CASCADE)
    slug = models.SlugField(max_length=120)
    title = models.CharField(max_length=255)
    text = models.TextField()
    source_label = models.CharField(max_length=255)
    confidence = models.CharField(max_length=80, default="candidate")
    ai_suggested = models.BooleanField(default=False)
    selected_by_default = models.BooleanField(default=True)

    class Meta:
        unique_together = [("matter", "slug")]
        ordering = ["id"]

    def __str__(self):
        return self.title


class TriageRubric(models.Model):
    slug = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    standard = models.TextField()
    criteria = models.JSONField(default=list, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class TriageAssessment(models.Model):
    matter = models.ForeignKey(Matter, related_name="triage_assessments", on_delete=models.CASCADE)
    rubric = models.ForeignKey(TriageRubric, related_name="assessments", on_delete=models.PROTECT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="triage_assessments",
    )
    case_type = models.CharField(max_length=255, blank=True)
    priority = models.BooleanField(default=False)
    priority_label = models.CharField(max_length=120, blank=True)
    confidence = models.CharField(max_length=80, default="needs_review")
    summary = models.TextField(blank=True)
    reasoning = models.TextField(blank=True)
    matched_criteria = models.JSONField(default=list, blank=True)
    missing_information = models.JSONField(default=list, blank=True)
    evidence = models.JSONField(default=list, blank=True)
    llm_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.matter} - {self.rubric}"
