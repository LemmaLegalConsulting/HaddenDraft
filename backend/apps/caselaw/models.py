from django.db import models


class CaseLawImportBatch(models.Model):
    source_path = models.TextField()
    storage_backend = models.CharField(max_length=80)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=40, default="running")
    total_files = models.PositiveIntegerField(default=0)
    total_cases = models.PositiveIntegerField(default=0)
    imported_cases = models.PositiveIntegerField(default=0)
    skipped_cases = models.PositiveIntegerField(default=0)
    failed_cases = models.PositiveIntegerField(default=0)
    report = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.source_path} ({self.status})"


class CaseLawDecision(models.Model):
    title = models.CharField(max_length=500)
    short_title = models.CharField(max_length=500, blank=True)
    normalized_title = models.CharField(max_length=500, blank=True)

    docket_number = models.CharField(max_length=255, blank=True)
    case_number = models.CharField(max_length=255, blank=True)
    external_source_id = models.CharField(max_length=255, blank=True)

    court = models.CharField(max_length=255, blank=True)
    court_division = models.CharField(max_length=255, blank=True)
    county = models.CharField(max_length=255, blank=True)
    jurisdiction = models.CharField(max_length=120, blank=True)
    judge = models.CharField(max_length=255, blank=True)
    magistrate = models.CharField(max_length=255, blank=True)

    parties = models.JSONField(default=list, blank=True)
    party_roles = models.JSONField(default=list, blank=True)

    decision_date = models.DateField(null=True, blank=True)
    entry_date = models.DateField(null=True, blank=True)
    filed_date = models.DateField(null=True, blank=True)
    hearing_date = models.DateField(null=True, blank=True)
    service_date = models.DateField(null=True, blank=True)
    finality_date = models.DateField(null=True, blank=True)

    appeal_deadline = models.DateField(null=True, blank=True)
    appeal_filed_date = models.DateField(null=True, blank=True)
    vacated_date = models.DateField(null=True, blank=True)
    reversed_date = models.DateField(null=True, blank=True)
    superseded_date = models.DateField(null=True, blank=True)

    publication_status = models.CharField(max_length=80, default="unpublished")
    precedential_status = models.CharField(max_length=120, blank=True)
    authority_level = models.CharField(max_length=120, blank=True)
    court_level = models.CharField(max_length=120, blank=True)

    is_unpublished = models.BooleanField(default=True)
    is_trial_court = models.BooleanField(default=False)
    is_administrative = models.BooleanField(default=False)
    is_persuasive_only = models.BooleanField(default=True)

    citation_string = models.CharField(max_length=500, blank=True)
    parallel_citations = models.JSONField(default=list, blank=True)
    westlaw_lexis_citation_if_any = models.CharField(max_length=500, blank=True)

    case_type = models.CharField(max_length=255, blank=True)
    claim_type = models.CharField(max_length=255, blank=True)
    motion_type = models.CharField(max_length=255, blank=True)
    procedural_stage = models.CharField(max_length=255, blank=True)
    posture = models.TextField(blank=True)
    appeal_status = models.CharField(max_length=120, blank=True)
    tenant_landlord_role = models.CharField(max_length=120, blank=True)
    subsidy_program = models.CharField(max_length=255, blank=True)
    housing_type = models.CharField(max_length=255, blank=True)

    issues = models.JSONField(default=list, blank=True)
    holdings = models.JSONField(default=list, blank=True)
    rules_applied = models.JSONField(default=list, blank=True)
    statutes_cited = models.JSONField(default=list, blank=True)
    regulations_cited = models.JSONField(default=list, blank=True)
    cases_cited = models.JSONField(default=list, blank=True)
    # Researcher-phrased retrieval keywords ("deficient notice", "improper
    # service") that rarely appear verbatim in opinion text.
    search_keywords = models.JSONField(default=list, blank=True)

    key_facts = models.TextField(blank=True)
    outcome = models.TextField(blank=True)
    relief_granted = models.TextField(blank=True)
    relief_denied = models.TextField(blank=True)
    disposition = models.TextField(blank=True)

    treatment_status = models.CharField(max_length=80, default="unchecked")
    treatment_notes = models.TextField(blank=True)
    negative_treatment_type = models.CharField(max_length=120, blank=True)
    negative_treatment_source = models.TextField(blank=True)
    related_appeal_case = models.TextField(blank=True)
    later_history = models.TextField(blank=True)
    overruled_by = models.TextField(blank=True)
    distinguished_by = models.JSONField(default=list, blank=True)
    followed_by = models.JSONField(default=list, blank=True)
    cited_by = models.JSONField(default=list, blank=True)

    last_treatment_checked_at = models.DateTimeField(null=True, blank=True)
    last_currentness_reviewed_by = models.CharField(max_length=255, blank=True)
    last_currentness_reviewed_at = models.DateTimeField(null=True, blank=True)

    original_filename = models.CharField(max_length=500, blank=True)
    source_sha256 = models.CharField(max_length=64, unique=True)
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    mime_type = models.CharField(max_length=120, blank=True)

    has_embedded_text = models.BooleanField(default=False)
    has_ocr_layer = models.BooleanField(default=False)

    metadata_source = models.CharField(max_length=80, default="unverified_json")
    metadata_verified = models.BooleanField(default=False)

    approved_for_search = models.BooleanField(default=True)
    approved_for_drafting = models.BooleanField(default=False)

    imported_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-decision_date", "title"]
        indexes = [
            models.Index(fields=["decision_date"]),
            models.Index(fields=["entry_date"]),
            models.Index(fields=["court"]),
            models.Index(fields=["county"]),
            models.Index(fields=["jurisdiction"]),
            models.Index(fields=["judge"]),
            models.Index(fields=["publication_status"]),
            models.Index(fields=["authority_level"]),
            models.Index(fields=["treatment_status"]),
            models.Index(fields=["approved_for_search"]),
        ]

    def __str__(self):
        return self.title


