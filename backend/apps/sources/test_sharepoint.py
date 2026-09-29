from datetime import timedelta
from unittest.mock import Mock

import requests
from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory, override_settings
from django.utils import timezone

from apps.sources.connectors.sharepoint import (
    SharePointClient, SharePointConnector, SharePointError, graph_token_for_request,
)
from apps.sources.models import UserOAuthConnection


@override_settings(SHAREPOINT_SITE_ID="site", SHAREPOINT_DRIVE_ID="drive", SHAREPOINT_ACCESS_TOKEN="service")
class GraphTests(TestCase):
    def client_for(self, *responses):
        session = Mock()
        session.get.side_effect = responses
        return SharePointClient(session=session, sleep=Mock())

    def response(self, status=200, payload=None, headers=None):
        return Mock(status_code=status, headers=headers or {}, json=Mock(return_value=payload or {}))

    def test_common_failures_are_explicit(self):
        for status, code in [(401, "authentication_required"), (403, "access_denied"), (404, "not_found"), (429, "throttled")]:
            with self.subTest(status=status):
                client = self.client_for(self.response(status, headers={"Retry-After": "30"}))
                with self.assertRaises(SharePointError) as caught:
                    SharePointConnector(client).search("lease")
                self.assertEqual(caught.exception.status_code, status)
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(client.session.get.call_count, 1)

    def test_throttling_has_bounded_retry(self):
        client = self.client_for(self.response(429, headers={"Retry-After": "2"}), self.response(payload={"id": "item"}))
        self.assertEqual(client.get_item("item")["id"], "item")
        client.sleep.assert_called_once_with(2)
        client = self.client_for(self.response(429), self.response(429))
        with self.assertRaises(SharePointError):
            client.get_item("item")
        self.assertEqual(client.session.get.call_count, 2)

    def test_network_and_malformed_response(self):
        for response in [requests.Timeout("secret URL"), self.response(payload=[1])]:
            with self.subTest(response=response):
                with self.assertRaises(SharePointError) as caught:
                    self.client_for(response).get_item("item")
                self.assertNotIn("secret", str(caught.exception))

    def test_encoding_and_provenance_without_download_capability(self):
        item = {"id": "item", "name": "Lease.docx", "webUrl": "https://example.org/lease", "eTag": "v1",
                "lastModifiedDateTime": "2026-09-01T10:00:00Z", "file": {"mimeType": "application/docx"},
                "parentReference": {"path": "/drives/drive/root:/Library"},
                "@microsoft.graph.downloadUrl": "secret"}
        client = self.client_for(self.response(payload={"value": [item, {"folder": {}, "id": "folder"}]}))
        results = SharePointConnector(client).search("tenant's / lease")
        self.assertIn("tenant%27%27s%20%2F%20lease", client.session.get.call_args.args[0])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].metadata["etag"], "v1")
        self.assertEqual(results[0].metadata["driveId"], "drive")
        self.assertNotIn("secret", str(results[0].to_dict()))

    def test_expired_delegated_token_never_falls_back(self):
        user = User.objects.create_user("graph-user")
        UserOAuthConnection.objects.create(user=user, provider="office365", access_token="expired", expires_at=timezone.now()-timedelta(minutes=1))
        request = RequestFactory().get("/")
        request.user, request.session = user, {}
        with self.assertRaises(SharePointError) as caught:
            graph_token_for_request(request)
        self.assertEqual(caught.exception.status_code, 401)
        self.assertFalse(SharePointClient(access_token="").configured)

    def test_http_failure_contract(self):
        import json
        from apps.sources.sharepoint_http import graph_errors
        for status in (401, 403, 404, 429):
            view = graph_errors(Mock(side_effect=SharePointError("Failure", status_code=status, retry_after=30 if status == 429 else None)))
            response = view(None)
            self.assertEqual(response.status_code, status)
            self.assertEqual(json.loads(response.content)["error"], "Failure")
            if status == 429:
                self.assertEqual(response["Retry-After"], "30")
