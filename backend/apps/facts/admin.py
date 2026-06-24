from django.contrib import admin

from apps.facts.models import ExtractedFact


@admin.register(ExtractedFact)
class ExtractedFactAdmin(admin.ModelAdmin):
    list_display = ("id", "case_id", "field_path", "source", "confidence", "review_status", "created_at")
    list_filter = ("source", "review_status")
    search_fields = ("case_id", "field_path")
    readonly_fields = ("created_at",)
