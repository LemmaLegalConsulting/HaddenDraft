from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sources", "0005_user_source_identity"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sourceconfiguration",
            name="legalserver_matters_path",
            field=models.CharField(
                blank=True,
                help_text="Advanced override. Leave blank to use /api/v2/matters.",
                max_length=255,
                verbose_name="Matters path",
            ),
        ),
        migrations.AlterField(
            model_name="sourceconfiguration",
            name="legalserver_user_filter_param",
            field=models.CharField(
                blank=True,
                help_text="Advanced override. Leave blank to disable server-side user filtering.",
                max_length=120,
                verbose_name="User filter parameter",
            ),
        ),
    ]
