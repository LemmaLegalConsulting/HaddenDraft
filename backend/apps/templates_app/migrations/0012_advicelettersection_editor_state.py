from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("templates_app", "0011_advicelettersection_copyedit_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="advicelettersection",
            name="editor_state",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Initial Lexical state converted from the maintained section DOCX.",
            ),
        ),
    ]
