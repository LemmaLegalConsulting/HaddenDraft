from django.contrib import admin

from apps.templates_app.models import DocumentTemplate, TemplateBlock


class TemplateBlockInline(admin.StackedInline):
    model = TemplateBlock
    extra = 0


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "jurisdiction", "source_label", "created_from_example")
    list_filter = ("kind", "created_from_example")
    search_fields = ("title", "description", "jurisdiction")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [TemplateBlockInline]


@admin.register(TemplateBlock)
class TemplateBlockAdmin(admin.ModelAdmin):
    list_display = ("label", "template", "block_type", "order", "required", "ai_fill_mode")
    list_filter = ("block_type", "required", "ai_fill_mode")
    search_fields = ("label", "body")
