"""Deterministic filing-format checks against a court's maintained rule profile.

Nothing here is a model call. A page limit, a type size, and whether the paper
carries a certificate of service are facts about the document, and an advocate
asking "will the clerk take this" deserves an answer that is checked rather than
generated.

Two rules govern how results are reported:

* An unverified profile can only warn. Its requirements were not read off the
  court's own local rules, so reporting them as errors would put a starter
  profile's guess on the same footing as the rule itself.
* A property that could not be measured is reported as unmeasured, never as a
  pass. A DOCX has no page count until something renders it, and a scanned PDF
  has no type size to read; silently skipping either would tell an advocate
  their fifty-page brief fits in fifteen.

Rule codes: E/W/I900-999 (court filing-format compliance).
"""

import re

from apps.validation.findings import make_finding, sort_and_condense_findings


CATEGORY = "court_formatting"

SPACING_LABELS = {"double": "double-spaced", "one_and_a_half": "1.5-spaced", "single": "single-spaced", "any": "any spacing"}
SPACING_ORDER = {"single": 1.0, "one_and_a_half": 1.5, "double": 2.0}
# A handful of runs at a smaller size is a superscript or a page number, not the
# body of the brief. Only a size carrying real text is worth a finding.
SIGNIFICANT_RUN_SHARE = 0.05


def _severity_for(profile, declared):
    """An unverified profile warns; it never errors."""
    declared = declared if declared in {"error", "warning", "info"} else "warning"
    if profile.verification != profile.VERIFIED and declared == "error":
        return "warning"
    return declared


SEVERITY_PREFIX = {"error": "E", "warning": "W", "info": "I"}


def _code(severity, number):
    return f"{SEVERITY_PREFIX[severity]}{number}"


def _finding(document_id, severity, number, *, target, message, details=None, action=None):
    return make_finding(
        draft_id=document_id,
        rule_code=_code(severity, number),
        severity=severity,
        category=CATEGORY,
        target=target,
        message=message,
        details=details or {},
        action=action or {"type": "human_review", "label": "Check this against the court's local rules.", "payload": {}},
        manual_review=severity != "info",
    )


def _applies(entry_types, pleading_type):
    """An empty pleading-type list means the requirement applies to everything."""
    types = [str(item) for item in entry_types or []]
    return not types or pleading_type in types


def _profile_note(profile):
    if profile.verification == profile.VERIFIED:
        return profile.source or "this court's recorded local rules"
    return "an unverified starter profile, not this court's own rules"


def check_required_elements(profile, text, pleading_type, document_id):
    findings = []
    haystack = str(text or "")
    for element in profile.required_elements or []:
        if not isinstance(element, dict) or not _applies(element.get("pleading_types"), pleading_type):
            continue
        patterns = [str(pattern) for pattern in element.get("patterns") or []]
        found = False
        for pattern in patterns:
            try:
                if re.search(pattern, haystack, flags=re.IGNORECASE | re.MULTILINE):
                    found = True
                    break
            except re.error:
                # A malformed pattern is a content-library defect, not a finding
                # about the document. Treat the element as unchecked.
                continue
        if found:
            continue
        severity = _severity_for(profile, element.get("severity", "error"))
        label = element.get("label") or element.get("id") or "required element"
        findings.append(
            _finding(
                document_id,
                severity,
                900,
                target=str(element.get("id") or label),
                message=(
                    f"{label} was not found in this document. "
                    f"{profile.name} requires it for a {pleading_type or 'filing'} per {_profile_note(profile)}."
                ),
                details={"elementId": element.get("id", ""), "patterns": patterns, "profile": profile.slug},
            )
        )
    return findings


def check_typography(profile, formatting, document_id):
    findings = []
    fonts = formatting.get("fonts") or []
    rules = (profile.formatting or {}).get("fonts") or {}
    total_runs = sum(int(font.get("runs") or 0) for font in fonts) or 0

    minimum = rules.get("min_size_pt")
    if minimum:
        if not fonts:
            findings.append(
                _finding(
                    document_id,
                    "info",
                    950,
                    target="type size",
                    message=(
                        "Type size could not be read from this file, so the "
                        f"{minimum}-point minimum was not checked."
                    ),
                    details={"property": "fontSize"},
                )
            )
        else:
            undersized = [
                font
                for font in fonts
                if font.get("sizePt")
                and float(font["sizePt"]) < float(minimum)
                and total_runs
                and int(font.get("runs") or 0) / total_runs >= SIGNIFICANT_RUN_SHARE
            ]
            for font in undersized:
                severity = _severity_for(profile, "error")
                findings.append(
                    _finding(
                        document_id,
                        severity,
                        911,
                        target="type size",
                        message=(
                            f"Text is set in {font['sizePt']:g} point. {profile.name} requires at least "
                            f"{minimum} point per {_profile_note(profile)}."
                        ),
                        details={"sizePt": font["sizePt"], "family": font.get("family", ""), "minimumPt": minimum},
                    )
                )

    allowed = [str(family).casefold() for family in rules.get("allowed_families") or []]
    if allowed and fonts:
        for font in fonts:
            family = str(font.get("family") or "").casefold()
            share = int(font.get("runs") or 0) / total_runs if total_runs else 0
            if family and share >= SIGNIFICANT_RUN_SHARE and not any(option in family for option in allowed):
                findings.append(
                    _finding(
                        document_id,
                        _severity_for(profile, "warning"),
                        910,
                        target="typeface",
                        message=(
                            f"{font.get('family')} is not among the typefaces {profile.name} accepts "
                            f"({', '.join(rules.get('allowed_families'))})."
                        ),
                        details={"family": font.get("family", ""), "allowed": rules.get("allowed_families")},
                    )
                )
    return findings


