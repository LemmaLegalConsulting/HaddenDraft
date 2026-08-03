"""Filling an author profile from the advocate's LegalServer user record.

The letterhead needs a name, title, direct phone, fax, email, office, and (for
filing signature blocks) a bar number. LegalServer's users endpoint carries all
of them, so an advocate should not have to retype what their case system already
knows.

Verified field names against a live LegalServer instance:

    first / middle / last / suffix   ->  display_name
    title                            ->  title
    email                            ->  email
    phone_business                   ->  phone
    phone_fax                        ->  fax
    bar_number                       ->  bar_number
    office.office_name               ->  office_name
    address_work.{street,city,...}   ->  address

Values already set on the profile are left alone. An advocate who corrected a
detail by hand should not have it overwritten the next time this runs.
"""

from __future__ import annotations

import re


DELIVERABLE_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}")

PROFILE_FIELDS = (
    "display_name",
    "title",
    "email",
    "phone",
    "fax",
    "bar_number",
    "office_name",
    "address",
    "salutation",
)


def _clean(value):
    if value in (None, "", "@"):
        return ""
    return str(value).strip()


def _full_name(payload):
    parts = [_clean(payload.get(key)) for key in ("first", "middle", "last", "suffix")]
    return " ".join(part for part in parts if part)


def _work_address(payload):
    address = payload.get("address_work") or {}
    if not isinstance(address, dict):
        return ""
    street = " ".join(
        part for part in (_clean(address.get("street")), _clean(address.get("street_2"))) if part
    )
    apartment = _clean(address.get("apt_num"))
    if apartment:
        street = f"{street} {apartment}".strip()
    city = _clean(address.get("city"))
    state = _clean(address.get("state"))
    postal = _clean(address.get("zip"))
    locality = ", ".join(part for part in (city, " ".join(p for p in (state, postal) if p)) if part)
    return "\n".join(part for part in (street, locality) if part)


def _office_name(payload):
    office = payload.get("office") or {}
    if not isinstance(office, dict):
        return _clean(office)
    return _clean(office.get("office_display")) or _clean(office.get("office_name"))


def profile_values_from_legalserver_user(payload):
    """Map a LegalServer user record onto author-profile fields."""
    if not isinstance(payload, dict):
        return {}
    values = {
        "display_name": _full_name(payload),
        "title": _clean(payload.get("title")),
        "email": _clean(payload.get("email")),
        "phone": _clean(payload.get("phone_business")) or _clean(payload.get("preferred_phone")),
        "fax": _clean(payload.get("phone_fax")),
        "bar_number": _clean(payload.get("bar_number")),
        "office_name": _office_name(payload),
        "address": _work_address(payload),
        "salutation": _clean(payload.get("salutation")),
    }
    # LegalServer stores placeholder addresses such as "@" and "none@none" on
    # demo and inactive records. Requiring a dotted domain keeps those off a
    # letterhead, where a bad address is what a recipient would reply to.
    if not DELIVERABLE_EMAIL_RE.fullmatch(values["email"]):
        values["email"] = ""
    return {key: value for key, value in values.items() if value}


def apply_legalserver_user_to_profile(profile, payload, *, overwrite=False):
    """Fill blank profile fields from LegalServer; return the fields changed."""
    values = profile_values_from_legalserver_user(payload)
    changed = []
    for field, value in values.items():
        if field not in PROFILE_FIELDS:
            continue
        if not overwrite and _clean(getattr(profile, field, "")):
            continue
        if _clean(getattr(profile, field, "")) == value:
            continue
        setattr(profile, field, value)
        changed.append(field)
    return changed
