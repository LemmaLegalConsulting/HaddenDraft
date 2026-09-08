"""A run that finishes its work must not die on the way to reporting it.

A real run against an appellate brief reached the last stage, wrote a verdict
longer than the column that holds it, and took the whole run down at the final
save -- after every model call had already been paid for. Worse, the failure
handler saved the same over-long value again, so it raised too, and the row
kept saying "running": the client polled a run that would never finish rather
than being told it had failed.
"""

import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import DataError
from django.test import TestCase
from django.test.utils import override_settings

from apps.argument_gym import ingestion
from apps.argument_gym.models import GymDocument, GymRun, GymWorkspace
from apps.argument_gym.pipeline import VERDICT_LIMIT, execute_run
from apps.argument_gym.tests import BRIEF, StubRegistry

LONG_VERDICT = (
    "A brief that argues its strongest ground persuasively but leaves the "
    "record citations for the second assignment of error unsupported"
)


class VerdictClient:
    """Answers every stage with the assessment payload.

    Unconditional on purpose. Keying off the prompt text made the test pass
    while the bug was still there: the assessment stage never matched, fell
    back to its deterministic verdict, and the assertion measured a string the
    model had not written.
    """

    def complete(self, *, system, user, **_kwargs):
        return json.dumps(
            {
                "verdict": LONG_VERDICT,
                "assessment": (
                    "The brief is well organized and its first assignment of error is argued "
                    "from the record, but the second rests on assertions the record does not "
                    "support."
                ),
            }
        )


def make_run(user):
    workspace = GymWorkspace.objects.create(owner=user, title="Appellant brief")
    ingested = ingestion.ingest_upload(BRIEF.encode("utf-8"), filename="brief.txt")
    brief = GymDocument.objects.create(
        workspace=workspace,
        role=GymDocument.BRIEF_UNDER_TEST,
        source_type=GymDocument.UPLOAD,
        title="Appellant Brief of Plaintiff-Appellants",
        extracted_text=ingested["text"],
        extraction_metadata=ingested["metadata"],
    )
    return GymRun.objects.create(workspace=workspace, brief=brief)


@override_settings(AI_DRAFTING_ENABLED=True)
class LongVerdictTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("advocate", password="secret")

    def test_a_verdict_longer_than_its_column_still_completes(self):
        self.assertGreater(len(LONG_VERDICT), VERDICT_LIMIT, "the fixture must exceed the column")

        run = execute_run(make_run(self.user), connector_registry=StubRegistry(), llm_client=VerdictClient())

        self.assertEqual(run.status, GymRun.COMPLETE, run.error)
        # The model's own verdict, clamped -- not the deterministic fallback,
        # which would make the length assertion below prove nothing.
        self.assertEqual(run.assessment_verdict, LONG_VERDICT[:VERDICT_LIMIT])
        self.assertLessEqual(len(run.assessment_verdict), VERDICT_LIMIT)
        run.refresh_from_db()
        self.assertEqual(run.status, GymRun.COMPLETE)

    def test_the_stage_never_writes_more_than_the_column_holds(self):
        # The limit is read from the model, so widening or narrowing the column
        # cannot silently leave the pipeline writing the old width.
        field = GymRun._meta.get_field("assessment_verdict")
        self.assertEqual(VERDICT_LIMIT, field.max_length)


@override_settings(AI_DRAFTING_ENABLED=False)
class FailureReportingTests(TestCase):
    """The handler must report the failure, not raise a second one.

    Whatever made the save fail is still on the instance when the failure path
    saves it, so a handler that rewrites every column raises the same error and
    the row is never updated at all -- which is how a run ends up saying
    "running" with nobody coming back for it. SQLite does not enforce column
    widths, so the database that caught this in production cannot reproduce it
    here; the save itself is made to fail instead.
    """

    def test_a_run_whose_save_fails_is_reported_as_failed(self):
        run = make_run(User.objects.create_user("advocate", password="secret"))
        original = GymRun.save

        def fails_on_a_full_save(self, *args, **kwargs):
            # Exactly the shape of the production failure: writing every column
            # raises, writing only the named ones does not.
            if kwargs.get("update_fields") is None:
                raise DataError("value too long for type character varying(60)")
            return original(self, *args, **kwargs)

        with patch.object(GymRun, "save", fails_on_a_full_save):
            finished = execute_run(run, connector_registry=StubRegistry())

        self.assertEqual(finished.status, GymRun.FAILED)
        self.assertIn("too long", finished.error)
        finished.refresh_from_db()
        self.assertEqual(finished.status, GymRun.FAILED, "the failure never reached the database")
        self.assertIsNotNone(finished.completed_at)
