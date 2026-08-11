from django.contrib import admin

from apps.matters.models import LegalServerDelivery, Matter, MatterFact, TriageAssessment, TriageRubric


class MatterFactInline(admin.TabularInline):
    model = MatterFact
    extra = 0


class TriageAssessmentInline(admin.TabularInline):
    model = TriageAssessment
    extra = 0
    readonly_fields = (
        "rubric",
        "case_type",
        "priority",
        "priority_label",
        "confidence",
        "summary",
        "created_at",
    )
    can_delete = False


@admin.register(Matter)
class MatterAdmin(admin.ModelAdmin):
    list_display = ("external_id", "client_name", "matter_type", "jurisdiction", "posture", "risk")
    search_fields = ("external_id", "client_name", "matter_type", "summary")
    inlines = [MatterFactInline, TriageAssessmentInline]


@admin.register(MatterFact)
class MatterFactAdmin(admin.ModelAdmin):
    list_display = ("title", "matter", "source_label", "confidence", "ai_suggested", "selected_by_default")
    list_filter = ("confidence", "ai_suggested", "selected_by_default")
    search_fields = ("title", "text", "source_label")


@admin.register(TriageRubric)
class TriageRubricAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "active", "updated_at")
    list_filter = ("active",)
    search_fields = ("name", "slug", "description", "standard")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(LegalServerDelivery)
class LegalServerDeliveryAdmin(admin.ModelAdmin):
    list_display = ("matter", "kind", "origin", "status", "title", "created_by", "created_at")
    list_filter = ("kind", "status", "origin")
    search_fields = ("matter__external_id", "matter__client_name", "title", "filename", "remote_id")
    # An attempt to write to a case file is a historical record; it is read in
    # the admin, never edited there.
    readonly_fields = tuple(field.name for field in LegalServerDelivery._meta.fields)

    def has_add_permission(self, request):
        return False


@admin.register(TriageAssessment)
class TriageAssessmentAdmin(admin.ModelAdmin):
    list_display = ("matter", "rubric", "priority", "priority_label", "confidence", "case_type", "created_at")
    list_filter = ("priority", "confidence", "rubric")
    search_fields = ("matter__external_id", "matter__client_name", "summary", "reasoning")
    readonly_fields = ("created_at",)
