from urllib.parse import urljoin

import requests
from django.conf import settings

from apps.sources.connectors.base import SourceConnector, SourceResult
from apps.sources.models import SourceConfiguration, UserSourceIdentity


class LegalServerError(RuntimeError):
    pass


def _clean_base_url(base_url):
    return base_url.rstrip("/") + "/" if base_url else ""


def _first_value(payload, *keys, default=""):
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return default


def _display_value(value):
    if value in (None, ""):
        return ""
    if isinstance(value, dict):
        for key in (
            "lookup_value_name",
            "name",
            "label",
            "case_title",
            "user_name",
            "organization_name",
            "value",
        ):
            if value.get(key) not in (None, ""):
                return str(value[key])
        return ""
    if isinstance(value, list):
        return ""
    return str(value)


class LegalServerClient:
    search_fields = ("case_number", "case_title", "external_id", "first", "last")

    def __init__(self, *, base_url=None, api_token=None, session=None):
        config = SourceConfiguration.effective_settings(
            "legalserver",
            {
                "base_url": settings.LEGALSERVER_BASE_URL,
                "api_token": settings.LEGALSERVER_API_TOKEN,
                "matters_path": settings.LEGALSERVER_MATTERS_PATH,
                "matter_documents_path": settings.LEGALSERVER_MATTER_DOCUMENTS_PATH,
                "user_filter_param": settings.LEGALSERVER_USER_FILTER_PARAM,
            },
        )
        self.base_url = _clean_base_url(base_url or config["base_url"])
        self.api_token = api_token or config["api_token"]
        self.matters_path = config["matters_path"]
        self.matter_documents_path = config["matter_documents_path"]
        self.user_filter_param = config["user_filter_param"]
        self.session = session or requests.Session()

    @property
    def configured(self):
        return bool(self.base_url and self.api_token)

    def _url(self, path):
        return urljoin(self.base_url, path.lstrip("/"))

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
        }

    def _get(self, path, *, params=None):
        if not self.configured:
            raise LegalServerError("LegalServer is not configured")
        response = self.session.get(self._url(path), headers=self._headers(), params=params or {}, timeout=20)
        if response.status_code >= 400:
            raise LegalServerError(f"LegalServer request failed with status {response.status_code}")
        return response.json()

    def download_document(self, url):
        if not self.configured:
            raise LegalServerError("LegalServer is not configured")
        response = self.session.get(url, headers=self._headers(), timeout=30)
        if response.status_code >= 400:
            raise LegalServerError(f"LegalServer document download failed with status {response.status_code}")
        return {
            "content": response.content,
            "content_type": response.headers.get("content-type", ""),
            "filename": url.rsplit("/", 1)[-1].split("?", 1)[0],
        }

    def _search_params(self, *, user_email="", limit=25):
        params = {"page_size": limit}
        if user_email:
            params[self.user_filter_param] = user_email
        return params

    def search_matters(self, *, query="", user_email="", limit=25):
        params = self._search_params(user_email=user_email, limit=limit)
        if query:
            matters_by_id = {}
            for field in self.search_fields:
                payload = self._get(self.matters_path, params={**params, field: query})
                for matter in self._matter_list_from_payload(payload):
                    matter_key = _first_value(
                        matter,
                        "id",
                        "matter_id",
                        "matter_uuid",
                        "case_id",
                        "case_number",
                        "external_id",
                        "uuid",
                        default=str(len(matters_by_id)),
                    )
                    matters_by_id[str(matter_key)] = matter
            return list(matters_by_id.values())
        payload = self._get(self.matters_path, params=params)
        return self._matter_list_from_payload(payload)

    def _matter_list_from_payload(self, payload):
        if isinstance(payload, list):
            return payload
        return payload.get("results") or payload.get("data") or payload.get("matters") or []

    def get_matter(self, matter_id):
        path = f"{self.matters_path.rstrip('/')}/{matter_id}"
        return self._get(path)

    def get_matter_documents(self, matter_id):
        path = self.matter_documents_path.format(matter_id=matter_id)
        payload = self._get(path)
        if isinstance(payload, list):
            return payload
        return payload.get("results") or payload.get("data") or payload.get("documents") or []


