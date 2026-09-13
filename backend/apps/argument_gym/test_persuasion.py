"""The persuasive communication suite: a separate question from whether the brief is right."""

import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.test.utils import override_settings

from apps.argument_gym import checks, ingestion
from apps.argument_gym.models import GymDocument, GymRun, GymWorkspace
from apps.argument_gym.persuasion import run_persuasion_review
from apps.argument_gym.pipeline import execute_run
from apps.argument_gym.tests import BRIEF, StubRegistry


FRAMING = "persuasion_issue_framing"
EMPHASIS = "persuasion_emphasis"


class SuiteClient:
    """Answers the persuasion call and nothing else, so other stages fall back."""

    def __init__(self, dimensions):
        self.dimensions = dimensions
        self.prompts = []

    def complete(self, *, system, user, **_kwargs):
        self.prompts.append(user)
        if "Dimensions to assess" not in user:
            return ""
        return json.dumps({"dimensions": self.dimensions})


def units_from(text=BRIEF):
    return ingestion.ingest_upload(text.encode("utf-8"), filename="brief.txt")["metadata"]["units"]


class CatalogTests(TestCase):
    def test_the_suite_is_its_own_group_of_twelve_selectable_tests(self):
        catalog = {check["id"]: check for check in checks.catalog()}
        suite = [check for check in catalog.values() if check["category"] == "persuasion"]
        self.assertEqual(len(suite), 12)
        self.assertEqual(len(checks.PERSUASION_CHECK_IDS), 12)
        self.assertEqual(catalog[FRAMING]["categoryLabel"], "Persuasive communication")
        self.assertEqual(catalog[FRAMING]["kind"], "model")
        for check in suite:
            # The description is the question the test actually asks.
            self.assertTrue(check["description"].endswith("?"), check["id"])

    def test_correctness_and_completeness_are_kept_apart(self):
        catalog = {check["id"]: check for check in checks.catalog()}
        self.assertEqual(catalog["rule_elements"]["category"], "correctness")
        self.assertEqual(catalog["record_support"]["category"], "correctness")
        self.assertEqual(catalog["authority_support"]["category"], "correctness")
        self.assertEqual(catalog["adversarial"]["category"], "completeness")
        self.assertEqual(catalog["adversarial"]["categoryLabel"], "Argumentative completeness")

    def test_the_catalog_is_ordered_so_the_groups_hold_together(self):
        seen = []
        for check in checks.catalog():
            if check["category"] not in seen:
                seen.append(check["category"])
        self.assertEqual(seen, [category["id"] for category in checks.category_catalog()])

    def test_only_the_dimensions_the_author_selected_are_asked_about(self):
        dimensions = checks.persuasion_dimensions([FRAMING, EMPHASIS, "grammar"])
        self.assertEqual([item["id"] for item in dimensions], [FRAMING, EMPHASIS])
        self.assertIn("real dispute", dimensions[0]["question"])


