from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("templates_app", "0003_word_template_assets")]

    operations = [
        migrations.AddField(
            model_name="documenttemplate",
            name="content_path",
            field=models.CharField(blank=True, help_text="Provider-relative path to a prepared template manifest.", max_length=500),
        ),
        migrations.AddField(
            model_name="documenttemplate",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="documenttemplate",
            name="last_synced_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="documenttemplate",
            name="source_checksum",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="documenttemplate",
            name="source_kind",
            field=models.CharField(choices=[("database", "Database/admin managed"), ("content_library", "Content library")], default="database", max_length=40),
        ),
        migrations.AddField(
            model_name="templateblock",
            name="content_path",
            field=models.CharField(blank=True, help_text="Provider-relative path to this block's DOCX snippet, when present.", max_length=500),
        ),
        migrations.AddField(
            model_name="templateblock",
            name="editable",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="templateblock",
            name="input_schema",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="templateblock",
            name="lexical_config",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="templateblock",
            name="source_checksum",
            field=models.CharField(blank=True, max_length=64),
        ),
    ]
