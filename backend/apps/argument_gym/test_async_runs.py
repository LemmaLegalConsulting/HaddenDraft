"""Launching a run without holding the request open for it.

A run is eight sequential model calls and several retrieval rounds. Held open,
it outlives the worker timeout, and a killed worker returns no headers at all --
which a browser reports as a CORS failure rather than as the timeout it is.
"""

import json
import threading
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, TransactionTestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.argument_gym import ingestion
from apps.argument_gym.models import GymDocument, GymRun, GymWorkspace
from apps.argument_gym.pipeline import fail_if_stalled, start_run
from apps.argument_gym.tests import BRIEF, StubRegistry


def make_workspace(user):
    workspace = GymWorkspace.objects.create(owner=user, title="Answer")
    ingested = ingestion.ingest_upload(BRIEF.encode("utf-8"), filename="answer.txt")
    GymDocument.objects.create(
        workspace=workspace,
        role=GymDocument.BRIEF_UNDER_TEST,
        source_type=GymDocument.UPLOAD,
        title="Answer",
        extracted_text=ingested["text"],
        extraction_metadata=ingested["metadata"],
    )
    return workspace


@override_settings(ARGUMENT_GYM_BACKGROUND_RUNS=False, AI_DRAFTING_ENABLED=False)
class SynchronousRunTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("advocate", password="secret")
        self.client.force_login(self.user)
        self.workspace = make_workspace(self.user)

    def test_a_finished_run_answers_200(self):
        response = self.client.post(
            reverse("api_gym_workspace_runs", args=[self.workspace.id]),
            data="{}",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["run"]["status"], GymRun.COMPLETE)

    def test_a_failed_run_answers_502_rather_than_pretending_to_have_worked(self):
        empty = GymDocument.objects.create(
            workspace=self.workspace,
            role=GymDocument.BRIEF_UNDER_TEST,
            source_type=GymDocument.UPLOAD,
            title="Empty",
        )
        response = self.client.post(
            reverse("api_gym_workspace_runs", args=[self.workspace.id]),
            data=json.dumps({"briefId": empty.id}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["run"]["status"], GymRun.FAILED)


@override_settings(AI_DRAFTING_ENABLED=False)
class StalledRunTests(TestCase):
    """A replica that died mid-run leaves a row nothing will ever finish."""

    def setUp(self):
        self.user = User.objects.create_user("advocate", password="secret")
        self.workspace = make_workspace(self.user)

    def _run(self, *, status, age_minutes):
        run = GymRun.objects.create(
            workspace=self.workspace,
            brief=self.workspace.documents.first(),
            status=status,
        )
        GymRun.objects.filter(id=run.id).update(created_at=timezone.now() - timedelta(minutes=age_minutes))
        run.refresh_from_db()
        return run

    def test_a_run_still_within_its_budget_is_left_alone(self):
        run = fail_if_stalled(self._run(status=GymRun.RUNNING, age_minutes=5))
        self.assertEqual(run.status, GymRun.RUNNING)

    def test_a_run_past_the_budget_is_reported_failed_rather_than_running_forever(self):
        run = fail_if_stalled(self._run(status=GymRun.RUNNING, age_minutes=45))
        self.assertEqual(run.status, GymRun.FAILED)
        self.assertIn("interrupted by a restart", run.error)
        self.assertIn("Nothing was written to your draft", run.error)
        run.refresh_from_db()
        self.assertEqual(run.status, GymRun.FAILED)

    def test_a_finished_run_is_never_rewritten_by_the_guard(self):
        run = fail_if_stalled(self._run(status=GymRun.COMPLETE, age_minutes=600))
        self.assertEqual(run.status, GymRun.COMPLETE)
        self.assertEqual(run.error, "")

    def test_polling_a_stalled_run_reports_the_failure(self):
        run = self._run(status=GymRun.RUNNING, age_minutes=45)
        self.client.force_login(self.user)
        payload = self.client.get(reverse("api_gym_run_detail", args=[run.id])).json()
        self.assertEqual(payload["run"]["status"], GymRun.FAILED)


@override_settings(AI_DRAFTING_ENABLED=False)
class BackgroundRunTests(TransactionTestCase):
    """The background path needs real committed rows, so it cannot use TestCase."""

    def setUp(self):
        self.user = User.objects.create_user("advocate", password="secret")
        self.client.force_login(self.user)
        self.workspace = make_workspace(self.user)

    def _wait_for(self, run_id, *, seconds=30):
        for thread in threading.enumerate():
            if thread.name == f"gym-run-{run_id}":
                thread.join(timeout=seconds)
        return GymRun.objects.get(id=run_id)

    def test_the_request_returns_immediately_with_a_run_to_poll(self):
        response = self.client.post(
            reverse("api_gym_workspace_runs", args=[self.workspace.id]),
            data="{}",
            content_type="application/json",
        )
        # 202: the work was accepted, not finished. Holding the request until it
        # was would outlive the worker timeout.
        self.assertEqual(response.status_code, 202)
        payload = response.json()["run"]
        self.assertIn(payload["status"], {GymRun.PENDING, GymRun.RUNNING})
        self.assertTrue(payload["id"])
        self._wait_for(payload["id"])

    def test_the_run_finishes_on_its_own_and_polling_sees_it(self):
        run_id = self.client.post(
            reverse("api_gym_workspace_runs", args=[self.workspace.id]),
            data="{}",
            content_type="application/json",
        ).json()["run"]["id"]
        run = self._wait_for(run_id)
        self.assertEqual(run.status, GymRun.COMPLETE, run.error)
        self.assertTrue(run.challenges.exists())
        payload = self.client.get(reverse("api_gym_run_detail", args=[run_id])).json()
        self.assertEqual(payload["run"]["status"], GymRun.COMPLETE)
        self.assertTrue(payload["run"]["challenges"])

    def test_progress_is_visible_while_the_run_is_still_going(self):
        run = GymRun.objects.create(workspace=self.workspace, brief=self.workspace.documents.first())
        seen = []

        original = GymRun.save

        def watch(self, *args, **kwargs):
            original(self, *args, **kwargs)
            if self.id == run.id and self.status == GymRun.RUNNING:
                seen.append(len(self.stage_trace or []))

        GymRun.save = watch
        try:
            start_run(run, connector_registry=StubRegistry())
            self._wait_for(run.id)
        finally:
            GymRun.save = original
        # Stages are saved as they finish rather than only at the end, so a
        # client polling can say which stage the run is on.
        self.assertTrue(seen, "no progress was written while the run was going")
        self.assertEqual(seen, sorted(seen))
        self.assertGreater(max(seen), 1)
