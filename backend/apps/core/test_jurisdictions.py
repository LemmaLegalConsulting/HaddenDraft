"""Tests for the shared county vocabulary.

The behaviour worth pinning is not that "Cuyahoga County" becomes "Cuyahoga".
It is that nothing else does: this corpus holds out-of-state counties, and a
vocabulary that guessed at the nearest Ohio match would file a Florida decision
on an Ohio shelf without anything looking wrong.
"""

from __future__ import annotations

from django.db import migrations
from django.test import SimpleTestCase, TestCase

from apps.core.jurisdictions import (
    appellate_district,
    canonical_county,
    county_names,
    is_known_county,
    normalize_county_key,
    vocabulary_status,
)


class CountyVocabularyTests(SimpleTestCase):
    def test_the_vocabulary_holds_every_ohio_county(self):
        status = vocabulary_status()
        self.assertTrue(status["available"])
        self.assertEqual(status["countyCount"], 88)
        self.assertEqual(len(set(county_names())), 88)

    def test_the_two_spellings_the_corpus_actually_uses_are_one_county(self):
        self.assertEqual(canonical_county("Cuyahoga"), "Cuyahoga")
        self.assertEqual(canonical_county("Cuyahoga County"), "Cuyahoga")

    def test_case_punctuation_and_the_ways_of_writing_county_do_not_matter(self):
        for spelling in (
            "CUYAHOGA COUNTY", "cuyahoga county", "Cuyahoga Cty.", "Cuyahoga Co.",
            "County of Cuyahoga", "Cuyahoga County, Ohio", "  Cuyahoga  ",
        ):
            self.assertEqual(canonical_county(spelling), "Cuyahoga", spelling)

    def test_a_two_word_county_survives_normalization(self):
        self.assertEqual(canonical_county("Van Wert County"), "Van Wert")

    def test_an_out_of_state_county_is_left_exactly_as_it_arrived(self):
        # The corpus really contains these. Rewriting "Miami-Dade" to Ohio's
        # "Miami" would put a Florida decision on an Ohio shelf, and nothing
        # downstream would look wrong.
        for spelling in (
            "Miami-Dade County", "Dade (Miami-Dade) County", "Durham County, North Carolina",
            "Cook County", "St. Joseph",
        ):
            self.assertEqual(canonical_county(spelling), spelling, spelling)
            self.assertFalse(is_known_county(spelling), spelling)
            self.assertEqual(appellate_district(spelling), "", spelling)

    def test_an_empty_county_stays_empty_rather_than_becoming_a_county(self):
        for value in ("", "   ", None):
            self.assertEqual(canonical_county(value), "")
            self.assertFalse(is_known_county(value))

    def test_the_district_comes_from_the_vocabulary_for_either_spelling(self):
        self.assertEqual(appellate_district("Cuyahoga"), "Eighth District")
        self.assertEqual(appellate_district("Cuyahoga County"), "Eighth District")
        self.assertEqual(appellate_district("Hamilton"), "First District")
        self.assertEqual(appellate_district("Warren County"), "Twelfth District")

    def test_every_county_has_a_district(self):
        missing = [name for name in county_names() if not appellate_district(name)]
        self.assertEqual(missing, [])

    def test_normalization_does_not_collide_two_different_counties(self):
        keys = [normalize_county_key(name) for name in county_names()]
        self.assertEqual(len(set(keys)), len(keys))
        # The collision that would actually happen if matching were fuzzy.
        self.assertNotEqual(normalize_county_key("Miami-Dade"), normalize_county_key("Miami"))


class IngestionWritesTheCanonicalCountyTests(TestCase):
    def test_a_decision_imported_with_county_suffix_is_stored_without_it(self):
        from apps.caselaw.importing import decision_defaults

        class Group:
            stem = "sample"
            pdf_path = None

        values = decision_defaults(
            {"title": "Smith v. Jones", "county": "Cuyahoga County"},
            Group(), "a" * 64, False, allow_search=True,
        )
        self.assertEqual(values["county"], "Cuyahoga")

    def test_an_out_of_state_county_survives_ingestion_unchanged(self):
        from apps.caselaw.importing import decision_defaults

        class Group:
            stem = "sample"
            pdf_path = None

        values = decision_defaults(
            {"title": "Smith v. Jones", "county": "Miami-Dade County"},
            Group(), "b" * 64, False, allow_search=True,
        )
        self.assertEqual(values["county"], "Miami-Dade County")