class CaseLawArtifact(models.Model):
    decision = models.ForeignKey(CaseLawDecision, on_delete=models.CASCADE, related_name="artifacts")
    artifact_type = models.CharField(max_length=80)
    original_filename = models.CharField(max_length=500, blank=True)
    storage_backend = models.CharField(max_length=80)
    storage_key = models.TextField()
    content_type = models.CharField(max_length=120, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["artifact_type", "original_filename"]
        unique_together = [("decision", "artifact_type", "storage_key")]

    def __str__(self):
        return f"{self.decision}: {self.artifact_type}"


class CaseLawPage(models.Model):
    decision = models.ForeignKey(CaseLawDecision, on_delete=models.CASCADE, related_name="pages")
    page_number = models.PositiveIntegerField()
    text = models.TextField(blank=True)
    ocr_confidence_avg = models.FloatField(null=True, blank=True)
    ocr_confidence_min = models.FloatField(null=True, blank=True)
    is_handwritten = models.BooleanField(default=False)
    needs_review = models.BooleanField(default=False)

    class Meta:
        ordering = ["decision_id", "page_number"]
        unique_together = [("decision", "page_number")]

    def __str__(self):
        return f"{self.decision} p. {self.page_number}"


class CaseLawChunk(models.Model):
    decision = models.ForeignKey(CaseLawDecision, on_delete=models.CASCADE, related_name="chunks")
    chunk_type = models.CharField(max_length=80, default="body")
    page_start = models.PositiveIntegerField(default=1)
    page_end = models.PositiveIntegerField(default=1)
    text = models.TextField()
    ordinal = models.PositiveIntegerField(default=0)
    ocr_confidence_min = models.FloatField(null=True, blank=True)
    has_handwriting = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["decision_id", "ordinal"]
        unique_together = [("decision", "chunk_type", "ordinal")]

    def __str__(self):
        return f"{self.decision} chunk {self.ordinal}"


class CaseLawSearchDocument(models.Model):
    decision = models.ForeignKey(CaseLawDecision, on_delete=models.CASCADE, related_name="search_documents")
    chunk = models.ForeignKey(CaseLawChunk, on_delete=models.CASCADE, null=True, blank=True)
    document_type = models.CharField(max_length=80)
    title = models.CharField(max_length=500, blank=True)
    search_text = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["decision_id", "document_type", "id"]
        indexes = [
            models.Index(fields=["decision", "document_type"]),
            models.Index(fields=["document_type"]),
        ]

    def __str__(self):
        return f"{self.decision}: {self.document_type}"


class CaseLawSimilarityEdge(models.Model):
    from_decision = models.ForeignKey(CaseLawDecision, on_delete=models.CASCADE, related_name="similar_from")
    to_decision = models.ForeignKey(CaseLawDecision, on_delete=models.CASCADE, related_name="similar_to")
    relation_type = models.CharField(max_length=80, default="similar")
    score = models.FloatField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-score"]
        unique_together = [("from_decision", "to_decision", "relation_type")]

    def __str__(self):
        return f"{self.from_decision} -> {self.to_decision}"
