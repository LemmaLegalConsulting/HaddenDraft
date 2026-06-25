from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("drafting", "0002_selected_curated_facts"),
    ]

    operations = [
        migrations.AddField(
            model_name="draftingsession",
            name="author_profile",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
