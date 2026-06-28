from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("drafting", "0003_draftingsession_author_profile")]

    operations = [
        migrations.AddField(
            model_name="draftingsession",
            name="template_data",
            field=models.JSONField(blank=True, default=dict, help_text="Values for fields declared by the selected prepared template."),
        )
    ]
