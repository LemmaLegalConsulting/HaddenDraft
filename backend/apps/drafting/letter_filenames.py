"""Naming a downloaded letter so it is findable a month later.

`advice-letter.docx` in a downloads folder tells an advocate nothing, and every
letter they send collides with the last one. The default here sorts
chronologically, groups by client, and says what the letter covers:

    2026-08-02-garcia-robert-advice-letter-security-deposit-nonpayment-of-rent.docx

The pattern is a template so an organization can change it without a deploy --
some file by case number, some by client. Placeholders that resolve to nothing
drop out along with their separator, so a letter drafted before the client's
name is known still gets a usable name rather than a run of hyphens.
"""

from __future__ import annotations

import re
from datetime import date

from django.utils.text import slugify


DEFAULT_PATTERN = "{date}-{client}-advice-letter-{sections}"

# Enough to identify the letter; more turns the name into a paragraph.
DEFAULT_SECTION_LIMIT = 3
MAX_LENGTH = 120

# An honorific is not part of the name and sorts the file under the wrong letter.
HONORIFICS = {"mr", "mrs", "ms", "mx", "dr", "miss", "prof", "rev", "sir", "madam"}

# Words that add nothing once the name already says "advice letter".
SECTION_NOISE = {
    "cle", "neo", "rtc", "draft", "cleveland", "the", "a", "an", "of", "and",
    "for", "to", "in", "your", "with",
}


def client_slug(name: str) -> str:
    """"Robert Garcia" -> "garcia-robert", so a client's letters sort together."""
    cleaned = re.sub(r"\s+", " ", str(name or "")).strip()
    if not cleaned:
        return ""
    if "," in cleaned:
        # Already "Garcia, Robert".
        return slugify(cleaned.replace(",", " "))
    parts = [
        part
        for part in cleaned.split(" ")
        if part.strip(".").casefold() not in HONORIFICS
    ] or cleaned.split(" ")
    if len(parts) == 1:
        return slugify(parts[0])
    surname, given = parts[-1], " ".join(parts[:-1])
    return slugify(f"{surname} {given}")


def section_slug(title: str) -> str:
    """Trim a section title down to what distinguishes it."""
    words = [
        word
        for word in slugify(str(title or "")).split("-")
        if word and word not in SECTION_NOISE
    ]
    return "-".join(words)


def sections_slug(titles, *, limit=DEFAULT_SECTION_LIMIT) -> str:
    seen = []
    for title in titles:
        slug = section_slug(title)
        if slug and slug not in seen:
            seen.append(slug)
        if len(seen) >= limit:
            break
    return "-".join(seen)


def _tidy(value: str) -> str:
    value = re.sub(r"-{2,}", "-", value).strip("-")
    if len(value) <= MAX_LENGTH:
        return value
    # Cut on a word boundary so the name stays readable.
    return value[:MAX_LENGTH].rsplit("-", 1)[0].strip("-")


def letter_filename(
    *,
    pattern: str = "",
    client_name: str = "",
    section_titles=None,
    letter_date: date | None = None,
    case_number: str = "",
    kind: str = "advice-letter",
    section_limit: int = DEFAULT_SECTION_LIMIT,
    extension: str = "docx",
) -> str:
    """Build the download name for one letter."""
    values = {
        "date": (letter_date or date.today()).isoformat(),
        "client": client_slug(client_name),
        "sections": sections_slug(section_titles or [], limit=section_limit),
        "case": slugify(case_number),
        "kind": slugify(kind),
    }
    rendered = (pattern or DEFAULT_PATTERN).format_map(_Missing(values))
    name = _tidy(slugify(rendered, allow_unicode=False))
    return f"{name or 'advice-letter'}.{extension}"


class _Missing(dict):
    """An unknown placeholder becomes empty rather than raising.

    The pattern is organization-editable, so a typo should cost a hyphen in one
    filename, not a failed download.
    """

    def __missing__(self, key):
        return ""
