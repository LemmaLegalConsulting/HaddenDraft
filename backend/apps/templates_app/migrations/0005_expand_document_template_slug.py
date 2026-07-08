from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("templates_app", "0004_content_library_templates"),
    ]

    operations = [
        migrations.AlterField(
            model_name="documenttemplate",
            name="slug",
            field=models.SlugField(max_length=120, unique=True),
        ),
    ]
