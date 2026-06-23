from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sources", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sourceconfiguration",
            name="kind",
            field=models.CharField(
                choices=[
                    ("legalserver", "LegalServer"),
                    ("sharepoint", "SharePoint"),
                    ("openai", "OpenAI-compatible AI backend"),
                    ("rag", "RAG database"),
                    ("local_cases", "Local archived cases"),
                    ("user_resources", "User-specific resources"),
                ],
                max_length=80,
            ),
        ),
    ]
