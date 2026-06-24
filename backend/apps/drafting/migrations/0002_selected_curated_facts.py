from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("drafting", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="draftingsession",
            name="selected_curated_facts",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
