from dataclasses import dataclass

from apps.matters.models import Matter
from apps.sources.connectors.legalserver import LegalServerClient, LegalServerError, matter_payload_to_defaults
from apps.sources.models import UserSourceIdentity


@dataclass
class LegalServerSyncResult:
    matters: list
    connected: bool
    configured: bool
    identifier: str = ""
    error: str = ""


def legalserver_id(payload):
    for key in ("id", "matter_id", "matter_uuid", "case_id", "case_number", "external_id", "uuid"):
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def upsert_matter_from_legalserver(payload):
    external_id = legalserver_id(payload)
    if not external_id:
        return None
    defaults = matter_payload_to_defaults(payload)
    matter, _created = Matter.objects.update_or_create(external_id=external_id, defaults=defaults)
    return matter


def suggested_legalserver_identifier(user):
    if user and getattr(user, "is_authenticated", False):
        return getattr(user, "email", "") or getattr(user, "username", "")
    return ""


def legalserver_identifier_for_user(user):
    return UserSourceIdentity.identifier_for(user, "legalserver")


def payload_matches_legalserver_identifier(payload, identifier):
    if not identifier:
        return False
    normalized = identifier.casefold()
    candidates = {normalized}
    if "@" in normalized:
        candidates.add(normalized.split("@", 1)[0])
    for assignment in payload.get("assignments") or []:
        if not isinstance(assignment, dict):
            continue
        values = [
            assignment.get("name"),
            assignment.get("assigned_by"),
            assignment.get("notes"),
        ]
        user = assignment.get("user")
        if isinstance(user, dict):
            values.extend([user.get("user_name"), user.get("user_id"), user.get("user_uuid")])
        for value in values:
            if value and any(candidate in str(value).casefold() for candidate in candidates):
                return True
    return False


def legalserver_account_status(user, *, client=None):
    client = client or LegalServerClient()
    identifier = legalserver_identifier_for_user(user)
    return {
        "configured": client.configured,
        "connected": bool(identifier),
        "identifier": identifier,
        "suggestedIdentifier": suggested_legalserver_identifier(user),
        "userFilterParam": client.user_filter_param,
    }


def sync_legalserver_matters_for_user(user, *, query="", limit=50, restrict_to_user=True, client=None):
    client = client or LegalServerClient()
    if not client.configured:
        return LegalServerSyncResult(matters=[], connected=False, configured=False, error="not_configured")
    identifier = legalserver_identifier_for_user(user)
    if not identifier:
        return LegalServerSyncResult(matters=[], connected=False, configured=True, error="not_connected")
    try:
        payloads = client.search_matters(
            query=query,
            user_email=identifier if restrict_to_user else "",
            limit=limit,
        )
        if restrict_to_user:
            payloads = [payload for payload in payloads if payload_matches_legalserver_identifier(payload, identifier)]
        if query and not payloads:
            payload = client.get_matter(query)
            payloads = [payload] if payload else []
    except LegalServerError as exc:
        return LegalServerSyncResult(
            matters=[],
            connected=True,
            configured=True,
            identifier=identifier,
            error=str(exc) or "request_failed",
        )
    matters = [matter for matter in (upsert_matter_from_legalserver(payload) for payload in payloads) if matter]
    return LegalServerSyncResult(matters=matters, connected=True, configured=True, identifier=identifier)


def sync_legalserver_matter(matter_id, *, client=None):
    client = client or LegalServerClient()
    if not client.configured:
        return None
    try:
        payload = client.get_matter(matter_id)
    except LegalServerError:
        return None
    return upsert_matter_from_legalserver(payload)
