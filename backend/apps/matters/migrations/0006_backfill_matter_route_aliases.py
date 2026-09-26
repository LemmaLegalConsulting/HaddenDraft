from django.db import migrations


def backfill(apps, schema_editor):
    from apps.matters.route_aliases import backfill_route_aliases

    backfill_route_aliases(apps.get_model("matters", "Matter"), apps.get_model("matters", "MatterRouteAlias"))


class Migration(migrations.Migration):
    dependencies = [
        ("matters", "0005_matter_route_alias"),
    ]

    # Reversing drops the table in 0005, which removes the rows with it.
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
