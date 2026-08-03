"""Addressing and subject details for a letter, taken from the case.

A letter to a client needs the client's name, their address, and a line saying
what it is about. All three are already in LegalServer, so asking an advocate to
retype them invites a letter addressed to "[Client]" -- which is exactly what
shipped before this existed.

Nothing here invents a value. A field the case does not carry comes back empty
so the caller can leave it blank or prompt for it, rather than printing a
plausible-looking guess on something going out in the post.
"""

from __future__ import annotations

import re

from apps.sources.connectors.legalserver import _display_value, _first_value


# LegalServer stores the client's address twice; mail goes to the mailing
# address when there is one.
ADDRESS_KEYS = ("client_address_mailing", "client_address_home")

# "01 Bankruptcy/Debtor Relief" -- the leading code is internal.
PROBLEM_CODE_RE = re.compile(r"^\s*\d+\s+")


def _clean(value):
    if value in (None, "", "null"):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def format_address(address) -> str:
    """Render a LegalServer address block as postal lines."""
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
    locality = " ".join(part for part in (state, postal) if part)
    locality = ", ".join(part for part in (city, locality) if part)
    return "\n".join(part for part in (street, locality) if part)


def client_address(payload) -> str:
    for key in ADDRESS_KEYS:
        formatted = format_address(payload.get(key))
        if formatted:
            return formatted
    return ""


def matter_subject(matter, payload) -> str:
    """A short phrase naming what the letter is about.

    It lands mid-sentence -- "help with your ___" -- where the maintained
    wrapper said "[eviction/housing issue]".

    LegalServer's problem code is a filing category, not English. Passing it
    through produced "help with your private landlord/tenant", so codes are
    mapped to a handful of readable categories instead. Each one is a complete
    noun phrase, because the sentence has no other noun to lean on.
    """
    problem = PROBLEM_CODE_RE.sub("", _clean(_display_value(payload.get("legal_problem_code"))))
    haystack = " ".join(
        [problem, _clean(getattr(matter, "matter_type", "")), _clean(getattr(matter, "summary", ""))]
    ).casefold()

    if any(term in haystack for term in ("evict", "detainer", "forcible entry", "f.e.d")):
        return "eviction"
    if any(
        term in haystack
        for term in (
            "landlord", "tenant", "housing", "lease", "rent", "subsid", "voucher",
            "foreclos", "habitab", "utilit", "mobile home",
        )
    ):
        return "housing matter"
    return "legal matter"


def case_reference(matter, payload) -> str:
    """The "Re:" line: what the case is, and its number."""
    parts = []
    title = _clean(_display_value(payload.get("case_title")))
    if title:
        parts.append(title)
    number = _clean(
        _first_value(payload, "case_number", "matter_identification_number", default="")
    ) or _clean(getattr(matter, "external_id", ""))
    court = _clean(getattr(matter, "jurisdiction", ""))
    if number:
        parts.append(f"Case No. {number}")
    if court:
        parts.append(court)
    return ", ".join(parts)


def client_letter_context(matter) -> dict:
    """Everything a letter needs about who it is going to."""
    payload = getattr(matter, "raw_payload", None) or {}
    name = _clean(
        _display_value(
            _first_value(
                payload, "client_full_name", "client_name", "full_name", default=""
            )
        )
    ) or _clean(getattr(matter, "client_name", ""))
    return {
        "recipientName": name,
        "recipientAddress": client_address(payload),
        "recipientEmail": _clean(
            _first_value(payload, "client_email_address", "email", default="")
        ),
        "caseNumber": _clean(
            _first_value(payload, "case_number", "matter_identification_number", default="")
        )
        or _clean(getattr(matter, "external_id", "")),
        "caseReference": case_reference(matter, payload),
        "matterSubject": matter_subject(matter, payload),
        "court": _clean(getattr(matter, "jurisdiction", "")),
    }


def salutation_name(name: str) -> str:
    """The client's name as the case records it, with whitespace tidied.

    Capitalization is left exactly as entered, including all caps. A name is not
    ours to restyle: "DeCarlo", "McDONALD", "van der Berg", and "O'Brien" all
    lose something to title-casing, and a person who records their name in caps
    has recorded it that way. Where the case data looks wrong, the fix belongs in
    the case, not in a transformation applied on the way out.
    """
    return _clean(name)
