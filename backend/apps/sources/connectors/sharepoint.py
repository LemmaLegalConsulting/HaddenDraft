import hashlib
import time
from urllib.parse import quote, urlsplit

from django.utils import timezone

import requests
from django.conf import settings

from apps.sources.connectors.base import SourceConnector, SourceResult
from apps.sources.models import SourceConfiguration, UserOAuthConnection


GRAPH_ROOT = "https://graph.microsoft.com/v1.0"


class SharePointError(RuntimeError):
    def __init__(self, message, *, status_code=None, code="graph_error", retry_after=None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.retry_after = retry_after


ERRORS = {
    401: ("authentication_required", "SharePoint authentication expired or is invalid. Sign in again."),
    403: ("access_denied", "Your SharePoint connection does not have permission to read this document or library."),
    404: ("not_found", "The SharePoint document or library was not found."),
    429: ("throttled", "SharePoint is busy. Retry after the indicated delay."),
}


def item_metadata(item, *, site_id="", drive_id=""):
    """Allowlisted provenance: never persist Graph's preauthenticated download URL."""
    parent = item.get("parentReference") or {}
    return {
        "itemId": item.get("id", ""),
        "siteId": parent.get("siteId") or site_id,
        "driveId": parent.get("driveId") or drive_id,
        "webUrl": item.get("webUrl", ""),
        "path": parent.get("path", ""),
        "name": item.get("name", ""),
        "modifiedAt": item.get("lastModifiedDateTime", ""),
        "etag": item.get("eTag", ""),
        "mimeType": (item.get("file") or {}).get("mimeType", ""),
        "size": item.get("size"),
    }


class SharePointClient:
    def __init__(self, *, access_token=None, site_id=None, drive_id=None, session=None, sleep=time.sleep):
        config = SourceConfiguration.effective_settings(
            "sharepoint",
            {
                "access_token": settings.SHAREPOINT_ACCESS_TOKEN,
                "site_id": settings.SHAREPOINT_SITE_ID,
                "drive_id": settings.SHAREPOINT_DRIVE_ID,
                "case_folder_template": settings.SHAREPOINT_CASE_FOLDER_TEMPLATE,
            },
        )
        self.access_token = config["access_token"] if access_token is None else access_token
        self.site_id = site_id or config["site_id"]
        self.drive_id = drive_id or config["drive_id"]
        self.case_folder_template = config["case_folder_template"]
        self.session = session or requests.Session()
        self.sleep = sleep

    @property
    def configured(self):
        return bool(self.access_token and self.site_id and self.drive_id)

    def _headers(self):
        return {"Authorization": f"Bearer {self.access_token}", "Accept": "application/json"}

    def _request(self, path, *, params=None, **kwargs):
        if not self.configured:
            raise SharePointError("SharePoint is not configured", code="not_configured")
        # One short retry fits a web request. Longer Retry-After delays are
        # surfaced to the caller instead of sleeping through a worker timeout.
        for attempt in range(2):
            try:
                response = self.session.get(
                    f"{GRAPH_ROOT}{path}", headers=self._headers(), params=params or {},
                    timeout=10, allow_redirects=False, **kwargs,
                )
            except requests.RequestException as exc:
                raise SharePointError("Microsoft Graph could not be reached.", code="unavailable") from exc
            if response.status_code < 400:
                return response
            retry_after = None
            if response.status_code == 429:
                try:
                    retry_after = max(1, int(response.headers.get("Retry-After", "1")))
                except (TypeError, ValueError):
                    retry_after = 1
                if attempt == 0 and retry_after <= 2:
                    self.sleep(retry_after)
                    continue
            code, message = ERRORS.get(response.status_code, ("graph_error", "Microsoft Graph request failed."))
            raise SharePointError(message, status_code=response.status_code, code=code, retry_after=retry_after)

    def _get(self, path, *, params=None):
        response = self._request(path, params=params)
        try:
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("Expected an object")
            if response.status_code != 200:
                raise ValueError("Unexpected status")
            return payload
        except ValueError as exc:
            raise SharePointError("Microsoft Graph returned an invalid response.", code="invalid_response") from exc

    @property
    def drive_path(self):
        return f"/sites/{quote(self.site_id, safe='')}/drives/{quote(self.drive_id, safe='')}"

    def item_path(self, item_id):
        if not isinstance(item_id, str) or not item_id or item_id in {".", ".."}:
            raise SharePointError("A SharePoint item identifier is required.", code="invalid_item")
        return f"{self.drive_path}/items/{quote(item_id, safe='')}"

    def get_item(self, item_id):
        return self._get(self.item_path(item_id))

    def get_document(self, item_id, *, max_bytes=25 * 1024 * 1024):
        """Download a file and reject a version changed during retrieval.

        Download capabilities are short lived and never leave this method.
        The download session carries neither the Graph token nor netrc auth.
        """
        item = self.get_item(item_id)
        if "file" not in item or "remoteItem" in item:
            raise SharePointError("Choose a file in the configured SharePoint drive.", code="unsupported_item")
        if item.get("size", 0) > max_bytes:
            raise SharePointError("The SharePoint document exceeds the download limit.", code="too_large")
        response = self._request(self.item_path(item_id) + "/content", stream=True)
        try:
            if response.status_code == 302:
                location = response.headers.get("Location", "")
                try:
                    parsed = urlsplit(location)
                    port = parsed.port
                except ValueError as exc:
                    raise SharePointError("Graph returned an invalid download URL.", code="invalid_response") from exc
                host = (parsed.hostname or "").lower()
                if (parsed.scheme != "https" or parsed.username or parsed.password or port not in (None, 443)
                        or not any(host.endswith("." + domain) for domain in ("sharepoint.com", "1drv.com"))):
                    raise SharePointError("Graph returned an unsupported download host.", code="invalid_response")
                response.close()
                with requests.Session() as download:
                    download.trust_env = False
                    with download.get(location, timeout=20, stream=True, allow_redirects=False) as content_response:
                        content = self._read_content(content_response, max_bytes)
            else:
                content = self._read_content(response, max_bytes)
        except requests.RequestException as exc:
            raise SharePointError("The SharePoint download failed. Retry retrieval.", code="download_failed") from exc
        finally:
            response.close()
        if item.get("size") is not None and len(content) != item["size"]:
            raise SharePointError("The SharePoint download was incomplete. Retry retrieval.", code="download_failed")
        current = self.get_item(item_id)
        if not item.get("eTag") or current.get("eTag") != item["eTag"]:
            raise SharePointError("The SharePoint version could not be confirmed. Retry retrieval.", code="version_changed")
        return {
            "content": content,
            "metadata": {
                **item_metadata(item, site_id=self.site_id, drive_id=self.drive_id),
                "sha256": hashlib.sha256(content).hexdigest(),
                "fetchedAt": timezone.now().isoformat(),
            },
        }

    @staticmethod
    def _read_content(response, max_bytes):
        if response.status_code != 200:
            code, message = ERRORS.get(response.status_code, ("download_failed", "The SharePoint download failed."))
            raise SharePointError(message, status_code=response.status_code, code=code)
        chunks, size = [], 0
        started = time.monotonic()
        for chunk in response.iter_content(chunk_size=65536):
            size += len(chunk)
            if size > max_bytes:
                raise SharePointError("The SharePoint document exceeds the download limit.", code="too_large")
            if time.monotonic() - started > 60:
                raise SharePointError("The SharePoint download took too long.", code="download_failed")
            chunks.append(chunk)
        return b"".join(chunks)

    def search_drive(self, query, *, limit=10):
        # OData string literals double apostrophes before URL encoding.
        query = quote((query or "*").replace("'", "''"), safe="")
        path = f"{self.drive_path}/root/search(q='{query}')"
        payload = self._get(path, params={"$top": limit})
        return payload.get("value", [])[:limit]

    def list_case_documents(self, matter_id, *, limit=25):
        folder = self.case_folder_template.format(matter_id=matter_id)
        encoded_folder = quote(folder.strip("/"), safe="/")
        path = f"{self.drive_path}/root:/{encoded_folder}:/children"
        payload = self._get(path, params={"$top": limit})
        return payload.get("value", [])[:limit]


def graph_token_for_request(request):
    if request is not None:
        token = request.session.get("ms_graph_access_token")
        if token:
            return token
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            connection = UserOAuthConnection.objects.filter(user=user, provider="office365", enabled=True).first()
            if connection:
                if connection.expires_at and connection.expires_at <= timezone.now():
                    raise SharePointError(ERRORS[401][1], status_code=401, code="authentication_required")
                # An existing delegated connection must never fall back to a
                # more privileged service token, including when its token is empty.
                return connection.access_token
    return None


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
        items = (
                client.list_case_documents(matter.external_id, limit=limit)
                if matter
                else client.search_drive(query or jurisdiction or "*", limit=limit)
            )
        results = []
        for item in items[:limit]:
            if "folder" in item:
                continue
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
                        **item_metadata(item, site_id=getattr(client, "site_id", ""), drive_id=getattr(client, "drive_id", "")),
                    },
                )
            )
        return results
