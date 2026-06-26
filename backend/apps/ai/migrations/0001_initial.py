# Generated manually for the initial prompt override model.
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="PromptOverride",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=120, unique=True)),
                ("system", models.TextField()),
                ("user", models.TextField()),
                ("default_model", models.CharField(blank=True, max_length=120)),
                ("default_reasoning_level", models.CharField(blank=True, max_length=40)),
                ("enabled", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["key"]},
        )
    ]