class BackfillTests(TestCase):
    def _decision(self, title, county, sha):
        from apps.caselaw.models import CaseLawDecision

        return CaseLawDecision.objects.create(title=title, county=county, source_sha256=sha)

    def test_the_command_rewrites_recognized_counties_and_leaves_the_rest(self):
        from io import StringIO

        from django.core.management import call_command

        from apps.caselaw.models import CaseLawDecision

        # Written straight to the database, as a corpus imported before the
        # vocabulary existed would have been.
        CaseLawDecision.objects.bulk_create([
            CaseLawDecision(title="A", county="Cuyahoga County", source_sha256="1" * 64),
            CaseLawDecision(title="B", county="Cuyahoga", source_sha256="2" * 64),
            CaseLawDecision(title="C", county="Miami-Dade County", source_sha256="3" * 64),
        ])
        out = StringIO()
        call_command("normalize_case_counties", stdout=out)
        counties = sorted(CaseLawDecision.objects.values_list("county", flat=True))
        self.assertEqual(counties, ["Cuyahoga", "Cuyahoga", "Miami-Dade County"])
        self.assertIn("Miami-Dade County", out.getvalue())

    def test_a_dry_run_reports_without_writing(self):
        from io import StringIO

        from django.core.management import call_command

        from apps.caselaw.models import CaseLawDecision

        self._decision("A", "Summit County", "4" * 64)
        call_command("normalize_case_counties", "--dry-run", stdout=StringIO())
        self.assertEqual(CaseLawDecision.objects.get(title="A").county, "Summit County")

    def test_running_it_twice_changes_nothing_the_second_time(self):
        from io import StringIO

        from django.core.management import call_command

        self._decision("A", "Stark County", "5" * 64)
        call_command("normalize_case_counties", stdout=StringIO())
        out = StringIO()
        call_command("normalize_case_counties", stdout=out)
        self.assertIn("already stored canonically", out.getvalue())


class MigrationTests(TestCase):
    """The data migration is what carries the fix to every other environment."""

    def test_the_migration_normalizes_and_is_reversible(self):
        from django.db.migrations.executor import MigrationExecutor
        from django.db import connection

        from apps.caselaw.models import CaseLawDecision

        CaseLawDecision.objects.create(title="A", county="Cuyahoga County", source_sha256="a" * 64)
        CaseLawDecision.objects.create(title="B", county="Miami-Dade County", source_sha256="b" * 64)

        executor = MigrationExecutor(connection)
        migration = executor.loader.get_migration("caselaw", "0005_normalize_decision_counties")
        operation = migration.operations[0]
        operation.code(executor.loader.project_state(("caselaw", "0005_normalize_decision_counties")).apps, None)

        self.assertEqual(CaseLawDecision.objects.get(title="A").county, "Cuyahoga")
        self.assertEqual(CaseLawDecision.objects.get(title="B").county, "Miami-Dade County")
        # Reversing must not raise; the spellings it merged are not recoverable
        # and carry nothing the canonical name does not.
        self.assertIs(operation.reverse_code, migrations.RunPython.noop)


class MissingVocabularyTests(TestCase):
    def test_a_missing_vocabulary_file_on_first_use_reads_as_no_vocabulary(self):
        # A missing file fingerprints as None, which used to match the empty
        # cache and raise KeyError on the very first lookup in a process.
        import tempfile

        from django.test import override_settings

        from apps.core import jurisdictions

        jurisdictions._CACHE.clear()
        with tempfile.TemporaryDirectory() as directory, override_settings(CONTENT_LIBRARY_DIR=directory):
            self.assertEqual(jurisdictions.canonical_county("Cuyahoga"), jurisdictions.canonical_county("Cuyahoga"))
        jurisdictions._CACHE.clear()
