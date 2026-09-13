from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("caselaw", "0002_rename_caselaw_indexes"),
        ("sources", "0008_ordinanceoverride_ordinancedocument"),
    ]

    operations = [
        migrations.CreateModel(
            name="CourtListenerCitationCache",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("citation_key", models.CharField(max_length=64, unique=True)),
                ("citation", models.CharField(max_length=500)),
                ("status", models.CharField(choices=[("resolved", "Resolved"), ("not_found", "Not found in CourtListener"), ("ambiguous", "Ambiguous in CourtListener")], max_length=20)),
                ("source_url", models.URLField(blank=True, max_length=1000)),
                ("provider_payload", models.JSONField(blank=True, default=dict)),
                ("checked_at", models.DateTimeField(auto_now=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("decision", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="courtlistener_citation_cache", to="caselaw.caselawdecision")),
            ],
            options={
                "ordering": ["citation"],
                "indexes": [models.Index(fields=["status", "expires_at"], name="sources_cou_status_4278d7_idx")],
            },
        ),
    ]
