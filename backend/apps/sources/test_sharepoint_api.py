from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from apps.sources.connectors.sharepoint import SharePointError
from apps.sources.models import RetrievedDocument, ManagedSource


@override_settings(SHAREPOINT_SITE_ID="site", SHAREPOINT_DRIVE_ID="drive", SHAREPOINT_ACCESS_TOKEN="service")
class PrecedentSearchTests(TestCase):
    url = "/api/sharepoint/precedents/"

    def setUp(self):
        self.user = User.objects.create_user("searcher")
        self.client.force_login(self.user)

    @patch("apps.sources.connectors.sharepoint.SharePointClient.search_drive")
    def test_normalized_results_and_no_persistence(self, search):
        search.return_value = [{"id": "item", "name": "Brief.docx", "webUrl": "https://tenant.sharepoint.com/Brief.docx",
                                "file": {"mimeType": "application/docx"}, "eTag": "v3"}]
        response = self.client.get(self.url, {"q": " rent ", "limit": 3, "driveId": "ignored"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        search.assert_called_once_with("rent", limit=3)
        self.assertEqual(payload["results"][0]["sourceKind"], "sharepoint")
        self.assertEqual(payload["results"][0]["metadata"]["driveId"], "drive")
        self.assertFalse(payload["usedAi"])
        self.assertIn("No AI", payload["aiSummary"])
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertFalse(RetrievedDocument.objects.exists())
        self.assertFalse(ManagedSource.objects.exists())

    @patch("apps.sources.connectors.sharepoint.SharePointClient.search_drive")
    def test_validation_and_authentication_do_not_query_graph(self, search):
        for params in ({}, {"q": " "}, {"q": "x"*501}, {"q": "rent", "limit": "bad"}, {"q": "rent", "limit": 0}, {"q": "rent", "limit": 51}):
            self.assertEqual(self.client.get(self.url, params).status_code, 400)
        self.assertEqual(self.client.post(self.url, {"q": "rent"}).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.get(self.url, {"q": "rent"}).status_code, 401)
        search.assert_not_called()

    @patch("apps.sources.connectors.sharepoint.SharePointClient.search_drive")
    def test_empty_and_failed_are_distinct(self, search):
        search.return_value = []
        self.assertEqual(self.client.get(self.url, {"q": "rent"}).json()["results"], [])
        for status in (401, 403, 404, 429):
            search.side_effect = SharePointError("Graph failure", status_code=status, retry_after=30 if status == 429 else None)
            response = self.client.get(self.url, {"q": "rent"})
            self.assertEqual(response.status_code, status)
            self.assertNotIn("results", response.json())

    @override_settings(SHAREPOINT_DRIVE_ID="")
    def test_unconfigured_is_not_an_empty_search(self):
        response = self.client.get(self.url, {"q": "rent"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "not_configured")

    @patch("apps.sources.connectors.sharepoint.requests.Session")
    def test_delegated_failure_does_not_retry_as_service(self, session_factory):
        session = self.client.session
        session["ms_graph_access_token"] = "expired-delegated"
        session.save()
        graph = session_factory.return_value
        graph.get.return_value = Mock(status_code=401)
        self.assertEqual(self.client.get(self.url, {"q": "rent"}).status_code, 401)
        graph.get.assert_called_once()
        self.assertEqual(graph.get.call_args.kwargs["headers"]["Authorization"], "Bearer expired-delegated")
