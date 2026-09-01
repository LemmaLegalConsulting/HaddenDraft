"""Loading, seeding, and matching the file-backed court filing-rule profiles.

Profiles are maintained as YAML under ``content/court-rules/`` and seeded into
the database, where an office edits them. Seeding never overwrites a profile
someone has edited here: a wrong filing rule is worse than a missing one, and
so is quietly reverting a correction.
"""

from datetime import date

import yaml

from apps.core.content_library import content_path
from apps.rules.models import CourtProfile
from apps.sources.jurisdiction import normalize


CONTENT_DIRECTORY = ("court-rules",)
REQUIRED_FIELDS = {"slug", "name", "court_type"}
COURT_TYPES = {choice for choice, _label in CourtProfile.COURT_TYPE_CHOICES}
VERIFICATIONS = {choice for choice, _label in CourtProfile.VERIFICATION_CHOICES}


def _string_list(value):
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _parse_date(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def load_court_profile_file(path):
    """Read and validate one maintained court profile."""
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"Could not read court profile {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Court profile {path} must contain a YAML mapping.")
    missing = REQUIRED_FIELDS - payload.keys()
    if missing:
        raise ValueError(f"Court profile {path} is missing: {', '.join(sorted(missing))}.")
    court_type = str(payload["court_type"]).strip()
    if court_type not in COURT_TYPES:
        raise ValueError(f"Court profile {path} has unknown court_type {court_type!r}.")
    verification = str(payload.get("verification", CourtProfile.UNVERIFIED)).strip()
    if verification not in VERIFICATIONS:
        raise ValueError(f"Court profile {path} has unknown verification {verification!r}.")
    municipality = str(payload.get("municipality", "")).strip()
    if municipality and court_type not in CourtProfile.MUNICIPAL_TYPES:
        raise ValueError(
            f"Court profile {path} sets a municipality on a {court_type} court, where it does not apply."
        )
    return {
        "slug": str(payload["slug"]).strip(),
        "name": str(payload["name"]).strip(),
        "court_type": court_type,
        "state": str(payload.get("state", "")).strip(),
        "county": str(payload.get("county", "")).strip(),
        "municipality": municipality,
        "division": str(payload.get("division", "")).strip(),
        "aliases": _string_list(payload.get("aliases")),
        "verification": verification,
        "source": str(payload.get("source", "")).strip(),
        "source_url": str(payload.get("source_url", "")).strip(),
        "verified_on": _parse_date(payload.get("verified_on")),
        "pleading_types": _string_list(payload.get("pleading_types")),
        "formatting": payload.get("formatting") or {},
        "required_elements": payload.get("required_elements") or [],
        "notes": str(payload.get("notes", "")).strip(),
        "active": bool(payload.get("active", True)),
    }


def court_profile_seeds():
    directory = content_path(*CONTENT_DIRECTORY)
    if not directory.exists():
        return []
    return [load_court_profile_file(path) for path in sorted(directory.glob("*.yaml"))]


def sync_court_profile_seeds(*, update_existing=False):
    """Create file-backed profiles without discarding an office's own edits."""
    synced = []
    for seed in court_profile_seeds():
        profile, created = CourtProfile.objects.get_or_create(slug=seed["slug"], defaults=seed)
        if not created and update_existing and not profile.is_locally_edited:
            for field, value in seed.items():
                if field != "slug":
                    setattr(profile, field, value)
            profile.save()
        synced.append((profile, created))
    return synced


# Detection


def _candidate_strings(profile):
    """Everything that would identify this court in a caption or a case record."""
    values = [profile.name, *(profile.aliases or [])]
    if profile.division:
        values.append(profile.division)
    if profile.uses_municipality and profile.municipality:
        values.append(f"{profile.municipality} {profile.get_court_type_display()}")
    return [value for value in values if value]


def detect_court(text, *, matter=None, profiles=None):
    """Pick the court a document is headed to from its own words.

    Deliberately deterministic: the caption of a filing names its court, so this
    is string matching against maintained profiles, not an inference. It reports
    the phrase it matched so a person can see why, and reports nothing rather
    than guessing when nothing matches.
    """
    profiles = list(profiles if profiles is not None else CourtProfile.objects.filter(active=True))
    # A caption sits at the top. Reading the whole document would let a case
    # cited on page nine outrank the court the paper is actually filed in.
    haystacks = [
        ("brief caption", str(text or "")[:4000]),
        ("case record", getattr(matter, "jurisdiction", "") or ""),
    ]
    best = None
    for profile in profiles:
        for candidate in _candidate_strings(profile):
            needle = normalize(candidate)
            if len(needle) < 6:
                continue
            for where, haystack in haystacks:
                if needle and needle in normalize(haystack):
                    score = len(needle) + (40 if where == "brief caption" else 0)
                    if best is None or score > best["score"]:
                        best = {
                            "score": score,
                            "profile": profile,
                            "matched": candidate,
                            "where": where,
                        }
    if not best:
        return {
            "profile": None,
            "detected": False,
            "reason": "No maintained court profile matched this document's caption or the case record.",
            "matched": "",
            "where": "",
        }
    return {
        "profile": best["profile"],
        "detected": True,
        "reason": f"Matched “{best['matched']}” in the {best['where']}.",
        "matched": best["matched"],
        "where": best["where"],
    }


PLEADING_TYPE_PATTERNS = [
    # "Reply brief of appellant" is both a reply brief and a brief of appellant.
    # The narrower name has to be tried first or it never wins.
    ("reply_brief", ["reply brief", "brief in reply"]),
    ("appellate_brief", ["merit brief", "brief of appellant", "brief of appellee", "appellant's brief", "appellee's brief"]),
    ("memorandum", ["memorandum in opposition", "memorandum in support", "memorandum contra", "brief in opposition"]),
    ("motion", ["motion to", "motion for", "notice of motion"]),
    ("answer", ["answer and counterclaim", "answer to complaint", "defendant's answer"]),
    ("complaint", ["complaint for", "verified complaint"]),
    ("brief", ["brief"]),
]


def detect_pleading_type(text, *, title=""):
    """Name the kind of paper this is, from its title page.

    Ordered most specific first: "reply brief" must not be read as "brief", and
    an appellate merit brief must not be read as a trial-court motion.
    """
    haystack = normalize(f"{title} {str(text or '')[:3000]}")
    for pleading_type, phrases in PLEADING_TYPE_PATTERNS:
        for phrase in phrases:
            if normalize(phrase) in haystack:
                return {"pleadingType": pleading_type, "matched": phrase}
    return {"pleadingType": "", "matched": ""}
