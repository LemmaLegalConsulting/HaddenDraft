from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings

from apps.matters.models import Matter
from apps.sources.connectors.legalserver import LegalServerClient, LegalServerConnector, LegalServerError, matter_payload_to_defaults
from apps.sources.connectors.sharepoint import SharePointClient, SharePointConnector, graph_token_for_request
from apps.sources.models import SourceConfiguration, UserOAuthConnection
from apps.sources.registry import ConnectorRegistry


class FakeResponse:
    def __init__(self, payload, status_code=200, headers=None, text=""):
        self.payload = payload
        self.status_code = status_code
        self.headers = headers or {"content-type": "application/json"}
        self.text = text

    def json(self):
        if isinstance(self.payload, BaseException):
            raise self.payload
        return self.payload


class FakeSession:
    def __init__(self, payload, status_code=200, headers=None, text=""):
        self.payload = payload
        self.status_code = status_code
        self.headers = headers
        self.text = text
        self.calls = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
        return FakeResponse(self.payload, status_code=self.status_code, headers=self.headers, text=self.text)


class LegalServerClientTests(TestCase):
    @override_settings(
        LEGALSERVER_BASE_URL="https://example.legalserver.org",
        LEGALSERVER_API_TOKEN="token",
        LEGALSERVER_MATTERS_PATH="/api/v2/matters",
        LEGALSERVER_MATTERS_RESULTS="full",
    )
    def test_search_matters_uses_v2_full_results_shape(self):
        session = FakeSession({"results": [{"id": "123"}]})
        client = LegalServerClient(session=session)

        matters = client.search_matters(query="repair", user_email="advocate@example.org", limit=7)

        self.assertEqual(matters, [{"id": "123"}])
        call = session.calls[0]
        self.assertEqual(call["url"], "https://example.legalserver.org/api/v2/matters")
        self.assertEqual(call["headers"]["Authorization"], "Bearer token")
        self.assertEqual(call["params"]["page_size"], 7)
        searched_fields = {
            next(key for key in call["params"] if key not in ("page_size", "results")) for call in session.calls
        }
        self.assertEqual(searched_fields, {"case_number", "case_title", "external_id", "first", "last"})
        self.assertTrue(all(call["params"]["results"] == "full" for call in session.calls))
        self.assertTrue(all("caseworker" not in call["params"] for call in session.calls))

    def test_matter_payload_normalization_accepts_common_field_names(self):
        defaults = matter_payload_to_defaults(
            {
                "client": "Jane Tenant",
                "case_type": "Eviction",
                "court": "Housing Court",
                "case_summary": "Nonpayment case with repair issues.",
            }
        )

        self.assertEqual(defaults["client_name"], "Jane Tenant")
        self.assertEqual(defaults["matter_type"], "Eviction")
        self.assertEqual(defaults["jurisdiction"], "Housing Court")
        self.assertIn("repair", defaults["summary"])

    @override_settings(
        LEGALSERVER_BASE_URL="https://env.legalserver.org",
        LEGALSERVER_API_TOKEN="env-token",
        LEGALSERVER_MATTERS_PATH="/env/matters",
        LEGALSERVER_MATTERS_RESULTS="full",
        LEGALSERVER_USER_FILTER_PARAM="env_user",
    )
    def test_admin_source_configuration_overrides_legalserver_env_defaults(self):
        SourceConfiguration.objects.create(
            name="LegalServer",
            kind="legalserver",
            legalserver_base_url="https://admin.legalserver.org",
            legalserver_api_token="admin-token",
            legalserver_matters_path="/admin/matters",
            legalserver_user_filter_param="admin_user",
        )
        session = FakeSession({"results": []})
        client = LegalServerClient(session=session)

        client.search_matters(user_email="advocate@example.org")

        call = session.calls[0]
        self.assertEqual(call["url"], "https://admin.legalserver.org/admin/matters")
        self.assertEqual(call["headers"]["Authorization"], "Bearer admin-token")
        self.assertEqual(call["params"], {"page_size": 25, "results": "full"})

    @override_settings(
        LEGALSERVER_BASE_URL="https://example.legalserver.org",
        LEGALSERVER_API_TOKEN="token",
        LEGALSERVER_MATTERS_PATH="/api/v2/matters",
    )
    def test_error_includes_legalserver_response_detail(self):
        session = FakeSession({"detail": "Unknown query parameter assigned_user_email"}, status_code=400)
        client = LegalServerClient(session=session)

        with self.assertRaises(LegalServerError) as context:
            client.search_matters(user_email="advocate@example.org")

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("Unknown query parameter assigned_user_email", str(context.exception))

    @override_settings(
        LEGALSERVER_BASE_URL="https://example.legalserver.org",
        LEGALSERVER_API_TOKEN="token",
        LEGALSERVER_MATTERS_PATH="/api/v2/matters",
        LEGALSERVER_MATTERS_RESULTS="full",
        LEGALSERVER_USER_FILTER_PARAM="",
    )
    def test_user_email_is_not_sent_as_a_matter_search_filter(self):
        session = FakeSession({"results": []})
        client = LegalServerClient(session=session)

        client.search_matters(user_email="advocate@example.org")

        self.assertEqual(session.calls[0]["params"], {"page_size": 25, "results": "full"})


