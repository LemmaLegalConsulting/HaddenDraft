from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def copy_json_settings_to_typed_fields(apps, schema_editor):
    SourceConfiguration = apps.get_model("sources", "SourceConfiguration")
    for config in SourceConfiguration.objects.all():
        data = config.settings or {}
        if config.kind == "legalserver":
            config.legalserver_base_url = data.get("base_url", "")
            config.legalserver_api_token = data.get("api_token", "")
            config.legalserver_matters_path = data.get("matters_path", "")
            config.legalserver_matter_documents_path = data.get("matter_documents_path", "")
            config.legalserver_user_filter_param = data.get("user_filter_param", "")
        elif config.kind == "sharepoint":
            config.sharepoint_site_id = data.get("site_id", "")
            config.sharepoint_drive_id = data.get("drive_id", "")
            config.sharepoint_case_folder_template = data.get("case_folder_template", "")
            config.sharepoint_server_access_token = data.get("access_token", "")
        elif config.kind == "openai":
            config.openai_base_url = data.get("base_url", "")
            config.openai_api_key = data.get("api_key", "")
            config.openai_model = data.get("model", "")
            config.openai_enabled = str(data.get("enabled", False)).lower() in {"1", "true", "yes", "on"}
        config.save()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("sources", "0002_openai_sourceconfiguration_kind"),
    ]

    operations = [
        migrations.AddField(
            model_name="sourceconfiguration",
            name="legalserver_api_token",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="sourceconfiguration",
            name="legalserver_base_url",
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name="sourceconfiguration",
            name="legalserver_matter_documents_path",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="sourceconfiguration",
            name="legalserver_matters_path",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="sourceconfiguration",
            name="legalserver_user_filter_param",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="sourceconfiguration",
            name="openai_api_key",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="sourceconfiguration",
            name="openai_base_url",
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name="sourceconfiguration",
            name="openai_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="sourceconfiguration",
            name="openai_model",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="sourceconfiguration",
            name="sharepoint_case_folder_template",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="sourceconfiguration",
            name="sharepoint_drive_id",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="sourceconfiguration",
            name="sharepoint_server_access_token",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="sourceconfiguration",
            name="sharepoint_site_id",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.RunPython(copy_json_settings_to_typed_fields, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="sourceconfiguration",
            name="settings",
        ),
        migrations.CreateModel(
            name="UserOAuthConnection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(choices=[("office365", "Office 365")], max_length=80)),
                ("enabled", models.BooleanField(default=True)),
                ("tenant_id", models.CharField(blank=True, max_length=255)),
                ("client_id", models.CharField(blank=True, max_length=255)),
                ("access_token", models.TextField(blank=True)),
                ("refresh_token", models.TextField(blank=True)),
                ("scopes", models.TextField(blank=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="oauth_connections",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["user__username", "provider"],
                "unique_together": {("user", "provider")},
            },
        ),
    ]
