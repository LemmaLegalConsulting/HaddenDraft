from django.contrib import admin

from apps.sources.models import RetrievedDocument, SourceConfiguration, UserOAuthConnection


@admin.register(SourceConfiguration)
class SourceConfigurationAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "enabled", "updated_at")
    list_filter = ("kind", "enabled")
    search_fields = ("name",)
    legalserver_fields = (
        "legalserver_base_url",
        "legalserver_api_token",
    )
    legalserver_advanced_fields = (
        "legalserver_matters_path",
        "legalserver_matter_documents_path",
        "legalserver_user_filter_param",
    )
    sharepoint_fields = (
        "sharepoint_site_id",
        "sharepoint_drive_id",
        "sharepoint_case_folder_template",
        "sharepoint_server_access_token",
    )
    openai_fields = ("openai_base_url", "openai_api_key", "openai_model", "openai_enabled")

    def get_fieldsets(self, request, obj=None):
        base = [(None, {"fields": ("name", "kind", "enabled")})]
        if obj and obj.kind == "legalserver":
            return base + [
                ("LegalServer API", {"fields": self.legalserver_fields}),
                (
                    "Advanced LegalServer API overrides",
                    {
                        "classes": ("collapse",),
                        "fields": self.legalserver_advanced_fields,
                        "description": "Most sites should leave these blank. Use only for a proxy, API gateway, or confirmed nonstandard endpoint shape.",
                    },
                ),
            ]
        if obj and obj.kind == "sharepoint":
            return base + [
                (
                    "SharePoint Online",
                    {
                        "fields": self.sharepoint_fields,
                        "description": "Delegated Office 365 user connections are preferred at runtime. These server credentials are the fallback.",
                    },
                )
            ]
        if obj and obj.kind == "openai":
            return base + [("OpenAI-compatible AI backend", {"fields": self.openai_fields})]
        return base + [
            ("LegalServer API", {"classes": ("collapse",), "fields": self.legalserver_fields}),
            (
                "Advanced LegalServer API overrides",
                {
                    "classes": ("collapse",),
                    "fields": self.legalserver_advanced_fields,
                    "description": "Most sites should leave these blank. Use only for a proxy, API gateway, or confirmed nonstandard endpoint shape.",
                },
            ),
            (
                "SharePoint Online",
                {
                    "classes": ("collapse",),
                    "fields": self.sharepoint_fields,
                    "description": "Delegated Office 365 user connections are preferred at runtime. These server credentials are the fallback.",
                },
            ),
            ("OpenAI-compatible AI backend", {"classes": ("collapse",), "fields": self.openai_fields}),
        ]


@admin.register(UserOAuthConnection)
class UserOAuthConnectionAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "enabled", "tenant_id", "client_id", "expires_at", "updated_at")
    list_filter = ("provider", "enabled")
    search_fields = ("user__username", "user__email", "tenant_id", "client_id")
    fieldsets = (
        (None, {"fields": ("user", "provider", "enabled")}),
        ("Office 365 app", {"fields": ("tenant_id", "client_id", "scopes", "expires_at")}),
        ("Tokens", {"fields": ("access_token", "refresh_token")}),
    )


@admin.register(RetrievedDocument)
class RetrievedDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "source_kind", "source_label", "citation", "created_at")
    list_filter = ("source_kind",)
    search_fields = ("title", "snippet", "citation")
