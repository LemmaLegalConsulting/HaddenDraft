"""Bring stored county values onto the shared vocabulary.

Ingestion writes the canonical name from now on, so this is for the corpus
that arrived before the vocabulary existed: 622 of 1,295 decisions, in which
"Cuyahoga" and "Cuyahoga County" were two shelves and a reader who narrowed to
one of them was shown 126 cases and told that was all of them.

Reading canonicalizes as well, so nothing is broken before this runs -- it
makes the database agree with what the interface already shows, which is what
every other reader of the column needs: the admin, an export, a query nobody
has written yet.

Nothing that the vocabulary does not recognize is touched. The corpus holds
"Miami-Dade County" and "Durham County, North Carolina", and those are not
untidy spellings of Ohio counties. `manage.py normalize_case_counties --report`
lists what was left alone.

The reverse is a no-op rather than a failure. The original spellings are not
recoverable -- two of them mapped to one -- but they carry no information the
canonical name does not, and refusing to migrate backwards would block an
unrelated rollback for no gain.
"""

from django.db import migrations


def normalize_counties(apps, schema_editor):
    # The live helper rather than a copy, because the vocabulary is a content
    # file that is meant to grow: a county added to it should reach a database
    # migrated afterwards. The historical model is used for the rows, as a data
    # migration must.
    from apps.core.jurisdictions import canonical_county, is_known_county

    CaseLawDecision = apps.get_model("caselaw", "CaseLawDecision")
    stored = (
        CaseLawDecision.objects.exclude(county="")
        .values_list("county", flat=True).distinct()
    )
    for value in {item for item in stored if (item or "").strip()}:
        if not is_known_county(value):
            continue
        canonical = canonical_county(value)
        if canonical != value:
            CaseLawDecision.objects.filter(county=value).update(county=canonical)


class Migration(migrations.Migration):

    dependencies = [("caselaw", "0004_caselawdateprovenance")]

    operations = [
        migrations.RunPython(normalize_counties, migrations.RunPython.noop, elidable=True),
    ]
