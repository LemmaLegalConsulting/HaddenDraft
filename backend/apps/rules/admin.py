from django.contrib import admin

from apps.rules.models import (
    CourtProfile,
    LegalRuleProfile,
    DecisionRuleRow,
    DecisionTable,
    DecisionTestCase,
    RuleAuthority,
    RuleRunLog,
)


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


@admin.register(CourtProfile)
class CourtProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "court_type", "state", "county", "municipality", "verification", "active")
    list_filter = ("court_type", "verification", "active", "state")
    search_fields = ("name", "slug", "aliases", "county", "municipality", "division")
    readonly_fields = ("is_locally_edited", "created_at", "updated_at")
    fieldsets = (
        ("Identity", {"fields": ("slug", "name", "court_type", "state", "county", "municipality", "division", "aliases")}),
        (
            "Verification",
            {
                "description": (
                    "Only a verified profile's requirements are reported as errors. Leave this "
                    "unverified until someone has read this court's own published rules."
                ),
                "fields": ("verification", "source", "source_url", "verified_on", "notes"),
            },
        ),
        ("Filing rules", {"fields": ("pleading_types", "formatting", "required_elements")}),
        ("State", {"fields": ("active", "is_locally_edited", "created_at", "updated_at")}),
    )

    def save_model(self, request, obj, form, change):
        # An edit made here outranks the content library, and re-seeding must
        # not quietly undo it.
        if change:
            obj.is_locally_edited = True
        super().save_model(request, obj, form, change)


@admin.register(LegalRuleProfile)
class LegalRuleProfileAdmin(admin.ModelAdmin):
    list_display = ("citation", "name", "jurisdiction", "rule_type", "verification", "active")
    list_filter = ("rule_type", "verification", "active", "jurisdiction")
    search_fields = ("name", "slug", "citation", "aliases", "summary")
    readonly_fields = ("is_locally_edited", "created_at", "updated_at")
    fieldsets = (
        ("Identity", {"fields": ("slug", "name", "citation", "rule_type", "jurisdiction", "summary")}),
        (
            "Detection",
            {
                "description": "How to tell this rule was invoked: citation patterns, and phrases used without a citation.",
                "fields": ("citation_patterns", "aliases"),
            },
        ),
        (
            "Elements",
            {
                "description": (
                    "What the rule requires. Naming a published decision-table row pulls its "
                    "missing facts and condition facts in as elements too, so a rule the tables "
                    "already encode is not written down twice."
                ),
                "fields": ("elements", "decision_table_key", "decision_table_row"),
            },
        ),
        (
            "Verification",
            {
                "description": (
                    "These elements are substantive law. Only a verified list produces "
                    "error-level findings; leave it unverified until someone has read the rule."
                ),
                "fields": ("verification", "source", "source_url", "verified_on", "notes"),
            },
        ),
        ("State", {"fields": ("active", "is_locally_edited", "created_at", "updated_at")}),
    )

    def save_model(self, request, obj, form, change):
        if change:
            obj.is_locally_edited = True
        super().save_model(request, obj, form, change)
