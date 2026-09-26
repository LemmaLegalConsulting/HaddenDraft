from django.db import models


class DraftingSession(models.Model):
    MODE_CHOICES = [
        ("template_fill", "Fill template — no AI"),
        ("research", "Research"),
        ("draft_from_scratch", "Draft from scratch"),
        ("draft_from_template", "Draft from template"),
        ("advice_letter", "Client advice letter"),
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
    fill_state = models.JSONField(default=dict, blank=True)
    goal = models.TextField(blank=True)
    draft_plan = models.JSONField(default=dict, blank=True)
    missing_information = models.JSONField(default=list, blank=True)
    selected_template_ids = models.JSONField(default=list, blank=True)
    instructions = models.TextField(blank=True)
    # How the advocate set up planning: planningMode, allowMultipleDocuments,
    # clarifyMissingFactsBeforeDraft. Saved so a reopened session asks the
    # same way it was asked before.
    workflow_options = models.JSONField(default=dict, blank=True)
    # Counts saves of what the advocate chose. A write names the revision it
    # was based on and is refused if another tab saved first, rather than
    # silently replacing that tab's work.
    revision = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Saves that record where the workflow is, not what anyone chose.
    UNVERSIONED_FIELDS = frozenset({"status", "updated_at"})

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.mode}: {self.matter}"

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if self.pk and (update_fields is None or not set(update_fields) <= self.UNVERSIONED_FIELDS):
            self.revision = (self.revision or 0) + 1
            if update_fields is not None:
                kwargs["update_fields"] = [*update_fields, "revision"]
        super().save(*args, **kwargs)


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
    # Counts saves of the document's text. An edit names the revision it was
    # made against; an edit made against an older one is refused with 409.
    revision = models.PositiveIntegerField(default=0)
    # Which revision the stored findings describe. Findings for an older
    # revision are stale: they checked text that is no longer there.
    validated_revision = models.PositiveIntegerField(null=True, blank=True)
    validation_summary = models.JSONField(default=dict, blank=True)
    validated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Saves that record a check of the text rather than change it.
    UNVERSIONED_FIELDS = frozenset(
        {"validation_flags", "validated_revision", "validation_summary", "validated_at", "updated_at"}
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if self.pk and (update_fields is None or not set(update_fields) <= self.UNVERSIONED_FIELDS):
            self.revision = (self.revision or 0) + 1
            if update_fields is not None:
                kwargs["update_fields"] = [*update_fields, "revision"]
        super().save(*args, **kwargs)


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


class PackageRelationship(models.Model):
    """How two documents in the same filing package depend on each other.

    A plan can produce a motion, a memorandum, a declaration, and a proposed
    order. They are filed together and have to agree with each other, so the
    relationships between them are recorded rather than inferred at read time.
    """

    RELATIONSHIP_TYPES = [
        ("cites", "Cites"),
        ("authenticates_exhibit", "Authenticates exhibit"),
        ("implements_relief", "Implements relief"),
        ("incorporates", "Incorporates"),
        ("depends_on", "Depends on"),
    ]

    source_document = models.ForeignKey(
        DraftDocument,
        related_name="outgoing_relationships",
        on_delete=models.CASCADE,
    )
    target_document = models.ForeignKey(
        DraftDocument,
        related_name="incoming_relationships",
        on_delete=models.CASCADE,
    )
    relationship_type = models.CharField(max_length=80, choices=RELATIONSHIP_TYPES)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["source_document_id", "relationship_type"]
        unique_together = [("source_document", "target_document", "relationship_type")]

    def __str__(self):
        return f"{self.source_document_id} {self.relationship_type} {self.target_document_id}"


class SourceBinding(models.Model):
    """What a specific version of a component relied on, and in what way.

    Selected sources are a flat list on the session; a binding says which
    component used which source and whether that source may be cited, relied on
    for a fact, or only followed for style.
    """

    ROLE_CHOICES = [
        ("record_evidence", "Record evidence"),
        ("legal_authority", "Legal authority"),
        ("procedural_rule", "Procedural rule"),
        ("example_language", "Example language"),
        ("background_reference", "Background reference"),
    ]
    SUPPORT_TYPE_CHOICES = [
        ("direct", "Direct"),
        ("inference", "Inference"),
        ("background", "Background"),
        ("style_only", "Style only"),
    ]

    component_version = models.ForeignKey(
        ComponentVersion,
        related_name="source_bindings",
        on_delete=models.CASCADE,
    )
    source_key = models.CharField(max_length=255, help_text="Stable identifier of the source within its system.")
    source_kind = models.CharField(max_length=80, blank=True)
    role = models.CharField(max_length=40, choices=ROLE_CHOICES)
    support_type = models.CharField(max_length=40, choices=SUPPORT_TYPE_CHOICES)
    label = models.CharField(max_length=500, blank=True)
    citation = models.CharField(max_length=500, blank=True)
    locator = models.JSONField(
        default=dict,
        blank=True,
        help_text="Where in the source the support is, such as a fact id, URL, or excerpt index.",
    )
    excerpt = models.TextField(blank=True)
    verified = models.BooleanField(
        default=False,
        help_text="Set once the locator and quoted text have been checked against the source.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["component_version_id", "id"]

    def __str__(self):
        return f"{self.role}: {self.label or self.source_key}"


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


class DraftGenerationJob(models.Model):
    """One request to generate a plan's drafts, run off the request thread.

    Generation calls the model once per section and took 75 to 161 seconds for
    the same template on different runs. Held open as a request it outlived
    nginx's timeout: the browser got a CORS-less 504 ("Failed to fetch") while
    the server went on to save the draft, and the obvious retry made a second.
    Now the request returns this row at once and the client polls it.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    STATUS_CHOICES = [
        (PENDING, "Waiting to start"),
        (RUNNING, "Generating"),
        (COMPLETE, "Complete"),
        (FAILED, "Failed"),
    ]

    session = models.ForeignKey(DraftingSession, related_name="generation_jobs", on_delete=models.CASCADE)
    created_by = models.ForeignKey(
        "auth.User", related_name="draft_generation_jobs", null=True, blank=True, on_delete=models.SET_NULL
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    error = models.TextField(blank=True)
    draft_ids = models.JSONField(default=list, blank=True)
    # Supplied by the client that asked. A repeated request with the same key
    # -- a retry after a lost response -- gets this job back, not a second one.
    idempotency_key = models.CharField(max_length=80, blank=True)
    # The session revision and a digest of the plan inputs this job drafted
    # from, so a document can be traced to exactly what was asked for.
    input_revision = models.PositiveIntegerField(null=True, blank=True)
    input_hash = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            # One generation at a time per session, enforced by the database
            # so two tabs pressing Generate at once cannot both start one.
            models.UniqueConstraint(
                fields=["session"],
                condition=models.Q(status__in=["pending", "running"]),
                name="one_active_generation_per_session",
            ),
            models.UniqueConstraint(
                fields=["session", "idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="unique_generation_idempotency_key",
            ),
        ]

    def __str__(self):
        return f"Draft generation {self.pk} for session {self.session_id} ({self.status})"


class TemplateFillJob(models.Model):
    session = models.ForeignKey(DraftingSession, on_delete=models.CASCADE, related_name="fill_jobs")
    created_by = models.ForeignKey("auth.User", null=True, on_delete=models.SET_NULL)
    kind = models.CharField(max_length=20, choices=[("prepare", "Prepare"), ("export", "Export")])
    status = models.CharField(max_length=20, default="pending")
    payload = models.JSONField(default=dict)
    result = models.JSONField(default=dict)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True)
