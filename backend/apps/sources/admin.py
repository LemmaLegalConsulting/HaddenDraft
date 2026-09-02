from django.contrib import admin
from django import forms
from django.utils import timezone
from apps.sources.ordinance_storage import store_upload

from apps.sources.models import OrdinanceDocument, OrdinanceOverride, RetrievedDocument, SourceConfiguration, UserOAuthConnection, UserResource, UserSourceIdentity


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


@admin.register(UserSourceIdentity)
class UserSourceIdentityAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "identifier", "enabled", "updated_at")
    list_filter = ("provider", "enabled")
    search_fields = ("user__username", "user__email", "identifier")
    fieldsets = (
        (None, {"fields": ("user", "provider", "enabled")}),
        (
            "External identity mapping",
            {
                "fields": ("identifier",),
                "description": "For LegalServer, this is the email or username used to map the logged-in app user to LegalServer permissions. Disable this row to turn off an individual mapping.",
            },
        ),
    )


@admin.register(RetrievedDocument)
class RetrievedDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "source_kind", "source_label", "citation", "created_at")
    list_filter = ("source_kind",)
    search_fields = ("title", "snippet", "citation")


@admin.register(UserResource)
class UserResourceAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "resource_type", "original_filename", "updated_at")
    list_filter = ("resource_type",)
    search_fields = ("title", "original_filename", "text", "user__username", "user__email")


class OrdinanceDocumentForm(forms.ModelForm):
    """Upload a document, or point at one, without touching the filesystem."""

    upload = forms.FileField(
        required=False,
        help_text="Optional. Uploading replaces this row's stored file; the publisher URL can be kept alongside it.",
    )

    class Meta:
        model = OrdinanceDocument
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("upload") and not cleaned.get("url") and not self.instance.storage_key:
            raise forms.ValidationError("Give the document a publisher URL, an upload, or both.")
        return cleaned

    def save(self, commit=True):
        document = super().save(commit=False)
        upload = self.cleaned_data.get("upload")
        if upload:
            stored = store_upload(
                content=upload.read(),
                municipality_slug=document.municipality_slug,
                target_key=document.target_key,
                filename=upload.name,
                content_type=getattr(upload, "content_type", "") or "",
            )
            for field, value in stored.items():
                setattr(document, field, value)
        if commit:
            document.save()
        return document


@admin.register(OrdinanceDocument)
class OrdinanceDocumentAdmin(admin.ModelAdmin):
    form = OrdinanceDocumentForm
    list_display = (
        "municipality_slug", "target_key", "title", "source_type",
        "status", "verified", "has_file", "updated_at",
    )
    list_filter = ("status", "source_type", "verified", "municipality_slug")
    search_fields = ("municipality_slug", "target_key", "title", "url", "notes", "sha256")
    readonly_fields = ("storage_key", "sha256", "size_bytes", "original_filename", "created_at", "updated_at")
    actions = ("mark_verified", "mark_superseded", "mark_active")
    fieldsets = (
        ("Authority", {"fields": ("municipality_slug", "target_key", "title", "source_type")}),
        ("Document", {"fields": ("url", "upload", "storage_key", "original_filename", "content_type",
                                 "size_bytes", "sha256")}),
        ("Where the authority sits in it", {
            "fields": ("extract_start", "extract_end", "extract_pages"),
            "description": "A council packet is mostly other business. Without these the whole packet is the record.",
        }),
        ("Standing", {"fields": ("status", "superseded_by", "verified", "verified_by", "verified_at")}),
        ("Notes", {"fields": ("notes", "added_by", "created_at", "updated_at")}),
    )

    @admin.display(boolean=True, description="File")
    def has_file(self, obj):
        return bool(obj.storage_key)

    @admin.action(description="Mark selected documents verified against the publisher")
    def mark_verified(self, request, queryset):
        updated = queryset.update(
            verified=True, verified_by=request.user.get_username(), verified_at=timezone.now(),
        )
        self.message_user(request, f"{updated} document(s) marked verified.")

    @admin.action(description="Mark selected documents superseded")
    def mark_superseded(self, request, queryset):
        # Deliberately does not delete: which document an assertion rested on is
        # part of the assertion.
        updated = queryset.update(status="superseded")
        self.message_user(request, f"{updated} document(s) marked superseded and kept on the record.")

    @admin.action(description="Mark selected documents active")
    def mark_active(self, request, queryset):
        updated = queryset.update(status="active", superseded_by=None)
        self.message_user(request, f"{updated} document(s) marked active.")


@admin.register(OrdinanceOverride)
class OrdinanceOverrideAdmin(admin.ModelAdmin):
    list_display = (
        "municipality_slug", "target_key", "citation", "legal_status",
        "verified", "is_active", "changed_fields", "updated_at",
    )
    list_filter = ("is_active", "verified", "legal_status", "municipality_slug")
    search_fields = ("municipality_slug", "target_key", "citation", "notes")
    readonly_fields = ("created_at", "updated_at")
    actions = ("mark_reviewed",)
    fieldsets = (
        ("Authority", {"fields": ("municipality_slug", "target_key", "is_active")}),
        ("Citation", {
            "fields": ("citation", "title", "act_file_number", "enacted_as", "source_type"),
            "description": "Leave a field blank to keep the generated value. An override is a patch, not a replacement.",
        }),
        ("Dates and standing", {
            "fields": ("legal_status", "enacted_date", "effective_date", "amended_date", "repeal_date"),
        }),
        ("Preemption", {
            "fields": ("preemption_status", "preemption_note", "controlling_case",
                       "court_treatment", "preemption_confidence"),
        }),
        ("Review", {"fields": ("verified", "reviewed_by", "reviewed_at", "notes", "created_at", "updated_at")}),
    )

    @admin.display(description="Overrides")
    def changed_fields(self, obj):
        return ", ".join(sorted(obj.applied_fields())) or "—"

    @admin.action(description="Mark reviewed by me, now")
    def mark_reviewed(self, request, queryset):
        updated = queryset.update(
            verified=True, reviewed_by=request.user.get_username(), reviewed_at=timezone.now(),
        )
        self.message_user(request, f"{updated} override(s) marked reviewed.")