from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="authorprofile",
            name="default_jurisdiction",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.CreateModel(
            name="OrganizationSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("default_jurisdiction", models.CharField(blank=True, max_length=255)),
            ],
            options={"verbose_name": "organization settings", "verbose_name_plural": "organization settings"},
        ),
    ]