class LegalServerConnectorTests(TestCase):
    def test_connector_returns_case_documents_for_selected_matter(self):
        matter = Matter.objects.create(
            external_id="LS-1",
            client_name="Jane Tenant",
            matter_type="Eviction",
            jurisdiction="Housing Court",
        )
        client = SimpleNamespace(
            configured=True,
            get_matter_documents=lambda matter_id: [
                {
                    "id": "doc-1",
                    "title": "Notice to Quit",
                    "storage_provider": "LegalServer",
                    "download_url": "https://files.example/doc-1",
                }
            ],
        )
        connector = LegalServerConnector(client=client)

        results = connector.search("notice", matter=matter)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Notice to Quit")
        self.assertEqual(results[0].metadata["storage"], "LegalServer")


class SharePointClientTests(TestCase):
    @override_settings(SHAREPOINT_SITE_ID="site", SHAREPOINT_DRIVE_ID="drive", SHAREPOINT_ACCESS_TOKEN="token")
    def test_search_drive_uses_graph_with_bearer_token(self):
        session = FakeSession({"value": [{"id": "item-1", "name": "Guide.docx"}]})
        client = SharePointClient(session=session)

        items = client.search_drive("habitability", limit=3)

        self.assertEqual(items[0]["name"], "Guide.docx")
        call = session.calls[0]
        self.assertIn("graph.microsoft.com/v1.0/sites/site/drives/drive/root/search", call["url"])
        self.assertEqual(call["headers"]["Authorization"], "Bearer token")
        self.assertEqual(call["params"]["$top"], 3)

    def test_graph_token_prefers_django_session(self):
        request = RequestFactory().get("/")
        request.session = {"ms_graph_access_token": "delegated"}

        self.assertEqual(graph_token_for_request(request), "delegated")

    @override_settings(SHAREPOINT_SITE_ID="env-site", SHAREPOINT_DRIVE_ID="env-drive", SHAREPOINT_ACCESS_TOKEN="env-token")
    def test_admin_source_configuration_overrides_sharepoint_env_defaults(self):
        SourceConfiguration.objects.create(
            name="SharePoint",
            kind="sharepoint",
            sharepoint_site_id="admin-site",
            sharepoint_drive_id="admin-drive",
            sharepoint_server_access_token="admin-token",
        )
        session = FakeSession({"value": []})
        client = SharePointClient(session=session)

        client.search_drive("rent")

        call = session.calls[0]
        self.assertIn("/sites/admin-site/drives/admin-drive/", call["url"])
        self.assertEqual(call["headers"]["Authorization"], "Bearer admin-token")

    @override_settings(SHAREPOINT_ACCESS_TOKEN="server-token")
    def test_graph_token_prefers_saved_office365_user_connection_over_server_token(self):
        user = User.objects.create_user(username="advocate", email="advocate@example.org")
        UserOAuthConnection.objects.create(user=user, provider="office365", access_token="user-token")
        request = RequestFactory().get("/")
        request.session = {}
        request.user = user

        self.assertEqual(graph_token_for_request(request), "user-token")


class SharePointConnectorTests(TestCase):
    def test_connector_lists_case_folder_documents(self):
        matter = Matter.objects.create(
            external_id="LS-1",
            client_name="Jane Tenant",
            matter_type="Eviction",
            jurisdiction="Housing Court",
        )
        client = SimpleNamespace(
            configured=True,
            list_case_documents=lambda matter_id, limit=5: [
                {"id": "sp-1", "name": "Photos.pdf", "webUrl": "https://sharepoint/doc"}
            ],
        )
        connector = SharePointConnector(client=client)

        results = connector.search("photos", matter=matter)

        self.assertEqual(results[0].source_kind, "sharepoint")
        self.assertEqual(results[0].url, "https://sharepoint/doc")


class ConnectorRegistryTests(TestCase):
    def test_registry_passes_user_and_request_to_connectors(self):
        seen = {}

        class RecordingConnector:
            kind = "recording"

            def search(self, query, **kwargs):
                seen.update(kwargs)
                return []

        registry = ConnectorRegistry()
        registry.register(RecordingConnector())
        user = User(username="advocate", email="advocate@example.org")
        request = SimpleNamespace(session={})

        registry.search("repair", user=user, request=request)

        self.assertEqual(seen["user"], user)
        self.assertEqual(seen["request"], request)
