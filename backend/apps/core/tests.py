import json
import base64
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.contrib import admin
from django.contrib.auth.models import User
from django.test import TestCase, override_settings


class AuthViewTests(TestCase):
    def test_manual_login_uses_django_auth_and_stores_graph_token(self):
        User.objects.create_user(username="advocate", password="secret", email="advocate@example.org")

        response = self.client.post(
            "/api/auth/login/",
            data=json.dumps({"username": "advocate", "password": "secret", "msGraphAccessToken": "graph-token"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["user"]["isAuthenticated"])
        self.assertEqual(response.json()["user"]["profile"]["email"], "advocate@example.org")
        self.assertEqual(self.client.session["ms_graph_access_token"], "graph-token")

    def test_author_profile_can_be_updated(self):
        User.objects.create_user(username="advocate", password="secret", email="advocate@example.org")
        self.client.login(username="advocate", password="secret")

        response = self.client.patch(
            "/api/author-profile/",
            data=json.dumps({
                "displayName": "Ada Advocate",
                "salutation": "Dear Clerk:",
                "signoff": "Respectfully,",
                "phone": "555-0100",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        profile = response.json()["profile"]
        self.assertEqual(profile["displayName"], "Ada Advocate")
        self.assertEqual(profile["signoff"], "Respectfully,")

    def test_me_reports_anonymous_user(self):
        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["user"]["isAuthenticated"])

    @override_settings(OFFICE365_TENANT_ID="", OFFICE365_CLIENT_ID="")
    def test_office365_start_reports_not_configured(self):
        response = self.client.get("/api/auth/office365/start/")

        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["configured"])

    @override_settings(
        OFFICE365_TENANT_ID="tenant",
        OFFICE365_CLIENT_ID="client-id",
        OFFICE365_REDIRECT_URI="http://localhost:8000/api/auth/office365/callback/",
        OFFICE365_SCOPES="openid profile email",
    )
    def test_office365_start_returns_authorization_url(self):
        response = self.client.get("/api/auth/office365/start/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        parsed = urlparse(payload["authUrl"])
        params = parse_qs(parsed.query)
        self.assertEqual(parsed.netloc, "login.microsoftonline.com")
        self.assertEqual(params["client_id"], ["client-id"])
        self.assertEqual(params["scope"], ["openid profile email"])

    @override_settings(FRONTEND_SITE_URL="http://localhost:5173")
    def test_admin_view_site_points_to_frontend(self):
        self.assertEqual(admin.site.site_url, "http://localhost:5173")

    @override_settings(
        OFFICE365_TENANT_ID="organizations",
        OFFICE365_CLIENT_ID="client-id",
        OFFICE365_CLIENT_SECRET="secret",
        OFFICE365_REDIRECT_URI="http://localhost:5173/api/auth/office365/callback/",
        OFFICE365_SCOPES="openid profile email",
        FRONTEND_SITE_URL="http://localhost:5173",
    )
    def test_office365_callback_logs_in_with_model_backend(self):
        session = self.client.session
        session["office365_oauth_state"] = "state"
        session.save()
        claims = {
            "preferred_username": "advocate@example.org",
            "email": "advocate@example.org",
            "given_name": "Ada",
            "family_name": "Advocate",
            "tid": "tenant-id",
        }
        payload = base64.urlsafe_b64encode(json.dumps(claims).encode("utf-8")).decode("utf-8").rstrip("=")
        id_token = f"header.{payload}.signature"

        with patch("apps.core.views.requests.post") as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = {
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "id_token": id_token,
                "scope": "openid profile email",
            }
            response = self.client.get("/api/auth/office365/callback/?code=code&state=state")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "http://localhost:5173")
        user = User.objects.get(username="advocate@example.org")
        self.assertEqual(user.email, "advocate@example.org")
