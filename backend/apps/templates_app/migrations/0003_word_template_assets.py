from django.core.validators import FileExtensionValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("templates_app", "0002_author_aware_signature_blocks"),
    ]

    operations = [
        migrations.AddField(
            model_name="documenttemplate",
            name="replace_child_styles",
            field=models.BooleanField(
                default=True,
                help_text="When enabled, composed block documents inherit conflicting styles from the style template.",
            ),
        ),
        migrations.AddField(
            model_name="documenttemplate",
            name="style_template",
            field=models.FileField(
                blank=True,
                help_text="Optional .dotx or .docx style source used as the master document for Word exports.",
                upload_to="template_styles/",
                validators=[FileExtensionValidator(["docx", "dotx"])],
            ),
        ),
        migrations.AddField(
            model_name="templateblock",
            name="docx_template",
            field=models.FileField(
                blank=True,
                help_text="Optional .docx/.dotx Jinja template rendered for this block during Word export.",
                upload_to="template_blocks/",
                validators=[FileExtensionValidator(["docx", "dotx"])],
            ),
        ),
    ]