def user_email_for_filter(user):
    if user and getattr(user, "is_authenticated", False):
        return getattr(user, "email", "") or getattr(user, "username", "")
    return ""


def user_identifier_for_filter(user):
    return UserSourceIdentity.identifier_for(user, "legalserver")


def matter_payload_to_defaults(payload):
    client = _display_value(_first_value(payload, "client_name", "client_full_name", "client", "full_name", "name", default="Unknown client"))
    matter_type = _display_value(
        _first_value(
            payload,
            "matter_type",
            "case_type",
            "legal_problem_code",
            "problem_code",
            default="Housing",
        )
    )
    jurisdiction = _display_value(_first_value(payload, "jurisdiction", "court", "county_of_dispute", "county", default=""))
    summary = _display_value(
        _first_value(
            payload,
            "summary",
            "case_summary",
            "case_title",
            "pro_bono_opportunity_summary",
            "description",
            default="",
        )
    )
    return {
        "client_name": client,
        "matter_type": matter_type,
        "jurisdiction": jurisdiction,
        "posture": _display_value(_first_value(payload, "posture", "case_status", "status", "case_disposition", default="")),
        "risk": _display_value(_first_value(payload, "risk", "priority", "emergency", default="")),
        "summary": summary,
        "source_system": "LegalServer",
        "raw_payload": payload,
    }


class LegalServerConnector(SourceConnector):
    kind = "legalserver"
    label = "LegalServer"
    detail = "Matters, case notes, parties, deadlines, and case documents"

    def __init__(self, client=None):
        self.client = client or LegalServerClient()

    @property
    def status(self):
        return "Connected" if self.client.configured else "Configure LEGALSERVER_BASE_URL and LEGALSERVER_API_TOKEN"

    def search(self, query, *, matter=None, jurisdiction="", limit=5, user=None, request=None):
        if not self.client.configured:
            return []
        try:
            documents = self.client.get_matter_documents(matter.external_id) if matter else []
            matters = [] if matter else self.client.search_matters(
                query=query,
                user_email=user_identifier_for_filter(user),
                limit=limit,
            )
        except LegalServerError:
            return []

        results = []
        for doc in documents[:limit]:
            doc_id = _first_value(doc, "id", "document_id", "uuid", default="")
            title = _first_value(doc, "title", "name", "filename", default="LegalServer document")
            storage = _first_value(doc, "storage", "storage_provider", "source", default="LegalServer")
            url = _first_value(doc, "download_url", "url", "web_url", "sharepoint_url", default="")
            results.append(
                SourceResult(
                    id=f"lsdoc:{matter.external_id}:{doc_id or title}",
                    title=title,
                    snippet=_first_value(doc, "summary", "description", "snippet", default=f"Case document stored in {storage}."),
                    source_kind=self.kind,
                    source_label="LegalServer case document",
                    citation=title,
                    url=url,
                    metadata={"matter": matter.external_id, "storage": storage, "raw": doc},
                )
            )

        for payload in matters[:limit]:
            matter_id = str(_first_value(payload, "id", "matter_id", "matter_uuid", "case_id", "case_number", "external_id", "uuid", default=""))
            defaults = matter_payload_to_defaults(payload)
            results.append(
                SourceResult(
                    id=f"ls:{matter_id}",
                    title=f"{defaults['client_name']} - {defaults['matter_type']}",
                    snippet=defaults["summary"] or "LegalServer matter match.",
                    source_kind=self.kind,
                    source_label="LegalServer matter",
                    citation=f"LegalServer matter {matter_id}",
                    metadata={"matter": matter_id, "jurisdiction": defaults["jurisdiction"], "raw": payload},
                )
            )
        return results
