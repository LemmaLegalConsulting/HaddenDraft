"""Readable case numbers in application URLs.

A link such as `/drafting/26-0222` names a matter by the case number an
advocate reads on the screen. That number is a lookup alias, never the matter's
identity: `Matter.external_id` stays authoritative for every relation, and a
route key resolves to a matter only through `resolve_matter_route_key()`, which
applies the same access check as every other case read.

Two rules keep a readable link from opening the wrong client's file:

* An alias identifies one matter across every source system, because the URL
  carries no source. A number another matter already owns is not taken; the
  matter keeps routing by its external id and the collision is logged as the
  data-quality problem it is.
* An alias never shadows another matter's own external id. The external id is
  the identity, so when a matter claims one that an older alias spelled, the
  alias gives way.

Normalization is deliberately conservative: Unicode compatibility form,
surrounding whitespace, and case. Punctuation stays, so `26-0222` and `260222`
remain two different case numbers rather than one key that opens either.
"""

import logging
import re
import unicodedata

from django.db import IntegrityError, transaction

logger = logging.getLogger(__name__)

MAX_ROUTE_KEY_LENGTH = 120

# What a route key may look like before it is sent anywhere as a remote lookup.
# A key reaches LegalServer as a path segment, so anything that could climb out
# of that segment ("../", "/", "\") is refused outright.
_REMOTE_LOOKUP_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def normalize_route_key(value):
    text = unicodedata.normalize("NFKC", str(value or "")).strip()
    return text.casefold()


def is_remote_lookup_key(value):
    """Whether a route key is safe to hand to LegalServer as a matter id."""
    text = str(value or "")
    return (
        0 < len(text) <= MAX_ROUTE_KEY_LENGTH
        and ".." not in text
        and bool(_REMOTE_LOOKUP_KEY_RE.match(text))
    )


def _current_alias(matter):
    cache = getattr(matter, "_prefetched_objects_cache", {}) or {}
    if "route_aliases" in cache:
        return next((alias for alias in cache["route_aliases"] if alias.is_current), None)
    return matter.route_aliases.filter(is_current=True).first()


def route_key_for_matter(matter):
    """The key the frontend builds links from: the current alias, else the external id."""
    alias = _current_alias(matter)
    return alias.alias if alias else matter.external_id


# Sync runs for every matter on every case-list load, so it reads first and
# writes only when something changed: on SQLite even a DELETE or UPDATE that
# matches nothing takes the write lock, and fifty of them per page load held
# it long enough to time out an advocate's save in another tab.


def _release_aliases_shadowing(matter, alias_model):
    shadowing = list(
        alias_model.objects.filter(normalized_alias=normalize_route_key(matter.external_id)).exclude(
            matter_id=matter.pk
        )
    )
    if not shadowing:
        return
    for alias in shadowing:
        logger.warning(
            "Route alias %r for matter %s shadowed the external id of matter %s; released it.",
            alias.alias,
            alias.matter_id,
            matter.pk,
        )
    alias_model.objects.filter(pk__in=[alias.pk for alias in shadowing]).delete()


def _retire_current_aliases(matter, alias_model):
    current = alias_model.objects.filter(matter_id=matter.pk, is_current=True)
    if current.exists():
        current.update(is_current=False)


def _sync(matter, matter_model, alias_model):
    # Imported here: the serializers read route keys from this module.
    from apps.matters.serializers import payload_case_number

    _release_aliases_shadowing(matter, alias_model)

    number = payload_case_number(matter.raw_payload).strip()
    normalized = normalize_route_key(number)
    if not normalized or len(number) > MAX_ROUTE_KEY_LENGTH:
        # Nothing readable to route by (a quick case, sample data): the
        # external id is the route key, and no alias should claim otherwise.
        _retire_current_aliases(matter, alias_model)
        return None

    current = alias_model.objects.filter(matter_id=matter.pk, is_current=True).first()
    if current and current.normalized_alias == normalized and current.alias == number:
        return current

    owner = alias_model.objects.filter(normalized_alias=normalized).exclude(matter_id=matter.pk).first()
    external_owner = next(
        (
            other
            for other in matter_model.objects.filter(external_id__iexact=number).exclude(pk=matter.pk)
            if normalize_route_key(other.external_id) == normalized
        ),
        None,
    )
    if owner or external_owner:
        logger.warning(
            "Case number %r for matter %s is already used by matter %s; routing it by external id %r.",
            number,
            matter.pk,
            owner.matter_id if owner else external_owner.pk,
            matter.external_id,
        )
        _retire_current_aliases(matter, alias_model)
        return None

    try:
        with transaction.atomic():
            _retire_current_aliases(matter, alias_model)
            alias, _created = alias_model.objects.update_or_create(
                normalized_alias=normalized,
                defaults={
                    "matter_id": matter.pk,
                    "alias": number,
                    "source_system": matter.source_system,
                    "is_current": True,
                },
            )
    except IntegrityError:
        # Another request claimed the number between the check and the write.
        logger.warning("Case number %r was claimed concurrently; matter %s routes by external id.", number, matter.pk)
        return None
    return alias


def sync_matter_route_alias(matter):
    """Record the matter's current case number as its route alias.

    Earlier numbers stay as non-current aliases so old links keep resolving.
    Returns the current alias, or None when the matter routes by external id.
    """
    from apps.matters.models import Matter, MatterRouteAlias

    return _sync(matter, Matter, MatterRouteAlias)


def backfill_route_aliases(matter_model, alias_model):
    """Give every existing matter its alias; used by the data migration."""
    for matter in matter_model.objects.order_by("pk").iterator():
        _sync(matter, matter_model, alias_model)


def _matter_for_route_key(route_key):
    from apps.matters.models import Matter, MatterRouteAlias

    text = str(route_key or "").strip()
    normalized = normalize_route_key(text)
    if not normalized or len(text) > MAX_ROUTE_KEY_LENGTH:
        return None
    candidates = {}
    alias = MatterRouteAlias.objects.select_related("matter").filter(normalized_alias=normalized).first()
    if alias:
        candidates[alias.matter.pk] = alias.matter
    by_external_id = Matter.objects.filter(external_id=text).first()
    if by_external_id:
        candidates[by_external_id.pk] = by_external_id
    if len(candidates) > 1:
        # The write-side rules make this unreachable; if it happens anyway, no
        # guess is safe, because either guess may be the wrong client.
        logger.error("Route key %r matches more than one matter: %s", text, sorted(candidates))
        return None
    return next(iter(candidates.values()), None)


def resolve_matter_route_key(user, route_key):
    """The matter a route key names, if this user may open it; else None.

    An alias that exists but points at a matter the user cannot open answers
    exactly as an unknown key does, so a URL never confirms that a case exists.
    """
    from apps.matters.services import user_can_access_matter

    matter = _matter_for_route_key(route_key)
    if matter and user_can_access_matter(user, matter):
        return matter
    return None
