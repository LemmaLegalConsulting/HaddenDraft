from django.contrib import admin

from apps.issues.models import CandidateIssue


@admin.register(CandidateIssue)
class CandidateIssueAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "case_id",
        "issue_id",
        "title",
        "issue_type",
        "status",
        "source_table_key",
        "source_table_version",
        "source_row_id",
        "created_at",
    )
    list_filter = ("issue_type", "status", "source_table_key", "source_table_version")
    search_fields = ("case_id", "issue_id", "title", "source_row_id")
    readonly_fields = ("created_at",)
