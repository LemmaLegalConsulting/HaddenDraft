from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sources", "0003_typed_source_configuration_and_user_oauth"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sourceconfiguration",
            name="legalserver_api_token",
            field=models.CharField(blank=True, max_length=500, verbose_name="API token"),
        ),
        migrations.AlterField(
            model_name="sourceconfiguration",
            name="legalserver_base_url",
            field=models.URLField(blank=True, verbose_name="LegalServer base URL"),
        ),
        migrations.AlterField(
            model_name="sourceconfiguration",
            name="legalserver_matter_documents_path",
            field=models.CharField(
                blank=True,
                help_text="Advanced override. Leave blank to use /api/v1/matters/{matter_id}/documents.",
                max_length=255,
                verbose_name="Matter documents path",
            ),
        ),
        migrations.AlterField(
            model_name="sourceconfiguration",
            name="legalserver_matters_path",
            field=models.CharField(
                blank=True,
                help_text="Advanced override. Leave blank to use /api/v1/matters.",
                max_length=255,
                verbose_name="Matters path",
            ),
        ),
        migrations.AlterField(
            model_name="sourceconfiguration",
            name="legalserver_user_filter_param",
            field=models.CharField(
                blank=True,
                help_text="Advanced override. Leave blank to use assigned_user_email.",
                max_length=120,
                verbose_name="User filter parameter",
            ),
        ),
    ]
