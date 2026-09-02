"""Loading, seeding, and matching court filing-rule profiles."""

import tempfile
from pathlib import Path

from django.test import TestCase
from django.test.utils import override_settings

from apps.rules.court_profiles import (
    court_profile_seeds,
    detect_court,
    detect_pleading_type,
    load_court_profile_file,
    sync_court_profile_seeds,
)
from apps.rules.models import CourtProfile


def write_profile(directory, name, body):
    path = Path(directory) / name
    path.write_text(body, encoding="utf-8")
    return path


TRIAL_COURT = """
slug: cleveland-housing
name: Cleveland Municipal Court, Housing Division
court_type: municipal
state: Ohio
county: Cuyahoga
municipality: Cleveland
division: Housing Division
aliases: [Cleveland Housing Court]
verification: verified
source: Local Rule 1.01
verified_on: "2026-01-15"
pleading_types: [motion, answer]
formatting:
  fonts: {min_size_pt: 12}
required_elements:
  - id: caption
    label: Caption
    severity: error
    patterns: ["in the .{0,60}court"]
"""


class LoadingTests(TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()

    def test_a_profile_loads_with_its_verification_record(self):
        path = write_profile(self.directory, "court.yaml", TRIAL_COURT)
        seed = load_court_profile_file(path)
        self.assertEqual(seed["slug"], "cleveland-housing")
        self.assertEqual(seed["verification"], "verified")
        self.assertEqual(seed["verified_on"].isoformat(), "2026-01-15")
        self.assertEqual(seed["municipality"], "Cleveland")

    def test_an_unknown_court_type_is_refused(self):
        path = write_profile(self.directory, "court.yaml", "slug: x\nname: X\ncourt_type: tribunal-of-vibes\n")
        with self.assertRaisesMessage(ValueError, "unknown court_type"):
            load_court_profile_file(path)

    def test_a_municipality_on_an_appellate_court_is_refused(self):
        path = write_profile(
            self.directory,
            "court.yaml",
            "slug: eighth\nname: Eighth District\ncourt_type: appellate\nmunicipality: Cleveland\n",
        )
        with self.assertRaisesMessage(ValueError, "where it does not apply"):
            load_court_profile_file(path)

    def test_a_missing_field_names_itself(self):
        path = write_profile(self.directory, "court.yaml", "slug: x\n")
        with self.assertRaisesMessage(ValueError, "is missing: court_type, name"):
            load_court_profile_file(path)


class SeedingTests(TestCase):
    def test_the_shipped_starter_profiles_load_and_are_marked_unverified(self):
        seeds = court_profile_seeds()
        self.assertTrue(seeds)
        self.assertTrue(all(seed["verification"] == "unverified" for seed in seeds))

    def test_seeding_is_idempotent(self):
        first = sync_court_profile_seeds()
        second = sync_court_profile_seeds()
        self.assertTrue(all(created for _profile, created in first))
        self.assertFalse(any(created for _profile, created in second))

    def test_seeding_never_reverts_a_profile_edited_here(self):
        sync_court_profile_seeds()
        profile = CourtProfile.objects.get(slug="generic-ohio-trial-court")
        profile.name = "Our court, as we actually filed it"
        profile.verification = CourtProfile.VERIFIED
        profile.is_locally_edited = True
        profile.save()

        sync_court_profile_seeds(update_existing=True)
        profile.refresh_from_db()
        self.assertEqual(profile.name, "Our court, as we actually filed it")
        self.assertEqual(profile.verification, CourtProfile.VERIFIED)


class DetectionTests(TestCase):
    def setUp(self):
        self.housing = CourtProfile.objects.create(
            slug="cleveland-housing",
            name="Cleveland Municipal Court, Housing Division",
            court_type=CourtProfile.MUNICIPAL,
            state="Ohio",
            county="Cuyahoga",
            municipality="Cleveland",
            aliases=["Cleveland Housing Court"],
        )
        self.appellate = CourtProfile.objects.create(
            slug="eighth-district",
            name="Eighth District Court of Appeals",
            court_type=CourtProfile.APPELLATE,
            state="Ohio",
            aliases=["Court of Appeals of Ohio, Eighth Appellate District"],
        )

    def test_the_caption_decides_which_court_a_filing_is_headed_to(self):
        detection = detect_court("IN THE CLEVELAND MUNICIPAL COURT, HOUSING DIVISION\nCase No. CV-24-1")
        self.assertTrue(detection["detected"])
        self.assertEqual(detection["profile"], self.housing)
        self.assertEqual(detection["where"], "brief caption")

    def test_punctuation_and_case_do_not_change_the_answer(self):
        detection = detect_court("in the cleveland housing court")
        self.assertEqual(detection["profile"], self.housing)

    def test_the_case_record_answers_when_the_document_does_not(self):
        class FakeMatter:
            jurisdiction = "Eighth District Court of Appeals"

        detection = detect_court("A brief with no caption.", matter=FakeMatter())
        self.assertEqual(detection["profile"], self.appellate)
        self.assertEqual(detection["where"], "case record")

    def test_the_caption_outranks_the_case_record(self):
        class FakeMatter:
            jurisdiction = "Cleveland Municipal Court, Housing Division"

        detection = detect_court("IN THE EIGHTH DISTRICT COURT OF APPEALS", matter=FakeMatter())
        self.assertEqual(detection["profile"], self.appellate)

    def test_a_court_named_only_deep_in_the_document_does_not_win(self):
        filler = "argument " * 3000
        detection = detect_court(f"{filler}\nIN THE CLEVELAND MUNICIPAL COURT, HOUSING DIVISION")
        self.assertFalse(detection["detected"])

    def test_nothing_matching_reports_nothing_rather_than_guessing(self):
        detection = detect_court("IN THE SUPERIOR COURT OF SOMEWHERE ELSE")
        self.assertFalse(detection["detected"])
        self.assertIsNone(detection["profile"])
        self.assertIn("No maintained court profile matched", detection["reason"])


class PleadingTypeTests(TestCase):
    def test_the_most_specific_description_wins(self):
        self.assertEqual(detect_pleading_type("REPLY BRIEF OF APPELLANT")["pleadingType"], "reply_brief")
        self.assertEqual(detect_pleading_type("MERIT BRIEF OF APPELLANT")["pleadingType"], "appellate_brief")
        self.assertEqual(detect_pleading_type("MEMORANDUM IN OPPOSITION")["pleadingType"], "memorandum")
        self.assertEqual(detect_pleading_type("MOTION FOR SUMMARY JUDGMENT")["pleadingType"], "motion")

    def test_an_unrecognized_document_is_left_unnamed(self):
        self.assertEqual(detect_pleading_type("A letter to the client")["pleadingType"], "")
