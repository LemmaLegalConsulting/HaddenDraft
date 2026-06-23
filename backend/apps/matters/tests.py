import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from apps.matters.models import Matter
from apps.sources.models import UserSourceIdentity


class FakeLegalServerClient:
    configured = True
    user_filter_param = "assigned_user_email"

    def __init__(self):
        self.calls = []

    def search_matters(self, *, query="", user_email="", limit=50):
        self.calls.append({"query": query, "user_email": user_email, "limit": limit})
        return [
            {
                "id": "LS-REAL-1",
                "client_name": "Real Client",
                "matter_type": "Eviction defense",
                "court": "Housing Court",
                "assignments": [{"user": {"user_name": "quinten"}}],
            }
        ]

    def get_matter(self, matter_id):
        return {
            "id": matter_id,
            "client_name": "Direct Match",
            "matter_type": "Conditions",
            "court": "Housing Court",
        }


@override_settings(ENABLE_DEMO_MATTERS=False)
class CaseConnectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="quinten@lemmalegal.com",
            email="quinten@lemmalegal.com",
            password="password",
        )
        self.client.force_login(self.user)

    @patch("apps.matters.services.LegalServerClient")
    def test_unconnected_user_sees_no_cases_instead_of_demo_seed(self, client_class):
        fake_client = FakeLegalServerClient()
        client_class.return_value = fake_client

        response = self.client.get("/api/cases/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["cases"], [])
        self.assertFalse(payload["legalserver"]["connected"])
        self.assertEqual(payload["legalserver"]["syncError"], "not_connected")
        self.assertEqual(payload["legalserver"]["suggestedIdentifier"], "quinten@lemmalegal.com")
        self.assertFalse(Matter.objects.exists())
        self.assertEqual(fake_client.calls, [])

    @patch("apps.matters.services.LegalServerClient")
    def test_connected_user_filters_legalserver_by_saved_identifier(self, client_class):
        fake_client = FakeLegalServerClient()
        client_class.return_value = fake_client
        UserSourceIdentity.objects.create(
            user=self.user,
            provider="legalserver",
            identifier="quinten@lemmalegal.com",
        )

        response = self.client.get("/api/cases/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["cases"][0]["id"], "LS-REAL-1")
        self.assertTrue(payload["legalserver"]["connected"])
        self.assertEqual(fake_client.calls[0]["user_email"], "quinten@lemmalegal.com")

    @patch("apps.matters.services.LegalServerClient")
    def test_case_search_does_not_limit_to_primary_assignment(self, client_class):
        fake_client = FakeLegalServerClient()
        client_class.return_value = fake_client
        UserSourceIdentity.objects.create(
            user=self.user,
            provider="legalserver",
            identifier="quinten@lemmalegal.com",
        )

        response = self.client.get("/api/cases/?q=Acme")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["cases"][0]["id"], "LS-REAL-1")
        self.assertEqual(fake_client.calls[0]["query"], "Acme")
        self.assertEqual(fake_client.calls[0]["user_email"], "")

    def test_user_can_connect_legalserver_identifier_without_admin(self):
        response = self.client.post(
            "/api/legalserver/account/",
            data=json.dumps({"identifier": "quinten@lemmalegal.com"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["legalserver"]["connected"])
        identity = UserSourceIdentity.objects.get(user=self.user, provider="legalserver")
        self.assertEqual(identity.identifier, "quinten@lemmalegal.com")
