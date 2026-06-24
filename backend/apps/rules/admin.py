from django.contrib import admin

from apps.rules.models import DecisionRuleRow, DecisionTable, DecisionTestCase, RuleAuthority, RuleRunLog


class DecisionRuleRowInline(admin.TabularInline):
    model = DecisionRuleRow
    extra = 0
    fields = ("row_id", "label", "priority", "enabled", "conditions", "outputs", "explanation_template")


class DecisionTestCaseInline(admin.TabularInline):
    model = DecisionTestCase
    extra = 0
    fields = ("name", "enabled", "inputs", "expected_outputs")


@admin.register(RuleAuthority)
class RuleAuthorityAdmin(admin.ModelAdmin):
    list_display = ("id", "authority_type", "citation", "title", "pinpoint")
    list_filter = ("authority_type",)
    search_fields = ("citation", "title", "source_ref", "notes")


@admin.register(DecisionTable)
class DecisionTableAdmin(admin.ModelAdmin):
    list_display = ("id", "key", "version", "title", "workflow_type", "jurisdiction", "status", "hit_policy")
    list_filter = ("status", "hit_policy", "workflow_type", "jurisdiction", "engine_type")
    search_fields = ("key", "title", "description", "change_reason")
    filter_horizontal = ("authorities",)
    inlines = [DecisionRuleRowInline, DecisionTestCaseInline]


@admin.register(DecisionRuleRow)
class DecisionRuleRowAdmin(admin.ModelAdmin):
    list_display = ("id", "table", "row_id", "label", "priority", "enabled")
    list_filter = ("enabled", "table__key", "table__version")
    search_fields = ("row_id", "label", "explanation_template")


@admin.register(DecisionTestCase)
class DecisionTestCaseAdmin(admin.ModelAdmin):
    list_display = ("id", "table", "name", "enabled")
    list_filter = ("enabled", "table__key", "table__status")
    search_fields = ("name", "table__key")


@admin.register(RuleRunLog)
class RuleRunLogAdmin(admin.ModelAdmin):
    list_display = ("id", "case_id", "workflow_run_id", "table_key", "table_version", "created_at")
    list_filter = ("table_key", "table_version")
    search_fields = ("case_id", "workflow_run_id", "table_key")
    readonly_fields = ("created_at",)