def check_spacing(profile, formatting, document_id):
    required = ((profile.formatting or {}).get("spacing") or {}).get("body")
    if not required or required == "any":
        return []
    measured = formatting.get("lineSpacing")
    if not measured:
        return [
            _finding(
                document_id,
                "info",
                951,
                target="line spacing",
                message=(
                    "Line spacing could not be read from this file, so the "
                    f"{SPACING_LABELS.get(required, required)} requirement was not checked."
                ),
                details={"property": "lineSpacing"},
            )
        ]
    if SPACING_ORDER.get(measured, 0) + 0.001 < SPACING_ORDER.get(required, 0):
        return [
            _finding(
                document_id,
                _severity_for(profile, "error"),
                920,
                target="line spacing",
                message=(
                    f"The body is {SPACING_LABELS.get(measured, measured)}. {profile.name} requires "
                    f"{SPACING_LABELS.get(required, required)} per {_profile_note(profile)}."
                ),
                details={"measured": measured, "required": required},
            )
        ]
    return []


def check_margins(profile, formatting, document_id):
    required = (profile.formatting or {}).get("margins_in") or {}
    if not required:
        return []
    measured = formatting.get("marginsIn") or {}
    if not measured:
        return [
            _finding(
                document_id,
                "info",
                952,
                target="margins",
                message="Margins could not be read from this file, so the margin requirement was not checked.",
                details={"property": "margins", "required": required},
            )
        ]
    findings = []
    for edge, minimum in required.items():
        value = measured.get(edge)
        if value is None:
            continue
        if float(value) + 0.01 < float(minimum):
            findings.append(
                _finding(
                    document_id,
                    _severity_for(profile, "error"),
                    930,
                    target=f"{edge} margin",
                    message=(
                        f"The {edge} margin is {float(value):.2f} inches. {profile.name} requires "
                        f"{float(minimum):.2f} inches per {_profile_note(profile)}."
                    ),
                    details={"edge": edge, "measuredIn": value, "requiredIn": minimum},
                )
            )
    return findings


def page_limit_for(profile, pleading_type):
    for entry in (profile.formatting or {}).get("page_limits") or []:
        if isinstance(entry, dict) and _applies(entry.get("pleading_types"), pleading_type):
            try:
                return int(entry["max_pages"])
            except (KeyError, TypeError, ValueError):
                continue
    return None


def check_page_limit(profile, formatting, pleading_type, document_id):
    limit = page_limit_for(profile, pleading_type)
    if not limit:
        return []
    pages = formatting.get("countedPageCount")
    if not pages:
        return [
            _finding(
                document_id,
                "info",
                953,
                target="page limit",
                message=(
                    f"{profile.name} limits a {pleading_type or 'filing'} to {limit} pages, but this file has no "
                    "fixed page count to check. Count the pages in the rendered PDF before filing."
                ),
                details={"property": "pageCount", "maxPages": limit},
            )
        ]
    if pages > limit:
        return [
            _finding(
                document_id,
                _severity_for(profile, "error"),
                940,
                target="page limit",
                message=(
                    f"The brief runs {pages} pages. {profile.name} allows {limit} for a "
                    f"{pleading_type or 'filing'} per {_profile_note(profile)}."
                ),
                details={"pages": pages, "maxPages": limit},
            )
        ]
    return []


def check_court_compliance(*, profile, formatting, text, pleading_type="", document_id=0):
    """Every deterministic filing-format check this profile can make."""
    if profile is None:
        return {
            "checked": False,
            "reason": "No court profile is selected, so filing-format rules were not applied.",
            "findings": [],
        }
    formatting = formatting or {}
    known_types = [str(item) for item in profile.pleading_types or []]
    findings = [
        *check_required_elements(profile, text, pleading_type, document_id),
        *check_typography(profile, formatting, document_id),
        *check_spacing(profile, formatting, document_id),
        *check_margins(profile, formatting, document_id),
        *check_page_limit(profile, formatting, pleading_type, document_id),
    ]
    if known_types and pleading_type and pleading_type not in known_types:
        findings.append(
            _finding(
                document_id,
                "info",
                960,
                target="pleading type",
                message=(
                    f"{profile.name} has no rules on file for a {pleading_type}. "
                    "Requirements specific to that kind of filing were not checked."
                ),
                details={"pleadingType": pleading_type, "knownTypes": known_types},
            )
        )
    return {
        "checked": True,
        "profile": {
            "slug": profile.slug,
            "name": profile.name,
            "courtType": profile.court_type,
            "verification": profile.verification,
            "source": profile.source,
            "sourceUrl": profile.source_url,
        },
        "pleadingType": pleading_type,
        "unmeasured": formatting.get("unavailable", []),
        "findings": sort_and_condense_findings(findings),
    }
