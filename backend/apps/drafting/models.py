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
    goal = models.TextField(blank=True)
    draft_plan = models.JSONField(default=dict, blank=True)
    missing_information = models.JSONField(default=list, blank=True)
    selected_template_ids = models.JSONField(default=list, blank=True)
    instructions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.mode}: {self.matter}"


class DraftDocument(models.Model):
    session = models.ForeignKey(DraftingSession, related_name="drafts", on_delete=models.CASCADE)
    template = models.ForeignKey(
        "templates_app.DocumentTemplate",
        related_name="drafts",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text=(
            "Template this document was generated from. A session can produce several "
            "documents from different templates, so export renders from this, not the session."
        ),
    )
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


class DocumentComponent(models.Model):
    """A durable, individually addressable part of a draft document.

    `DraftDocument.sections` stays the shape the editor and export path read.
    A component is the same section as a domain object: it keeps its identity,
    history, and review state when the section JSON is rewritten.
    """

    document = models.ForeignKey(DraftDocument, related_name="components", on_delete=models.CASCADE)
    stable_key = models.CharField(
        max_length=160,
        help_text="Identity of this component within the document, normally the template block key.",
    )
    component_type = models.CharField(max_length=80, blank=True)
    label = models.CharField(max_length=255, blank=True)
    position = models.PositiveIntegerField(default=0)
    parent = models.ForeignKey("self", related_name="children", null=True, blank=True, on_delete=models.CASCADE)
    removed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Set when the component left the document. History is kept rather than deleted.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "id"]
        unique_together = [("document", "stable_key")]

    def __str__(self):
        return f"{self.document_id}:{self.stable_key}"

    @property
    def current_version(self):
        return self.versions.order_by("-sequence").first()


class ComponentVersion(models.Model):
    ORIGIN_CHOICES = [
        ("template", "Template"),
        ("ai", "AI generation"),
        ("human", "Human edit"),
        ("validation_repair", "Validation repair"),
        ("rollback", "Rollback"),
    ]

    component = models.ForeignKey(DocumentComponent, related_name="versions", on_delete=models.CASCADE)
    sequence = models.PositiveIntegerField()
    body = models.TextField(blank=True)
    structured_content = models.JSONField(
        default=dict,
        blank=True,
        help_text="Section fields other than key, label, and body, such as sources and formatting.",
    )
    origin = models.CharField(max_length=40, choices=ORIGIN_CHOICES, default="template")
    instruction = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["component_id", "sequence"]
        unique_together = [("component", "sequence")]

    def __str__(self):
        return f"{self.component}@{self.sequence}"


class DraftOperation(models.Model):
    """A proposed, reviewable change to one part of a document.

    Changes are described before they are made, so a reviewer (or a later
    model-driven stage) can see exactly what would move, and so an applied
    change keeps a record of what it replaced.
    """

    OPERATION_TYPES = [
        ("replace_component", "Replace component"),
        ("insert_component", "Insert component"),
        ("delete_component", "Delete component"),
        ("move_component", "Move component"),
        ("revert_component", "Revert component to an earlier version"),
    ]
    STATUS_CHOICES = [
        ("proposed", "Proposed"),
        ("applied", "Applied"),
        ("rejected", "Rejected"),
    ]

    document = models.ForeignKey(DraftDocument, related_name="operations", on_delete=models.CASCADE)
    operation_type = models.CharField(max_length=60, choices=OPERATION_TYPES)
    target_component = models.ForeignKey(
        DocumentComponent,
        related_name="operations",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    payload = models.JSONField(default=dict, blank=True)
    rationale = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="proposed")
    origin = models.CharField(max_length=40, choices=ComponentVersion.ORIGIN_CHOICES, default="human")
    decision_note = models.TextField(blank=True)
    result = models.JSONField(default=dict, blank=True)
    requested_by = models.ForeignKey(
        "auth.User",
        related_name="draft_operations",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.operation_type} on {self.document_id} ({self.status})"
