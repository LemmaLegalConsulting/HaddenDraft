"""One controlled vocabulary for the counties this corpus talks about.

Metadata reaches this application from scanned documents rather than from a
list, so the same county arrives as "Cuyahoga" on one decision and "Cuyahoga
County" on the next. Left alone that splits a shelf in two, and the half a
reader was not shown is invisible rather than merely unselected: narrowing to
one spelling reported 126 decisions where there were 264.

The fix is applied twice on purpose.

Ingestion writes the canonical name, so material imported from now on is
consistent in the database, which is the only place a fix is durable --
everything that reads the field afterwards, including the admin, an export, or
a query nobody has written yet, gets the same answer without knowing this
module exists.

Reading canonicalizes again, because a corpus imported before this existed is
still on disk and still has to group correctly, and because the next sidecar a
model writes will spell something a way nobody predicted.

A value this vocabulary does not recognize is returned exactly as it arrived.
That restraint is the point: this corpus holds "Miami-Dade County" and "Durham
County, North Carolina", and an out-of-state county quietly rewritten to the
nearest Ohio one would file a Florida decision on an Ohio shelf. Matching is
therefore exact against the vocabulary after mechanical tidying, never
nearest-neighbour, and what did not match is reportable rather than silent.
"""

from __future__ import annotations

import re
from functools import lru_cache

import yaml

from apps.core.content_library import content_path


COUNTIES_PATH = ("jurisdictions", "ohio-counties.yaml")

# Endings that are part of how a county is written rather than part of its
# name. Ordered longest first so "cty." is not left behind by stripping "co.".
_SUFFIXES = ("county", "cty", "co")
_STATE_SUFFIXES = ("ohio",)

_PUNCTUATION = re.compile(r"[^0-9a-z]+")


def _squash(value):
    return _PUNCTUATION.sub(" ", str(value or "").casefold()).strip()


def normalize_county_key(value):
    """The comparison key for a county, with the ways of writing one removed.

    Case, punctuation and spacing go first, then a trailing state name, then a
    leading "county of" or a trailing "county"/"cty"/"co". Nothing else is
    touched: "miami dade" stays two words and so never collides with "miami".
    """
    text = _squash(value)
    if not text:
        return ""
    for state in _STATE_SUFFIXES:
        if text.endswith(f" {state}"):
            text = text[: -len(state) - 1].strip()
    if text.startswith("county of "):
        text = text[len("county of ") :].strip()
    for suffix in _SUFFIXES:
        if text.endswith(f" {suffix}"):
            text = text[: -len(suffix) - 1].strip()
            break
    return text


def _fingerprint(path):
    try:
        status = path.stat()
    except OSError:
        return None
    return (status.st_mtime_ns, status.st_size)


_CACHE = {}


def _vocabulary():
    path = content_path(*COUNTIES_PATH)
    fingerprint = _fingerprint(path)
    # "value" in _CACHE, not just a matching fingerprint: a missing file has
    # fingerprint None, which also matches an empty cache, and the first call in
    # a process without the vocabulary raised KeyError instead of reading none.
    if "value" in _CACHE and _CACHE.get("fingerprint") == fingerprint:
        return _CACHE["value"]
    payload = {}
    if fingerprint is not None:
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            payload = {}
    by_key = {}
    order = []
    for entry in payload.get("counties") or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        record = {
            "name": name,
            "appellateDistrict": str(entry.get("appellate_district") or "").strip(),
            "state": str(payload.get("state") or "").strip(),
        }
        order.append(record)
        for spelling in [name, *(entry.get("aliases") or [])]:
            key = normalize_county_key(spelling)
            if key:
                by_key.setdefault(key, record)
    built = {"byKey": by_key, "counties": order, "available": bool(order)}
    _CACHE.update(fingerprint=fingerprint, value=built)
    # The lookups below are hot -- every record in a 15,000-passage index asks
    # for its county -- and the vocabulary only changes when the file does.
    county_profile.cache_clear()
    return built


@lru_cache(maxsize=4096)
def county_profile(value):
    """The vocabulary entry for a county, or ``None`` if it is not one of ours."""
    key = normalize_county_key(value)
    return _vocabulary()["byKey"].get(key) if key else None


def canonical_county(value):
    """The county's name as the vocabulary spells it, or the value unchanged.

    Unchanged is the honest answer for a county this vocabulary does not hold:
    it may be out of state, or it may be a gap in the file, and neither is a
    reason to rewrite it into the nearest Ohio county.
    """
    _vocabulary()
    profile = county_profile(value)
    return profile["name"] if profile else str(value or "").strip()


def appellate_district(county):
    """The Ohio appellate district that reviews a county, or ``""`` if unknown."""
    _vocabulary()
    profile = county_profile(county)
    return profile["appellateDistrict"] if profile else ""


def is_known_county(value):
    _vocabulary()
    return county_profile(value) is not None


def county_names():
    return [record["name"] for record in _vocabulary()["counties"]]


def vocabulary_status():
    vocabulary = _vocabulary()
    return {
        "available": vocabulary["available"],
        "countyCount": len(vocabulary["counties"]),
        "spellingCount": len(vocabulary["byKey"]),
        "path": str(content_path(*COUNTIES_PATH)),
    }