@override_settings(AI_DRAFTING_ENABLED=True)
class ReviewTests(TestCase):
    def test_every_selected_dimension_is_reported_under_its_own_check_id(self):
        client = SuiteClient(
            [
                {
                    "id": FRAMING,
                    "verdict": "weak",
                    "finding": "The brief opens on the standard of review rather than the notice defect.",
                    "quote": "This court reviews de novo.",
                    "suggestion": "Name the notice defect in the first paragraph.",
                },
                {
                    "id": EMPHASIS,
                    "verdict": "strong",
                    "finding": "Two thirds of the argument is spent on the dispositive notice question.",
                    "quote": "",
                    "suggestion": "",
                },
            ]
        )
        results, trace = run_persuasion_review(
            [FRAMING, EMPHASIS], units_from(), document_id=7, brief_title="Answer", llm_client=client
        )

        self.assertEqual(trace["method"], "llm")
        self.assertEqual(sorted(results), sorted([FRAMING, EMPHASIS]))
        framing = results[FRAMING]["findings"][0]
        self.assertEqual(results[FRAMING]["summary"], "Needs work")
        self.assertEqual(framing["severity"], "warning")
        self.assertEqual(framing["target"], "Issue framing")
        self.assertEqual(framing["details"]["suggestion"], "Name the notice defect in the first paragraph.")
        # A judgment about how a brief reads is a nudge; nothing here is an error.
        self.assertEqual(results[EMPHASIS]["findings"][0]["severity"], "info")
        self.assertEqual(results[EMPHASIS]["summary"], "Working")

    def test_a_dimension_the_model_skipped_is_unassessed_rather_than_missing(self):
        client = SuiteClient(
            [{"id": FRAMING, "verdict": "adequate", "finding": "The question is named in the introduction."}]
        )
        results, _trace = run_persuasion_review(
            [FRAMING, EMPHASIS], units_from(), document_id=7, brief_title="Answer", llm_client=client
        )
        self.assertEqual(results[EMPHASIS]["summary"], "Not assessed")
        self.assertIn("did not run is not a pass", results[EMPHASIS]["findings"][0]["message"])

    def test_an_unrecognized_verdict_does_not_become_a_passing_one(self):
        client = SuiteClient([{"id": FRAMING, "verdict": "excellent", "finding": "Framed well enough."}])
        results, _trace = run_persuasion_review(
            [FRAMING], units_from(), document_id=7, brief_title="Answer", llm_client=client
        )
        self.assertEqual(results[FRAMING]["findings"][0]["details"]["verdict"], "weak")

    def test_a_dimension_it_was_not_asked_about_is_discarded(self):
        client = SuiteClient(
            [
                {"id": EMPHASIS, "verdict": "weak", "finding": "Every point is argued at the same volume."},
                {"id": FRAMING, "verdict": "strong", "finding": "The dispute is named in the first line."},
            ]
        )
        results, _trace = run_persuasion_review(
            [FRAMING], units_from(), document_id=7, brief_title="Answer", llm_client=client
        )
        self.assertEqual(list(results), [FRAMING])


@override_settings(AI_DRAFTING_ENABLED=False)
class WithoutAModelTests(TestCase):
    def test_a_judgment_call_reports_itself_unassessed_rather_than_passing(self):
        results, trace = run_persuasion_review(
            checks.PERSUASION_CHECK_IDS, units_from(), document_id=7, brief_title="Answer"
        )
        self.assertEqual(trace["method"], "deterministic")
        self.assertEqual(len(results), 12)
        for check_id, result in results.items():
            self.assertEqual(result["summary"], "Not assessed", check_id)
            self.assertTrue(result["findings"][0]["manualReview"])
            self.assertEqual(result["findings"][0]["outcome"], "review")


@override_settings(ARGUMENT_GYM_BACKGROUND_RUNS=False, AI_DRAFTING_ENABLED=False)
class RunTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("advocate", password="secret")
        self.workspace = GymWorkspace.objects.create(owner=self.user, title="Answer")
        ingested = ingestion.ingest_upload(BRIEF.encode("utf-8"), filename="answer.txt")
        self.brief = GymDocument.objects.create(
            workspace=self.workspace,
            role=GymDocument.BRIEF_UNDER_TEST,
            source_type=GymDocument.UPLOAD,
            title="Answer",
            extracted_text=ingested["text"],
            extraction_metadata=ingested["metadata"],
        )

    def run_with(self, enabled):
        self.workspace.enabled_checks = enabled
        self.workspace.save(update_fields=["enabled_checks"])
        return execute_run(
            GymRun.objects.create(workspace=self.workspace, brief=self.brief), connector_registry=StubRegistry()
        )

    def test_the_selected_dimensions_land_in_the_run_beside_the_other_findings(self):
        run = self.run_with([FRAMING, EMPHASIS])
        self.assertIn(FRAMING, run.check_results)
        self.assertIn(EMPHASIS, run.check_results)
        by_id = {entry["id"]: entry for entry in run.checks_run}
        self.assertEqual(by_id[FRAMING]["status"], "on")
        self.assertEqual(by_id[FRAMING]["category"], "persuasion")
        stages = {stage["stage"]: stage["method"] for stage in run.stage_trace}
        self.assertEqual(stages["persuasion"], "deterministic")

    def test_a_suite_turned_off_produces_nothing_and_says_so(self):
        run = self.run_with(["grammar"])
        self.assertNotIn(FRAMING, run.check_results)
        stages = {stage["stage"]: stage["method"] for stage in run.stage_trace}
        self.assertEqual(stages["persuasion"], "off")
        by_id = {entry["id"]: entry for entry in run.checks_run}
        self.assertEqual(by_id[FRAMING]["status"], "off")
