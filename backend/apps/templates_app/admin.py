from django.contrib import admin

from apps.templates_app.models import DocumentTemplate, TemplateBlock


class TemplateBlockInline(admin.StackedInline):
    model = TemplateBlock
    extra = 0


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "jurisdiction", "source_kind", "is_active", "has_style_template", "created_from_example")
    list_filter = ("kind", "source_kind", "is_active", "created_from_example")
    search_fields = ("title", "description", "jurisdiction")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [TemplateBlockInline]

    @admin.display(boolean=True, description="Style template")
    def has_style_template(self, obj):
        return bool(obj.style_template)


@admin.register(TemplateBlock)
class TemplateBlockAdmin(admin.ModelAdmin):
    list_display = ("label", "template", "block_type", "order", "required", "editable", "ai_fill_mode", "has_docx_template")
    list_filter = ("block_type", "required", "editable", "ai_fill_mode")
    search_fields = ("label", "body")

    @admin.display(boolean=True, description="DOCX template")
    def has_docx_template(self, obj):
        return bool(obj.docx_template)
