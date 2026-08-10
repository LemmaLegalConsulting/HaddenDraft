from django.contrib import admin

from apps.caselaw.models import (
    CaseLawArtifact,
    CaseLawChunk,
    CaseLawDateProvenance,
    CaseLawDecision,
    CaseLawImportBatch,
    CaseLawPage,
    CaseLawSearchDocument,
    CaseLawSimilarityEdge,
)


@admin.action(description="Approve selected cases for search")
def approve_for_search(modeladmin, request, queryset):
    queryset.update(approved_for_search=True)


@admin.action(description="Approve selected cases for drafting")
def approve_for_drafting(modeladmin, request, queryset):
    queryset.update(approved_for_drafting=True)


@admin.action(description="Mark selected cases treatment unchecked")
def mark_treatment_unchecked(modeladmin, request, queryset):
    queryset.update(treatment_status="unchecked")


@admin.action(description="Mark selected pages as needing OCR review")
def mark_needs_ocr_review(modeladmin, request, queryset):
    queryset.update(needs_review=True)


class CaseLawArtifactInline(admin.TabularInline):
    model = CaseLawArtifact
    extra = 0
    fields = ("artifact_type", "original_filename", "storage_backend", "storage_key", "content_type", "size_bytes", "sha256")
    readonly_fields = ("storage_key", "size_bytes", "sha256")


class CaseLawDateProvenanceInline(admin.TabularInline):
    """Where each date came from, next to the dates themselves.

    Reviewing an extracted date means reading the passage it came from, so the
    supporting snippet belongs on the decision page rather than a screen away.
    """

    model = CaseLawDateProvenance
    extra = 0
    fields = ("field", "value", "raw_value", "corroborated", "context_label", "match_kind", "matched_text", "snippet", "source_key")
    readonly_fields = ("raw_value", "corroborated", "context_label", "match_kind", "matched_text", "snippet", "source_key")


class CaseLawPageInline(admin.TabularInline):
    model = CaseLawPage
    extra = 0
    fields = ("page_number", "needs_review", "is_handwritten", "ocr_confidence_avg", "ocr_confidence_min")


@admin.register(CaseLawDecision)
class CaseLawDecisionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "court",
        "county",
        "judge",
        "decision_date",
        "publication_status",
        "authority_level",
        "treatment_status",
        "metadata_verified",
        "approved_for_search",
        "approved_for_drafting",
    )
    list_filter = (
        "jurisdiction",
        "county",
        "court",
        "judge",
        "decision_date",
        "publication_status",
        "authority_level",
        "treatment_status",
        "metadata_verified",
        "approved_for_search",
        "approved_for_drafting",
    )
    search_fields = (
        "title",
        "short_title",
        "normalized_title",
        "docket_number",
        "case_number",
        "court",
        "judge",
        "key_facts",
        "outcome",
    )
    actions = [approve_for_search, approve_for_drafting, mark_treatment_unchecked]
    inlines = [CaseLawDateProvenanceInline, CaseLawArtifactInline, CaseLawPageInline]


@admin.register(CaseLawArtifact)
class CaseLawArtifactAdmin(admin.ModelAdmin):
    list_display = ("decision", "artifact_type", "storage_backend", "original_filename", "size_bytes", "created_at")
    list_filter = ("artifact_type", "storage_backend", "content_type")
    search_fields = ("decision__title", "original_filename", "storage_key", "sha256")


@admin.register(CaseLawPage)
class CaseLawPageAdmin(admin.ModelAdmin):
    list_display = ("decision", "page_number", "needs_review", "is_handwritten", "ocr_confidence_avg")
    list_filter = ("needs_review", "is_handwritten")
    search_fields = ("decision__title", "text")
    actions = [mark_needs_ocr_review]


@admin.register(CaseLawChunk)
class CaseLawChunkAdmin(admin.ModelAdmin):
    list_display = ("decision", "chunk_type", "ordinal", "page_start", "page_end")
    list_filter = ("chunk_type", "has_handwriting")
    search_fields = ("decision__title", "text")


@admin.register(CaseLawSearchDocument)
class CaseLawSearchDocumentAdmin(admin.ModelAdmin):
    list_display = ("decision", "document_type", "title", "created_at")
    list_filter = ("document_type",)
    search_fields = ("decision__title", "title", "search_text")


@admin.register(CaseLawImportBatch)
class CaseLawImportBatchAdmin(admin.ModelAdmin):
    list_display = ("source_path", "storage_backend", "status", "total_cases", "imported_cases", "skipped_cases", "failed_cases", "started_at", "finished_at")
    list_filter = ("status", "storage_backend")
    search_fields = ("source_path",)


@admin.register(CaseLawSimilarityEdge)
class CaseLawSimilarityEdgeAdmin(admin.ModelAdmin):
    list_display = ("from_decision", "to_decision", "relation_type", "score", "created_at")
    list_filter = ("relation_type",)
    search_fields = ("from_decision__title", "to_decision__title")


@admin.register(CaseLawDateProvenance)
class CaseLawDateProvenanceAdmin(admin.ModelAdmin):
    list_display = ("decision", "field", "value", "corroborated", "context_label", "match_kind", "matched_text")
    list_filter = ("field", "corroborated", "match_kind", "context_label", "source")
    search_fields = ("decision__title", "raw_value", "matched_text", "snippet")
    readonly_fields = ("decision", "field", "value", "raw_value", "source", "source_key", "source_sha256",
                       "corroborated", "page_number", "matched_text", "match_kind", "context_label", "snippet")
