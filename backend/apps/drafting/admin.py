from django.contrib import admin

from apps.drafting.models import DraftDocument, DraftingSession


@admin.register(DraftingSession)
class DraftingSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "mode", "matter", "template", "status", "updated_at")
    list_filter = ("mode", "status")
    search_fields = ("matter__client_name", "matter__external_id", "instructions")


@admin.register(DraftDocument)
class DraftDocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "session", "updated_at")
    search_fields = ("title", "plain_text")
