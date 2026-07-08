"""Structured validation finding builders.

Findings are plain dicts (not model instances) so they serialize directly into
``DraftDocument.validation_flags`` and the drafting API response without a
migration. See rule code ranges in ``apps/validation/services.py``.
"""

import hashlib

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"
VALID_SEVERITIES = {SEVERITY_ERROR, SEVERITY_WARNING, SEVERITY_INFO}

SEVERITY_ORDER = {SEVERITY_ERROR: 0, SEVERITY_WARNING: 1, SEVERITY_INFO: 2}

_SEVERITY_PREFIX = {
    SEVERITY_ERROR: "E",
    SEVERITY_WARNING: "W",
    SEVERITY_INFO: "I",
}

DEFAULT_ACTION = {
    "type": "human_review",
    "label": "Review this finding.",
    "payload": {},
}

DEFAULT_LOCATION = {
    "view": "json",
    "blockKey": None,
    "sectionLabel": None,
    "lineStart": None,
    "lineEnd": None,
    "excerpt": "",
}


def _stable_finding_id(draft_id, rule_code, target, message):
    digest = hashlib.sha1(f"{draft_id}|{rule_code}|{target}|{message}".encode("utf-8")).hexdigest()[:16]
    return f"{rule_code}-{digest}"


def make_finding(
    *,
    draft_id,
    rule_code,
    severity,
    category,
    target,
    message,
    outcome=None,
    location=None,
    action=None,
    manual_review=False,
    details=None,
):
    if severity not in VALID_SEVERITIES:
        raise ValueError(f"Invalid severity: {severity!r}. Must be one of {sorted(VALID_SEVERITIES)}.")
    expected_prefix = _SEVERITY_PREFIX[severity]
    if not rule_code.startswith(expected_prefix):
        raise ValueError(f"Rule code {rule_code!r} does not match severity {severity!r} (expected prefix {expected_prefix!r}).")
    if outcome is None:
        outcome = "pass" if severity == SEVERITY_INFO else ("review" if severity == SEVERITY_WARNING else "fail")
    return {
        "findingId": _stable_finding_id(draft_id, rule_code, target, message),
        "ruleCode": rule_code,
        "severity": severity,
        "outcome": outcome,
        "category": category,
        "target": target,
        "location": {**DEFAULT_LOCATION, **(location or {})},
        "message": message,
        "action": {**DEFAULT_ACTION, **(action or {})},
        "manualReview": manual_review,
        "details": details or {},
    }


def error_finding(**kwargs):
    return make_finding(severity=SEVERITY_ERROR, **kwargs)


def warning_finding(**kwargs):
    return make_finding(severity=SEVERITY_WARNING, **kwargs)


def info_finding(**kwargs):
    return make_finding(severity=SEVERITY_INFO, **kwargs)


def sort_and_condense_findings(findings):
    """De-duplicate by findingId (stable across repeated runs) and sort by severity."""
    deduped = {}
    for finding in findings:
        deduped[finding["findingId"]] = finding
    return sorted(
        deduped.values(),
        key=lambda finding: (SEVERITY_ORDER.get(finding["severity"], 3), finding["ruleCode"], finding["target"]),
    )
