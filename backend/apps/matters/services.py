from dataclasses import dataclass

from django.conf import settings

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


def _normalized_identifier_candidates(identifier):
    normalized = (identifier or "").casefold().strip()
    if not normalized:
        return set()
    candidates = {normalized}
    if "@" in normalized:
        candidates.add(normalized.split("@", 1)[0])
    return candidates


def _identity_value_matches(value, candidates):
    if value in (None, ""):
        return False
    return any(candidate in str(value).casefold() for candidate in candidates)


def _assignment_identity_values(payload):
    top_level_keys = (
        "assigned_user_email",
        "assigned_user",
        "assigned_to",
        "advocate_email",
        "advocate",
        "attorney_email",
        "staff_email",
        "user_email",
        "email",
        "username",
        "user_name",
        "user_id",
        "user_uuid",
    )
    for key in top_level_keys:
        value = payload.get(key)
        if isinstance(value, dict):
            yield from _assignment_identity_values(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    yield from _assignment_identity_values(item)
                else:
                    yield item
        else:
            yield value

    assignment_lists = (
        "assignments",
        "assigned_users",
        "users",
        "advocates",
        "staff_assignments",
        "case_assignments",
    )
    nested_keys = (
        "name",
        "email",
        "assigned_by",
        "notes",
        "user_name",
        "user_id",
        "user_uuid",
        "assigned_user_email",
    )
    for list_key in assignment_lists:
        for assignment in payload.get(list_key) or []:
            if not isinstance(assignment, dict):
                continue
            for key in nested_keys:
                yield assignment.get(key)
            user = assignment.get("user")
            if isinstance(user, dict):
                for key in nested_keys:
                    yield user.get(key)


def payload_matches_legalserver_identifier(payload, identifier):
    candidates = _normalized_identifier_candidates(identifier)
    if not candidates or not isinstance(payload, dict):
        return False
    return any(_identity_value_matches(value, candidates) for value in _assignment_identity_values(payload))


def user_can_access_matter(user, matter):
    if not user or not getattr(user, "is_authenticated", False) or not matter:
        return False
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    if settings.ENABLE_DEMO_MATTERS:
        return True
    identifier = legalserver_identifier_for_user(user)
    if not identifier:
        return False
    return payload_matches_legalserver_identifier(matter.raw_payload or {}, identifier)


def accessible_matters_for_user(user):
    return [matter for matter in Matter.objects.all() if user_can_access_matter(user, matter)]


def matter_for_user(user, external_id):
    matter = Matter.objects.filter(external_id=external_id).first()
    if matter and user_can_access_matter(user, matter):
        return matter
    return None


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
            payloads = [payload] if payload and payload_matches_legalserver_identifier(payload, identifier) else []
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


def sync_legalserver_matter(matter_id, *, user=None, client=None):
    client = client or LegalServerClient()
    if not client.configured:
        return None
    try:
        payload = client.get_matter(matter_id)
    except LegalServerError:
        return None
    if user is not None:
        identifier = legalserver_identifier_for_user(user)
        if not payload_matches_legalserver_identifier(payload, identifier):
            return None
    return upsert_matter_from_legalserver(payload)
