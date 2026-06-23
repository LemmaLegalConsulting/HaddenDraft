from urllib.parse import quote

import requests
from django.conf import settings

from apps.sources.connectors.base import SourceConnector, SourceResult
from apps.sources.models import SourceConfiguration, UserOAuthConnection


GRAPH_ROOT = "https://graph.microsoft.com/v1.0"


class SharePointError(RuntimeError):
    pass


class SharePointClient:
    def __init__(self, *, access_token=None, site_id=None, drive_id=None, session=None):
        config = SourceConfiguration.effective_settings(
            "sharepoint",
            {
                "access_token": settings.SHAREPOINT_ACCESS_TOKEN,
                "site_id": settings.SHAREPOINT_SITE_ID,
                "drive_id": settings.SHAREPOINT_DRIVE_ID,
                "case_folder_template": settings.SHAREPOINT_CASE_FOLDER_TEMPLATE,
            },
        )
        self.access_token = access_token or config["access_token"]
        self.site_id = site_id or config["site_id"]
        self.drive_id = drive_id or config["drive_id"]
        self.case_folder_template = config["case_folder_template"]
        self.session = session or requests.Session()

    @property
    def configured(self):
        return bool(self.access_token and self.site_id and self.drive_id)

    def _headers(self):
        return {"Authorization": f"Bearer {self.access_token}", "Accept": "application/json"}

    def _get(self, path, *, params=None):
        if not self.configured:
            raise SharePointError("SharePoint is not configured")
        response = self.session.get(f"{GRAPH_ROOT}{path}", headers=self._headers(), params=params or {}, timeout=20)
        if response.status_code >= 400:
            raise SharePointError(f"Microsoft Graph request failed with status {response.status_code}")
        return response.json()

    def search_drive(self, query, *, limit=10):
        path = f"/sites/{self.site_id}/drives/{self.drive_id}/root/search(q='{quote(query or '*')}')"
        payload = self._get(path, params={"$top": limit})
        return payload.get("value", [])

    def list_case_documents(self, matter_id, *, limit=25):
        folder = self.case_folder_template.format(matter_id=matter_id)
        encoded_folder = quote(folder.strip("/"))
        path = f"/sites/{self.site_id}/drives/{self.drive_id}/root:/{encoded_folder}:/children"
        payload = self._get(path, params={"$top": limit})
        return payload.get("value", [])


def graph_token_for_request(request):
    if request is not None:
        token = request.session.get("ms_graph_access_token")
        if token:
            return token
        token = UserOAuthConnection.access_token_for(getattr(request, "user", None), "office365")
        if token:
            return token
    return ""


class SharePointConnector(SourceConnector):
    kind = "sharepoint"
    label = "SharePoint"
    detail = "SharePoint Online case documents and practice libraries through Microsoft Graph"

    def __init__(self, client=None):
        self.client = client

    def _client_for_request(self, request):
        if self.client:
            return self.client
        return SharePointClient(access_token=graph_token_for_request(request))

    @property
    def status(self):
        client = self.client or SharePointClient()
        return "Connected" if client.configured else "Configure SharePoint Graph settings or sign in with Office 365"

    def search(self, query, *, matter=None, jurisdiction="", limit=5, user=None, request=None):
        client = self._client_for_request(request)
        if not client.configured:
            return []
        try:
            items = (
                client.list_case_documents(matter.external_id, limit=limit)
                if matter
                else client.search_drive(query or jurisdiction or "*", limit=limit)
            )
        except SharePointError:
            return []
        results = []
        for item in items[:limit]:
            name = item.get("name") or "SharePoint document"
            web_url = item.get("webUrl", "")
            item_id = item.get("id") or name
            results.append(
                SourceResult(
                    id=f"sp:{item_id}",
                    title=name,
                    snippet=item.get("description") or item.get("summary") or "SharePoint Online document.",
                    source_kind=self.kind,
                    source_label="SharePoint Online",
                    citation=name,
                    url=web_url,
                    metadata={
                        "matter": getattr(matter, "external_id", ""),
                        "mimeType": item.get("file", {}).get("mimeType", ""),
                        "raw": item,
                    },
                )
            )
        return results
