from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("templates_app", "0005_expand_document_template_slug"),
    ]

    operations = [
        migrations.AddField(
            model_name="documenttemplate",
            name="aliases",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="documenttemplate",
            name="goal",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="documenttemplate",
            name="negative_goal",
            field=models.TextField(blank=True),
        ),
    ]
