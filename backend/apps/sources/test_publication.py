import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from apps.core.storage import PUBLISHED, RAW, VALIDATED, get_document_storage
from apps.sources.models import ManagedSource, ManagedSourceEvent
from apps.sources.publication import PublicationError, import_version, publish_version, retire_source, rollback_source
from apps.sources.research.corpus import managed_records


class ManagedSourcePublicationTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = override_settings(
            DOCUMENT_STORAGE_BACKEND="filesystem",
            DOCUMENT_STORAGE_ROOT=Path(self.temp.name),
        )
        self.settings.enable()
        self.user = User.objects.create_user("operator")
        self.source = ManagedSource.objects.create(
            slug="iskin-treatise", title="Iskin Treatise", kind="treatise",
            jurisdiction="Ohio", created_by=self.user,
        )

    def tearDown(self):
        self.settings.disable()
        self.temp.cleanup()

    def import_text(self, text, *, publish=True, filename="iskin.txt"):
        return import_version(
            source=self.source, content=text.encode(), filename=filename,
            content_type="text/plain", actor=self.user, publish=publish,
        )

    def test_create_writes_each_area_and_makes_chunks_retrievable_with_provenance(self):
        version, created = self.import_text("Security deposits\n\nA landlord must itemize deductions.")

        self.assertTrue(created)
        self.source.refresh_from_db()
        version.refresh_from_db()
        self.assertEqual(self.source.current_version, version)
        self.assertEqual(self.source.state, "published")
        self.assertTrue(get_document_storage(RAW).exists(version.raw_key))
        self.assertTrue(get_document_storage(VALIDATED).exists(version.validated_manifest_key))
        self.assertTrue(get_document_storage(PUBLISHED).exists(version.published_manifest_key))
        self.assertTrue(get_document_storage(PUBLISHED).exists(version.published_source_key))
        record = managed_records()[0]
        self.assertEqual(record.metadata["sourceSha256"], version.sha256)
        self.assertEqual(record.metadata["managedSourceVersionId"], version.id)
        self.assertIn("itemize", record.text)
        self.client.force_login(self.user)
        response = self.client.get(record.open_target["sourceUrl"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source"]["sourceSha256"], version.sha256)

    def test_update_replaces_live_chunks_without_deleting_history(self):
        first, _ = self.import_text("old unique wording")
        second, _ = self.import_text("new unique wording")

        self.source.refresh_from_db()
        first.refresh_from_db()
        self.assertEqual(self.source.current_version, second)
        self.assertEqual(first.status, "superseded")
        live_text = " ".join(record.text for record in managed_records())
        self.assertIn("new unique wording", live_text)
        self.assertNotIn("old unique wording", live_text)
        self.assertTrue(get_document_storage(RAW).exists(first.raw_key))

    def test_unchanged_import_is_an_idempotent_no_op(self):
        first, created = self.import_text("same source")
        again, created_again = self.import_text("same source")

        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first.id, again.id)
        self.assertEqual(self.source.versions.count(), 1)

    def test_invalid_import_never_changes_the_live_version(self):
        live, _ = self.import_text("valid published source")
        failed, created = import_version(
            source=self.source, content=b"not a supported format", filename="scan.bin",
            actor=self.user, publish=True,
        )

        self.assertTrue(created)
        failed.refresh_from_db()
        self.source.refresh_from_db()
        self.assertEqual(failed.status, "failed")
        self.assertEqual(self.source.current_version, live)
        self.assertEqual(self.source.state, "published")
        self.assertFalse(get_document_storage(PUBLISHED).exists(failed.raw_key))

    def test_retire_and_rollback_preserve_an_attributable_history(self):
        first, _ = self.import_text("first edition")
        self.import_text("second edition")
        retire_source(self.source, actor=self.user)
        self.source.refresh_from_db()
        self.assertEqual(self.source.state, "retired")
        self.assertEqual(managed_records(), [])

        rollback_source(self.source, first, actor=self.user)
        self.source.refresh_from_db()
        self.assertEqual(self.source.current_version, first)
        self.assertEqual(self.source.state, "published")
        self.assertIn("first edition", managed_records()[0].text)
        self.assertTrue(ManagedSourceEvent.objects.filter(action="retired", actor=self.user).exists())
        self.assertTrue(ManagedSourceEvent.objects.filter(action="rolled_back", actor=self.user).exists())

    def test_storage_failure_cannot_move_the_live_pointer(self):
        live, _ = self.import_text("live edition")
        candidate, _ = self.import_text("candidate edition", publish=False)
        published = get_document_storage(PUBLISHED)
        with patch("apps.sources.publication.get_document_storage", side_effect=lambda area: (
            type("Broken", (), {"put_bytes": lambda *args, **kwargs: (_ for _ in ()).throw(OSError("down"))})()
            if area == PUBLISHED else get_document_storage(area)
        )):
            with self.assertRaises(PublicationError):
                publish_version(candidate, actor=self.user)

        self.source.refresh_from_db()
        self.assertEqual(self.source.current_version, live)
        self.assertTrue(published.exists(live.published_manifest_key))

    def test_case_import_proposes_metadata_but_waits_for_review(self):
        case = ManagedSource.objects.create(slug="tenant-v-landlord", title="Uploaded decision", kind="case")
        text = """IN THE COURT OF APPEALS OF OHIO\nTenant v. Landlord\n2026-Ohio-123\nSeptember 4, 2026\n\nOPINION\nThe judgment is affirmed."""
        version, _ = import_version(
            source=case, content=text.encode(), filename="decision.txt", content_type="text/plain",
            actor=self.user, publish=False,
        )

        case.refresh_from_db()
        self.assertEqual(version.status, "pending_review")
        self.assertEqual(case.state, "draft")
        self.assertEqual(case.citation, "2026-Ohio-123")
        self.assertEqual(case.decision_date.isoformat(), "2026-09-04")
        self.assertIn("Tenant v. Landlord", case.title)
