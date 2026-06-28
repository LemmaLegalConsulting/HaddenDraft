import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings

from apps.matters.models import Matter
from apps.sources.connectors.base import SourceResult
from apps.sources.connectors.legalserver import LegalServerClient, LegalServerConnector, LegalServerError, matter_payload_to_defaults
from apps.sources.connectors.sharepoint import SharePointClient, SharePointConnector, graph_token_for_request
from apps.sources.connectors.user_resources import UserResourceConnector
from apps.sources.connectors.rag import ContentLibraryTreatiseConnector
from apps.sources.models import SourceConfiguration, UserOAuthConnection, UserResource
from apps.sources.registry import ConnectorRegistry
from apps.sources.selection import automatic_source_selection


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


class UserResourceConnectorTests(TestCase):
    def test_connector_returns_only_current_users_private_references(self):
        user = User.objects.create_user(username="advocate")
        other = User.objects.create_user(username="other")
        UserResource.objects.create(
            user=user,
            title="Habitability brief",
            resource_type="brief",
            text="Example argument about mold and repair evidence.",
        )
        UserResource.objects.create(
            user=other,
            title="Other user's brief",
            resource_type="brief",
            text="Example argument about mold and repair evidence.",
        )

        results = UserResourceConnector().search("mold repair", user=user)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Habitability brief")
        self.assertEqual(results[0].source_label, "Private reference")
        self.assertTrue(results[0].metadata["private"])


class ContentLibraryTreatiseConnectorTests(TestCase):
    @override_settings(AI_DRAFTING_ENABLED=False)
    def test_searches_generated_chunks_and_retains_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            library = Path(directory)
            version = library / "treatises" / "markdown" / "green-book" / "2026-01"
            chunks = version / "chunks"
            chunks.mkdir(parents=True)
            (chunks / "0001-repairs.md").write_text(
                "---\nchunk_id: 0001-repairs\n---\n\n# Repairs\n\n## Source text\n\n"
                "A tenant may raise unsafe repair conditions after giving the landlord notice.\n",
                encoding="utf-8",
            )
            (version / "manifest.yaml").write_text(
                "document_slug: green-book\n"
                "document_title: Sample Housing Treatise\n"
                "document_version: 2026 edition\n"
                "source_path: treatises/source/sample/2026.pdf\n"
                "source_sha256: abc123\n"
                "chunks:\n"
                "- id: 0001-repairs\n"
                "  file: chunks/0001-repairs.md\n"
                "  heading: Repair conditions\n"
                "  path: [Chapter 1, Repair conditions]\n"
                "  pages: [12, 13]\n"
                "  content_kind: substantive-section\n"
                "  source_path: treatises/source/green-book/repairs.pdf\n"
                "  source_sha256: per-file-sha\n",
                encoding="utf-8",
            )
            with override_settings(CONTENT_LIBRARY_DIR=library):
                results = ContentLibraryTreatiseConnector().search(
                    "habitability repair defense", source_ids=["green-book"]
                )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source_kind, "rag")
        self.assertIn("Sample Housing Treatise", results[0].citation)
        self.assertIn("PDF pp. 12–13", results[0].citation)
        self.assertEqual(results[0].metadata["chunkId"], "0001-repairs")
        self.assertEqual(results[0].metadata["sourceSha256"], "per-file-sha")
        self.assertEqual(results[0].metadata["sourcePath"], "treatises/source/green-book/repairs.pdf")

    @override_settings(AI_DRAFTING_ENABLED=False)
    def test_searches_generated_statute_chunks_with_official_citation_and_url(self):
        with tempfile.TemporaryDirectory() as directory:
            library = Path(directory)
            statute = library / "statutes" / "ohio-revised-code"
            chunks = statute / "chunks"
            chunks.mkdir(parents=True)
            (chunks / "orc-5321-04-01.md").write_text(
                "# Ohio Rev. Code § 5321.04 — Landlord obligations\n\n## Source text\n\n"
                "A landlord shall make repairs necessary to keep premises fit and habitable.\n",
                encoding="utf-8",
            )
            (statute / "manifest.yaml").write_text(
                "document_slug: ohio-revised-code\n"
                "document_title: Ohio Revised Code\n"
                "jurisdiction: Ohio\n"
                "chunks:\n"
                "- id: orc-5321-04-01\n"
                "  file: chunks/orc-5321-04-01.md\n"
                "  heading: Ohio Rev. Code § 5321.04 — Landlord obligations\n"
                "  path: [Ohio Revised Code, Chapter 5321, § 5321.04]\n"
                "  content_kind: statute-section\n"
                "  citation: Ohio Rev. Code § 5321.04\n"
                "  url: https://codes.ohio.gov/ohio-revised-code/section-5321.04\n"
                "  effective_date: September 28, 2012\n",
                encoding="utf-8",
            )
            with override_settings(CONTENT_LIBRARY_DIR=library):
                results = ContentLibraryTreatiseConnector().search(
                    "landlord repair habitability", source_ids=["ohio-statutes"]
                )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].citation, "Ohio Rev. Code § 5321.04 (effective September 28, 2012)")
        self.assertEqual(results[0].url, "https://codes.ohio.gov/ohio-revised-code/section-5321.04")
        self.assertEqual(results[0].metadata["jurisdiction"], "Ohio")


class UserResourceViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="advocate", password="password")
        self.client.force_login(self.user)

    def test_user_can_upload_private_reference_document(self):
        response = self.client.post(
            "/api/user-resources/",
            data={
                "title": "Sample opposition",
                "resourceType": "brief",
                "file": SimpleUploadedFile(
                    "opposition.txt",
                    b"This example brief argues that rent should be abated for unrepaired mold.",
                    content_type="text/plain",
                ),
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["resource"]["title"], "Sample opposition")
        resource = UserResource.objects.get()
        self.assertEqual(resource.user, self.user)
        self.assertEqual(resource.resource_type, "brief")
        self.assertIn("unrepaired mold", resource.text)

    def test_user_resource_list_is_owner_scoped(self):
        other = User.objects.create_user(username="other")
        mine = UserResource.objects.create(user=self.user, title="My case", resource_type="case", text="Tenant won.")
        UserResource.objects.create(user=other, title="Other case", resource_type="case", text="Hidden.")

        response = self.client.get("/api/user-resources/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()["resources"]], [mine.id])


class ResearchViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="advocate", password="password")
        self.client.force_login(self.user)
        self.result = SourceResult(
            id="source:1",
            title="Habitability guide",
            snippet="Tenant may raise repair conditions as a defense.",
            source_kind="rag",
            source_label="Treatise",
            citation="Housing guide",
        )

    def test_research_without_ai_returns_only_retrieval_results(self):
        registry = SimpleNamespace(search=lambda *args, **kwargs: [self.result])

        with patch("apps.sources.views.connector_registry", registry), patch("apps.sources.views.OpenAICompatibleClient") as ai_client:
            response = self.client.post(
                "/api/research/",
                data=json.dumps({"query": "habitability", "useAi": False, "sourceMode": "auto"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["usedAi"])
        self.assertNotIn("answer", payload)
        self.assertEqual(payload["results"][0]["title"], "Habitability guide")
        self.assertEqual(payload["sourceDecision"]["mode"], "auto")
        self.assertEqual(
            [item["id"] for item in payload["sourceDecision"]["sources"]],
            ["ohio-statutes", "treatise"],
        )
        ai_client.assert_not_called()

    def test_research_with_ai_returns_answer_from_retrieved_sources(self):
        registry = SimpleNamespace(search=lambda *args, **kwargs: [self.result])
        fake_client = SimpleNamespace(complete=lambda **kwargs: "Yes, based on Housing guide.")

        with patch("apps.sources.views.connector_registry", registry), patch("apps.sources.views.OpenAICompatibleClient", return_value=fake_client):
            response = self.client.post(
                "/api/research/",
                data=json.dumps({
                    "query": "Can the tenant raise repairs?",
                    "useAi": True,
                    "messages": [{"role": "user", "content": "Earlier question"}],
                }),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["usedAi"])
        self.assertEqual(payload["answer"], "Yes, based on Housing guide.")
        self.assertEqual(payload["results"][0]["citation"], "Housing guide")
        history = self.client.get("/api/research/").json()["messages"]
        self.assertEqual([message["role"] for message in history], ["user", "assistant"])
        self.assertEqual(history[1]["citations"][0]["citation"], "Housing guide")

    def test_research_uses_the_users_default_jurisdiction_in_the_ai_guardrail(self):
        from apps.core.models import AuthorProfile

        AuthorProfile.objects.create(user=self.user, default_jurisdiction="Ohio")
        registry = SimpleNamespace(search=lambda *args, **kwargs: [self.result])
        captured = {}
        fake_client = SimpleNamespace(complete=lambda **kwargs: captured.update(kwargs) or "Ohio answer [1]")

        with patch("apps.sources.views.connector_registry", registry), patch("apps.sources.views.OpenAICompatibleClient", return_value=fake_client):
            response = self.client.post(
                "/api/research/",
                data=json.dumps({"query": "Can the tenant raise repairs?", "useAi": True}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("selected jurisdiction is Ohio", captured["system"])


class AutomaticSourceSelectionTests(TestCase):
    def test_general_question_explains_the_primary_and_secondary_baseline(self):
        selection = automatic_source_selection("What defenses can a tenant raise in an eviction?")

        self.assertEqual(selection["source_ids"], ["ohio-statutes", "treatise"])
        self.assertIn("Primary-law baseline", selection["annotations"][0]["reason"])
        self.assertIn("Secondary-source baseline", selection["annotations"][1]["reason"])

    def test_hud_question_explains_specialized_routing(self):
        selection = automatic_source_selection("What HUD voucher termination rules apply?")

        self.assertEqual(selection["source_ids"], ["hud-handbook"])
        self.assertEqual(selection["annotations"][0]["reason"], "The question concerns federally assisted housing or a HUD program.")

    def test_public_housing_question_routes_to_green_book(self):
        selection = automatic_source_selection("What rules govern a public housing authority homeownership program?")

        self.assertEqual(selection["source_ids"], ["green-book"])
        self.assertIn("Green Book", selection["annotations"][0]["reason"])


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
