import hashlib
import json
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings

from apps.core.storage import VALIDATED, get_document_storage
from apps.sources.connectors.sharepoint import SharePointClient, SharePointError
from apps.sources.sharepoint_import import import_sharepoint_source
from apps.sources.test_publication import ManagedSourceFixture


@override_settings(SHAREPOINT_SITE_ID="site", SHAREPOINT_DRIVE_ID="drive", SHAREPOINT_ACCESS_TOKEN="token")
class GraphDownloadTests(TestCase):
    def setUp(self):
        self.item = {"id": "item", "name": "guide.txt", "file": {"mimeType": "text/plain"}, "eTag": "v1", "size": 4}
        self.session = Mock()
        self.client = SharePointClient(session=self.session)
        self.client.get_item = Mock(return_value=self.item)

    def response(self, status=200, headers=None):
        return Mock(status_code=status, headers=headers or {}, iter_content=Mock(return_value=iter([b"text"])))

    def test_direct_content_preserves_checksum_and_version(self):
        self.session.get.return_value = self.response()
        document = self.client.get_document("item")
        self.assertEqual(document["content"], b"text")
        self.assertEqual(document["metadata"]["etag"], "v1")
        self.assertEqual(document["metadata"]["sha256"], hashlib.sha256(b"text").hexdigest())
        self.assertEqual(self.client.get_item.call_count, 2)

    @patch("apps.sources.connectors.sharepoint.requests.Session")
    def test_redirect_download_has_no_graph_credentials(self, factory):
        self.session.get.return_value = self.response(302, {"Location": "https://tenant.sharepoint.com/download?secret=capability"})
        download = factory.return_value.__enter__.return_value
        download.get.return_value.__enter__.return_value = self.response()
        document = self.client.get_document("item")
        self.assertFalse(download.trust_env)
        self.assertNotIn("headers", download.get.call_args.kwargs)
        self.assertFalse(download.get.call_args.kwargs["allow_redirects"])
        self.assertNotIn("capability", str(document))

    def test_unsafe_redirect_and_oversize_and_changing_version_are_rejected(self):
        for url in ["http://tenant.sharepoint.com/download", "https://localhost/download", "https://tenant.sharepoint.com.evil.test/download"]:
            self.session.get.return_value = self.response(302, {"Location": url})
            with self.assertRaises(SharePointError):
                self.client.get_document("item")
        self.session.get.return_value = self.response()
        with self.assertRaises(SharePointError) as caught:
            self.client.get_document("item", max_bytes=3)
        self.assertEqual(caught.exception.code, "too_large")
        self.session.get.return_value = self.response()
        self.client.get_item.side_effect = [self.item, {**self.item, "eTag": "v2"}]
        with self.assertRaises(SharePointError) as caught:
            self.client.get_document("item")
        self.assertEqual(caught.exception.code, "version_changed")

    def test_stream_limit_works_when_reported_size_is_wrong(self):
        self.client.get_item.return_value = {**self.item, "size": 0}
        self.session.get.return_value = self.response()
        with self.assertRaises(SharePointError) as caught:
            self.client.get_document("item", max_bytes=3)
        self.assertEqual(caught.exception.code, "too_large")

    def test_folder_is_not_downloaded(self):
        self.client.get_item.return_value = {"id": "folder", "folder": {}}
        with self.assertRaises(SharePointError):
            self.client.get_document("folder")
        self.session.get.assert_not_called()

    def test_truncated_body_is_not_importable(self):
        self.client.get_item.return_value = {**self.item, "size": 10}
        self.session.get.return_value = self.response()
        with self.assertRaises(SharePointError) as caught:
            self.client.get_document("item")
        self.assertEqual(caught.exception.code, "download_failed")


class SharePointImportTests(ManagedSourceFixture, TestCase):
    def graph_client(self, content=b"Approved library text"):
        client = Mock(drive_id="drive")
        client.get_document.return_value = {"content": content, "metadata": {
            "itemId": "item", "driveId": "drive", "siteId": "site", "etag": "v1", "name": "guide.txt",
            "mimeType": "text/plain", "modifiedAt": "2026-09-01T10:00:00Z", "fetchedAt": "2026-09-28T10:00:00Z",
            "webUrl": "https://tenant.sharepoint.com/guide.txt", "path": "/root:/Library",
            "sha256": hashlib.sha256(content).hexdigest(),
        }}
        return client

    def approve(self):
        self.source.source_system_id = "sharepoint:drive:item"
        self.source.save()

    def test_unapproved_or_other_drive_cannot_import(self):
        client = self.graph_client()
        for binding in ("", "sharepoint:other:item"):
            self.source.source_system_id = binding
            with self.assertRaises(SharePointError):
                import_sharepoint_source(self.source, client=client)
        client.get_document.assert_not_called()
        self.assertFalse(self.source.versions.exists())

    def test_import_stages_reviewable_version_with_persisted_provenance_and_is_idempotent(self):
        self.approve()
        client = self.graph_client()
        version, created = import_sharepoint_source(self.source, client=client, actor=self.user)
        self.assertTrue(created)
        self.assertEqual(version.status, "pending_review")
        self.source.refresh_from_db()
        self.assertIsNone(self.source.current_version)
        self.assertEqual(version.source_etag, "v1")
        self.assertEqual(version.source_provenance["itemId"], "item")
        with get_document_storage(VALIDATED).open(version.validated_manifest_key) as artifact:
            manifest = json.load(artifact)
        self.assertEqual(manifest["version"]["source_provenance"]["path"], "/root:/Library")
        again, created = import_sharepoint_source(self.source, client=client)
        self.assertFalse(created)
        self.assertEqual(again.pk, version.pk)

    def test_extraction_failure_is_recorded(self):
        self.approve()
        version, _ = import_sharepoint_source(self.source, client=self.graph_client(b""))
        self.assertEqual(version.status, "failed")
        self.assertTrue(version.error)
        self.assertEqual(version.source_provenance["itemId"], "item")

    def test_import_provenance_is_read_only_in_admin(self):
        from django.contrib.admin.sites import site
        from apps.sources.admin import ManagedSourceVersionAdmin
        from apps.sources.models import ManagedSourceVersion
        admin = ManagedSourceVersionAdmin(ManagedSourceVersion, site)
        self.assertIn("source_provenance", admin.readonly_fields)
