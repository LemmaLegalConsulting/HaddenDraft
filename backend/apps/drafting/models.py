from django.db import models


class DraftingSession(models.Model):
    MODE_CHOICES = [
        ("research", "Research"),
        ("draft_from_scratch", "Draft from scratch"),
        ("draft_from_template", "Draft from template"),
    ]
    STATUS_CHOICES = [
        ("setup", "Choose document"),
        ("facts_review", "Review facts"),
        ("support_review", "Review support"),
        ("law_review", "Review legal issues"),
        ("outline_review", "Approve outline"),
        ("draft_review", "Review draft"),
        ("validation", "Validation"),
        ("export", "Export"),
    ]

    mode = models.CharField(max_length=80, choices=MODE_CHOICES)
    matter = models.ForeignKey("matters.Matter", related_name="drafting_sessions", on_delete=models.CASCADE)
    template = models.ForeignKey(
        "templates_app.DocumentTemplate",
        related_name="drafting_sessions",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    status = models.CharField(max_length=80, choices=STATUS_CHOICES, default="setup")
    selected_fact_ids = models.JSONField(default=list, blank=True)
    selected_curated_facts = models.JSONField(default=list, blank=True)
    selected_source_results = models.JSONField(default=list, blank=True)
    selected_block_keys = models.JSONField(default=list, blank=True)
    author_profile = models.JSONField(default=dict, blank=True)
    template_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Values for fields declared by the selected prepared template.",
    )
    instructions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.mode}: {self.matter}"


class DraftDocument(models.Model):
    session = models.ForeignKey(DraftingSession, related_name="drafts", on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    sections = models.JSONField(default=list)
    plain_text = models.TextField()
    editor_state = models.JSONField(default=dict, blank=True)
    validation_flags = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
