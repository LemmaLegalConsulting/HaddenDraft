from django.contrib import admin

from apps.argument_gym.models import GymChallenge, GymDocument, GymRun, GymWorkspace


class GymDocumentInline(admin.TabularInline):
    model = GymDocument
    extra = 0
    fields = ("role", "source_type", "title", "excluded")


@admin.register(GymWorkspace)
class GymWorkspaceAdmin(admin.ModelAdmin):
    list_display = ("title", "matter", "owner", "jurisdiction", "updated_at")
    list_filter = ("jurisdiction",)
    search_fields = ("title", "matter__external_id", "matter__client_name")
    inlines = [GymDocumentInline]


@admin.register(GymRun)
class GymRunAdmin(admin.ModelAdmin):
    list_display = ("id", "workspace", "brief", "status", "created_by", "created_at")
    list_filter = ("status",)
    readonly_fields = ("snapshot", "research_trace", "materials", "stage_trace", "comparison")


@admin.register(GymChallenge)
class GymChallengeAdmin(admin.ModelAdmin):
    list_display = ("id", "run", "ordinal", "category", "severity", "disposition")
    list_filter = ("category", "severity", "disposition")
    search_fields = ("opponent_argument", "judge_assessment")
