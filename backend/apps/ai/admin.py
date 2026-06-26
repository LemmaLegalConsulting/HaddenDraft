from django.contrib import admin

from apps.ai.models import PromptOverride


@admin.register(PromptOverride)
class PromptOverrideAdmin(admin.ModelAdmin):
    list_display = ("key", "default_model", "default_reasoning_level", "enabled", "updated_at")
    list_filter = ("enabled",)
    search_fields = ("key", "system", "user")
