from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("drafting", "0005_draftingsession_template_data"),
    ]

    operations = [
        migrations.AddField(
            model_name="draftingsession",
            name="draft_plan",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="draftingsession",
            name="goal",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="draftingsession",
            name="missing_information",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="draftingsession",
            name="selected_template_ids",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
