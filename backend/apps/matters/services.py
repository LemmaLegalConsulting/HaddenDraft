from dataclasses import dataclass, field

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


@dataclass
class LegalServerAccessProfile:
    identifier: str = ""
    login_email: str = ""
    roles: list[str] = field(default_factory=list)
    user_payload: dict = field(default_factory=dict)
    is_superuser: bool = False
    email_matches_login: bool = False
    identity_required: bool = True
    error: str = ""

    @property
    def access_level(self):
        if self.is_superuser:
            return "superuser"
        if not self.identifier:
            return "unconnected"
        if self.error:
            return self.error
        return "regular"


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


def login_email_for_user(user):
    return (getattr(user, "email", "") or getattr(user, "username", "") or "").casefold().strip()


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


def _user_group_names(user):
    if not user or not getattr(user, "is_authenticated", False):
        return set()
    try:
        return {name.casefold() for name in user.groups.values_list("name", flat=True)}
    except Exception:
        return set()


def django_user_has_legalserver_superuser_role(user):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    configured_groups = {group.casefold() for group in getattr(settings, "LEGALSERVER_SUPERUSER_GROUPS", [])}
    return bool(configured_groups & _user_group_names(user))


def _flatten_values(value):
    if isinstance(value, dict):
        for nested in value.values():
            yield from _flatten_values(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _flatten_values(nested)
    elif value not in (None, ""):
        yield str(value)


def legalserver_user_roles(payload):
    role_fields = (
        "role",
        "roles",
        "role_name",
        "user_role",
        "user_roles",
        "groups",
        "permissions",
        "permission_groups",
        "profile",
        "access_level",
    )
    roles = []
    if not isinstance(payload, dict):
        return roles
    for field_name in role_fields:
        for role in _flatten_values(payload.get(field_name)):
            roles.append(role)
    return sorted({role for role in roles if role})


def legalserver_user_email(payload):
    if not isinstance(payload, dict):
        return ""
    for key in ("email", "user_email", "email_address", "work_email", "primary_email", "username", "user_name"):
        value = payload.get(key)
        if value:
            return str(value).casefold().strip()
    return ""


def legalserver_roles_include_superuser(roles):
    configured_roles = {role.casefold() for role in getattr(settings, "LEGALSERVER_SUPERUSER_ROLES", [])}
    normalized_roles = {role.casefold() for role in roles}
    return bool(configured_roles & normalized_roles)


def legalserver_access_profile_for_user(user, *, client=None):
    identifier = legalserver_identifier_for_user(user)
    login_email = login_email_for_user(user)
    profile = LegalServerAccessProfile(
        identifier=identifier,
        login_email=login_email,
        is_superuser=django_user_has_legalserver_superuser_role(user),
        identity_required=getattr(settings, "LEGALSERVER_REQUIRE_OFFICE365_EMAIL_MATCH", True),
    )
    if not identifier:
        return profile

    identifier_matches_login = identifier.casefold().strip() == login_email if login_email else False
    profile.email_matches_login = identifier_matches_login

    try:
        client = client or LegalServerClient()
        if getattr(client, "configured", False) and hasattr(client, "find_user"):
            profile.user_payload = client.find_user(identifier)
    except (LegalServerError, AttributeError):
        profile.user_payload = {}
    if profile.user_payload:
        profile.roles = legalserver_user_roles(profile.user_payload)
        profile.is_superuser = profile.is_superuser or legalserver_roles_include_superuser(profile.roles)
        legalserver_email = legalserver_user_email(profile.user_payload)
        if legalserver_email and login_email:
            profile.email_matches_login = legalserver_email == login_email

    if profile.is_superuser:
        profile.email_matches_login = True
    elif profile.identity_required and not profile.email_matches_login:
        profile.error = "identity_mismatch"
    return profile


def user_can_access_matter(user, matter, *, access_profile=None):
    if not user or not getattr(user, "is_authenticated", False) or not matter:
        return False
    access_profile = access_profile or legalserver_access_profile_for_user(user)
    if access_profile.is_superuser:
        return True
    if settings.ENABLE_DEMO_MATTERS:
        return True
    if settings.DEBUG and not matter.raw_payload:
        return True
    if not access_profile.identifier or access_profile.error:
        return False
    return payload_matches_legalserver_identifier(matter.raw_payload or {}, access_profile.identifier)


def accessible_matters_for_user(user):
    access_profile = legalserver_access_profile_for_user(user)
    if access_profile.is_superuser:
        return list(Matter.objects.all())
    return [matter for matter in Matter.objects.all() if user_can_access_matter(user, matter, access_profile=access_profile)]


def matter_for_user(user, external_id):
    matter = Matter.objects.filter(external_id=external_id).first()
    if matter and user_can_access_matter(user, matter):
        return matter
    return None


def legalserver_account_status(user, *, client=None):
    client = client or LegalServerClient()
    identifier = legalserver_identifier_for_user(user)
    access_profile = legalserver_access_profile_for_user(user, client=client)
    return {
        "configured": client.configured,
        "connected": bool(identifier),
        "identifier": identifier,
        "suggestedIdentifier": suggested_legalserver_identifier(user),
        "userFilterParam": client.user_filter_param,
        "accessLevel": access_profile.access_level,
        "roles": access_profile.roles,
        "emailMatchesLogin": access_profile.email_matches_login,
        "requiresOffice365EmailMatch": access_profile.identity_required,
        "autoMapOffice365Email": getattr(settings, "LEGALSERVER_AUTO_MAP_OFFICE365_EMAIL", True),
    }


def sync_legalserver_matters_for_user(user, *, query="", limit=50, restrict_to_user=True, client=None):
    client = client or LegalServerClient()
    if not client.configured:
        return LegalServerSyncResult(matters=[], connected=False, configured=False, error="not_configured")
    access_profile = legalserver_access_profile_for_user(user, client=client)
    if not access_profile.identifier:
        return LegalServerSyncResult(matters=[], connected=False, configured=True, error="not_connected")
    if access_profile.error:
        return LegalServerSyncResult(
            matters=[],
            connected=True,
            configured=True,
            identifier=access_profile.identifier,
            error=access_profile.error,
        )
    try:
        payloads = client.search_matters(
            query=query,
            user_email="" if access_profile.is_superuser or not restrict_to_user else access_profile.identifier,
            limit=limit,
        )
        if not access_profile.is_superuser and restrict_to_user:
            payloads = [payload for payload in payloads if payload_matches_legalserver_identifier(payload, access_profile.identifier)]
        if query and not payloads:
            payload = client.get_matter(query)
            if access_profile.is_superuser:
                payloads = [payload] if payload else []
            else:
                payloads = [payload] if payload and payload_matches_legalserver_identifier(payload, access_profile.identifier) else []
    except LegalServerError as exc:
        return LegalServerSyncResult(
            matters=[],
            connected=True,
            configured=True,
            identifier=access_profile.identifier,
            error=str(exc) or "request_failed",
        )
    matters = [matter for matter in (upsert_matter_from_legalserver(payload) for payload in payloads) if matter]
    return LegalServerSyncResult(matters=matters, connected=True, configured=True, identifier=access_profile.identifier)


def sync_legalserver_matter(matter_id, *, user=None, client=None):
    client = client or LegalServerClient()
    if not client.configured:
        return None
    access_profile = legalserver_access_profile_for_user(user, client=client) if user is not None else None
    if access_profile and access_profile.error:
        return None
    try:
        payload = client.get_matter(matter_id)
    except LegalServerError:
        return None
    if access_profile and not access_profile.is_superuser:
        if not payload_matches_legalserver_identifier(payload, access_profile.identifier):
            return None
    return upsert_matter_from_legalserver(payload)
