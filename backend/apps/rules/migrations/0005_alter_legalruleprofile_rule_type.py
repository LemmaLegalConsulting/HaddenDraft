from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("rules", "0004_legalruleprofile")]

    operations = [
        migrations.AlterField(
            model_name="legalruleprofile",
            name="rule_type",
            field=models.CharField(
                choices=[
                    ("statute", "Statute"),
                    ("civil_rule", "Rule of procedure"),
                    ("local_rule", "Local rule"),
                    ("doctrine", "Common-law doctrine"),
                    ("regulation", "Regulation"),
                ],
                default="statute",
                max_length=40,
            ),
        )
    ]
