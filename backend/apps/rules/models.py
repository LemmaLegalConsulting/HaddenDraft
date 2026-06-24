from django.conf import settings
from django.db import models


class RuleAuthority(models.Model):
    authority_type = models.CharField(max_length=50)
    citation = models.CharField(max_length=500, blank=True)
    title = models.CharField(max_length=500, blank=True)
    source_url = models.URLField(blank=True)
    source_ref = models.CharField(max_length=500, blank=True)
    pinpoint = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["authority_type", "citation", "title"]

    def __str__(self):
        return self.citation or self.title or self.authority_type


class DecisionTable(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("proposed", "Proposed"),
        ("approved", "Approved"),
        ("published", "Published"),
        ("retired", "Retired"),
    ]
    HIT_POLICY_CHOICES = [
        ("collect", "Collect"),
        ("first", "First"),
        ("unique", "Unique"),
        ("priority", "Priority"),
    ]
    ENGINE_TYPE_CHOICES = [
        ("dmn_lite", "DMN-lite"),
        ("jsonlogic", "JSONLogic"),
        ("blawx", "Blawx"),
    ]

    key = models.SlugField()
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    workflow_type = models.CharField(max_length=100)
    jurisdiction = models.CharField(max_length=100, blank=True)
    court_scope = models.JSONField(default=list, blank=True)
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="draft")
    hit_policy = models.CharField(max_length=50, choices=HIT_POLICY_CHOICES, default="collect")
    effective_start = models.DateField(null=True, blank=True)
    effective_end = models.DateField(null=True, blank=True)
    authorities = models.ManyToManyField(RuleAuthority, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    change_reason = models.TextField(blank=True)
    engine_type = models.CharField(max_length=50, choices=ENGINE_TYPE_CHOICES, default="dmn_lite")
    external_ruleset_ref = models.CharField(max_length=500, blank=True)

    class Meta:
        unique_together = [("key", "version")]
        ordering = ["key", "-version"]

    def __str__(self):
        return f"{self.key} v{self.version}"


class DecisionRuleRow(models.Model):
    table = models.ForeignKey(DecisionTable, related_name="rows", on_delete=models.CASCADE)
    row_id = models.SlugField()
    label = models.CharField(max_length=255)
    priority = models.IntegerField(default=100)
    conditions = models.JSONField()
    outputs = models.JSONField()
    explanation_template = models.TextField(blank=True)
    enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = [("table", "row_id")]
        ordering = ["priority", "id"]

    def __str__(self):
        return f"{self.table.key}.{self.row_id}"


class DecisionTestCase(models.Model):
    table = models.ForeignKey(DecisionTable, related_name="test_cases", on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    inputs = models.JSONField()
    expected_outputs = models.JSONField()
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["table__key", "name", "id"]

    def __str__(self):
        return f"{self.table}: {self.name}"


class RuleRunLog(models.Model):
    case_id = models.CharField(max_length=255)
    workflow_run_id = models.CharField(max_length=255, blank=True)
    table_key = models.SlugField()
    table_version = models.PositiveIntegerField()
    input_snapshot = models.JSONField()
    matched_rows = models.JSONField(default=list)
    outputs = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["case_id", "workflow_run_id"]),
            models.Index(fields=["table_key", "table_version"]),
        ]

    def __str__(self):
        return f"{self.case_id}: {self.table_key} v{self.table_version}"
