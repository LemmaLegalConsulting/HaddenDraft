from django.contrib import admin

from apps.drafting.models import (
    ComponentVersion,
    DocumentComponent,
    DraftDocument,
    DraftingSession,
    DraftOperation,
    PackageRelationship,
)


@admin.register(DraftingSession)
class DraftingSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "mode", "matter", "template", "status", "updated_at")
    list_filter = ("mode", "status")
    search_fields = ("matter__client_name", "matter__external_id", "instructions")


@admin.register(DraftDocument)
class DraftDocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "session", "updated_at")
    search_fields = ("title", "plain_text")


class ComponentVersionInline(admin.TabularInline):
    model = ComponentVersion
    extra = 0
    readonly_fields = ("sequence", "origin", "instruction", "body", "structured_content", "created_at")
    can_delete = False
    ordering = ("-sequence",)


@admin.register(DocumentComponent)
class DocumentComponentAdmin(admin.ModelAdmin):
    list_display = ("id", "document", "stable_key", "component_type", "position", "removed_at")
    list_filter = ("component_type",)
    search_fields = ("stable_key", "label", "document__title")
    inlines = [ComponentVersionInline]


@admin.register(DraftOperation)
class DraftOperationAdmin(admin.ModelAdmin):
    list_display = ("id", "document", "operation_type", "target_component", "status", "origin", "created_at")
    list_filter = ("operation_type", "status", "origin")
    search_fields = ("document__title", "rationale")
    readonly_fields = ("created_at", "resolved_at", "result")


@admin.register(PackageRelationship)
class PackageRelationshipAdmin(admin.ModelAdmin):
    list_display = ("id", "source_document", "relationship_type", "target_document", "created_at")
    list_filter = ("relationship_type",)
    search_fields = ("source_document__title", "target_document__title")
