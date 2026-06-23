from django.db import models
from django.db.utils import DatabaseError, OperationalError, ProgrammingError


class SourceConfiguration(models.Model):
    KIND_CHOICES = [
        ("legalserver", "LegalServer"),
        ("sharepoint", "SharePoint"),
        ("openai", "OpenAI-compatible AI backend"),
        ("rag", "RAG database"),
        ("local_cases", "Local archived cases"),
        ("user_resources", "User-specific resources"),
    ]

    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=80, choices=KIND_CHOICES)
    enabled = models.BooleanField(default=True)

    legalserver_base_url = models.URLField("LegalServer base URL", blank=True)
    legalserver_api_token = models.CharField("API token", max_length=500, blank=True)
    legalserver_matters_path = models.CharField(
        "Matters path",
        max_length=255,
        blank=True,
        help_text="Advanced override. Leave blank to use /api/v1/matters.",
    )
    legalserver_matter_documents_path = models.CharField(
        "Matter documents path",
        max_length=255,
        blank=True,
        help_text="Advanced override. Leave blank to use /api/v1/matters/{matter_id}/documents.",
    )
    legalserver_user_filter_param = models.CharField(
        "User filter parameter",
        max_length=120,
        blank=True,
        help_text="Advanced override. Leave blank to use assigned_user_email.",
    )

    sharepoint_site_id = models.CharField(max_length=255, blank=True)
    sharepoint_drive_id = models.CharField(max_length=255, blank=True)
    sharepoint_case_folder_template = models.CharField(max_length=500, blank=True)
    sharepoint_server_access_token = models.TextField(blank=True)

    openai_base_url = models.URLField(blank=True)
    openai_api_key = models.CharField(max_length=500, blank=True)
    openai_model = models.CharField(max_length=120, blank=True)
    openai_enabled = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["kind", "name"]

    def __str__(self):
        return self.name

    @classmethod
    def effective_settings(cls, kind, fallback):
        try:
            config = cls.objects.filter(kind=kind, enabled=True).order_by("-updated_at").first()
        except (DatabaseError, OperationalError, ProgrammingError):
            return fallback
        if not config:
            return fallback
        overrides = config.as_settings()
        return {**fallback, **{key: value for key, value in overrides.items() if value not in ("", None)}}

    def as_settings(self):
        if self.kind == "legalserver":
            return {
                "base_url": self.legalserver_base_url,
                "api_token": self.legalserver_api_token,
                "matters_path": self.legalserver_matters_path,
                "matter_documents_path": self.legalserver_matter_documents_path,
                "user_filter_param": self.legalserver_user_filter_param,
            }
        if self.kind == "sharepoint":
            return {
                "site_id": self.sharepoint_site_id,
                "drive_id": self.sharepoint_drive_id,
                "case_folder_template": self.sharepoint_case_folder_template,
                "access_token": self.sharepoint_server_access_token,
            }
        if self.kind == "openai":
            return {
                "base_url": self.openai_base_url,
                "api_key": self.openai_api_key,
                "model": self.openai_model,
                "enabled": self.openai_enabled,
            }
        return {}


class UserOAuthConnection(models.Model):
    PROVIDER_CHOICES = [
        ("office365", "Office 365"),
    ]

    user = models.ForeignKey("auth.User", related_name="oauth_connections", on_delete=models.CASCADE)
    provider = models.CharField(max_length=80, choices=PROVIDER_CHOICES)
    enabled = models.BooleanField(default=True)
    tenant_id = models.CharField(max_length=255, blank=True)
    client_id = models.CharField(max_length=255, blank=True)
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    scopes = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__username", "provider"]
        unique_together = [("user", "provider")]

    def __str__(self):
        return f"{self.user} - {self.get_provider_display()}"

    @classmethod
    def access_token_for(cls, user, provider):
        if not user or not getattr(user, "is_authenticated", False):
            return ""
        try:
            connection = cls.objects.filter(user=user, provider=provider, enabled=True).first()
        except (DatabaseError, OperationalError, ProgrammingError):
            return ""
        return connection.access_token if connection and connection.access_token else ""


class UserSourceIdentity(models.Model):
    PROVIDER_CHOICES = [
        ("legalserver", "LegalServer"),
    ]

    user = models.ForeignKey("auth.User", related_name="source_identities", on_delete=models.CASCADE)
    provider = models.CharField(max_length=80, choices=PROVIDER_CHOICES)
    identifier = models.CharField(max_length=255)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__username", "provider"]
        unique_together = [("user", "provider")]

    def __str__(self):
        return f"{self.user} - {self.get_provider_display()}: {self.identifier}"

    @classmethod
    def identifier_for(cls, user, provider):
        if not user or not getattr(user, "is_authenticated", False):
            return ""
        try:
            identity = cls.objects.filter(user=user, provider=provider, enabled=True).first()
        except (DatabaseError, OperationalError, ProgrammingError):
            return ""
        return identity.identifier if identity and identity.identifier else ""


class RetrievedDocument(models.Model):
    source_kind = models.CharField(max_length=80)
    source_label = models.CharField(max_length=255)
    external_id = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=500)
    snippet = models.TextField(blank=True)
    url = models.URLField(blank=True)
    citation = models.CharField(max_length=500, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
