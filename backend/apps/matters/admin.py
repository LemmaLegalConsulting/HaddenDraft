from django.contrib import admin

from apps.matters.models import Matter, MatterFact


class MatterFactInline(admin.TabularInline):
    model = MatterFact
    extra = 0


@admin.register(Matter)
class MatterAdmin(admin.ModelAdmin):
    list_display = ("external_id", "client_name", "matter_type", "jurisdiction", "posture", "risk")
    search_fields = ("external_id", "client_name", "matter_type", "summary")
    inlines = [MatterFactInline]


@admin.register(MatterFact)
class MatterFactAdmin(admin.ModelAdmin):
    list_display = ("title", "matter", "source_label", "confidence", "ai_suggested", "selected_by_default")
    list_filter = ("confidence", "ai_suggested", "selected_by_default")
    search_fields = ("title", "text", "source_label")
