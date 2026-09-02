"""Deterministic form-of-pleading checks.

The things a reader can verify by looking rather than by reasoning: whether the
paragraphs are numbered and run in order, whether the paper asks the court for
anything, whether it is signed, whether every exhibit it refers to is actually
attached, whether a placeholder is still sitting in the text.

These are conventions of practice. A specific court's own requirements live in
``content/court-rules/`` and are checked by ``court_formatting``, so the two
never disagree about whose rule is being applied -- a finding here never cites a
court, and a finding there always does.

Rule codes: E/W/I1000-1099.
"""

import functools
import re

import yaml

from apps.core.content_library import content_path
from apps.validation.findings import make_finding, sort_and_condense_findings


RULES_PATH = ("drafting-rules", "checks", "pleading-form.yaml")
CATEGORY = "pleading_form"
SEVERITY_PREFIX = {"error": "E", "warning": "W", "info": "I"}

CHECK_CODES = {
    "numbered_paragraphs": 1000,
    "paragraph_sequence": 1010,
    "required_text": 1020,
    "exhibit_references": 1030,
    "placeholder": 1040,
}

_NUMBERED_PARAGRAPH = re.compile(r"^\s*(\d{1,3})[.)]\s+\S", re.MULTILINE)
_EXHIBIT_REFERENCE = re.compile(r"\b(exhibit|attachment|appendix)\s+([A-Z0-9]{1,4})\b", re.IGNORECASE)
_DOUBLE_SPACE_SENTENCE = re.compile(r"[.!?]\s")


def load_rules():
    path = content_path(*RULES_PATH)
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


@functools.lru_cache(maxsize=1)
def _cached_rules():
    return load_rules()


def _finding(document_id, spec, message, *, target, details=None):
    severity = spec.get("severity", "warning")
    severity = severity if severity in SEVERITY_PREFIX else "warning"
    number = CHECK_CODES.get(spec.get("kind"), 1090)
    return make_finding(
        draft_id=document_id,
        rule_code=f"{SEVERITY_PREFIX[severity]}{number}",
        severity=severity,
        category=CATEGORY,
        target=target,
        message=re.sub(r"\s+", " ", message).strip(),
        details={"checkId": spec.get("id", ""), **(details or {})},
        action={"type": "human_review", "label": spec.get("label", "Check the form of this filing."), "payload": {}},
        manual_review=severity != "info",
    )


def _applies(spec, pleading_type):
    types = [str(item) for item in spec.get("pleading_types") or []]
    return not types or pleading_type in types


def _check_numbered_paragraphs(spec, text, pleading_type, document_id):
    found = len(_NUMBERED_PARAGRAPH.findall(text))
    minimum = int(spec.get("min_paragraphs", 3))
    if found >= minimum:
        return []
    message = str(spec.get("message", "")).format(
        pleading_type=pleading_type or "pleading", found=found, minimum=minimum
    )
    return [_finding(document_id, spec, message, target="numbered paragraphs", details={"found": found})]


def _check_paragraph_sequence(spec, text, _pleading_type, document_id):
    numbers = [int(match) for match in _NUMBERED_PARAGRAPH.findall(text)]
    findings = []
    previous = None
    for current in numbers:
        # Restarting at 1 is a new count -- a second cause of action, an
        # affirmative-defense section -- not a gap in the first one.
        if previous is not None and current != previous + 1 and current != 1:
            findings.append(
                _finding(
                    document_id,
                    spec,
                    str(spec.get("message", "")).format(previous=previous, current=current),
                    target=f"paragraph {current}",
                    details={"previous": previous, "current": current},
                )
            )
        previous = current
    return findings


def _check_required_text(spec, text, _pleading_type, document_id):
    for pattern in spec.get("patterns") or []:
        try:
            if re.search(str(pattern), text, flags=re.IGNORECASE | re.MULTILINE):
                return []
        except re.error:
            continue
    return [_finding(document_id, spec, str(spec.get("message", "")), target=spec.get("id", "required text"))]


def _check_exhibit_references(spec, text, _pleading_type, document_id, *, attached_labels=()):
    referenced = {}
    for kind, label in _EXHIBIT_REFERENCE.findall(text):
        referenced.setdefault(f"{kind.title()} {label.upper()}", 0)
        referenced[f"{kind.title()} {label.upper()}"] += 1
    attached = {str(label).strip().casefold() for label in attached_labels}
    if not attached:
        # Nothing was attached to compare against. Reporting every reference as
        # missing would be noise, and reporting none would be a false pass.
        return []
    missing = [name for name in referenced if name.casefold() not in attached]
    if not missing:
        return []
    return [
        _finding(
            document_id,
            spec,
            str(spec.get("message", "")).format(missing=", ".join(sorted(missing))),
            target="exhibit references",
            details={"missing": sorted(missing), "attached": sorted(attached)},
        )
    ]


def _check_placeholder(spec, text, _pleading_type, document_id):
    findings = []
    seen = set()
    for pattern in spec.get("patterns") or []:
        try:
            matches = re.findall(str(pattern), text)
        except re.error:
            continue
        for match in matches[:10]:
            excerpt = str(match)[:80]
            if excerpt.casefold() in seen:
                continue
            seen.add(excerpt.casefold())
            findings.append(
                _finding(
                    document_id,
                    spec,
                    str(spec.get("message", "")).format(excerpt=excerpt),
                    target="placeholder",
                    details={"excerpt": excerpt},
                )
            )
    return findings


CHECKERS = {
    "numbered_paragraphs": _check_numbered_paragraphs,
    "paragraph_sequence": _check_paragraph_sequence,
    "required_text": _check_required_text,
    "placeholder": _check_placeholder,
}


def check_pleading_form(text, *, pleading_type="", document_id=0, attached_labels=(), rules=None):
    """Run every form check that applies to this kind of paper."""
    rules = rules if rules is not None else _cached_rules()
    text = str(text or "")
    findings = []
    for spec in rules.get("checks") or []:
        if not isinstance(spec, dict) or not _applies(spec, pleading_type):
            continue
        kind = spec.get("kind")
        if kind == "exhibit_references":
            findings.extend(
                _check_exhibit_references(spec, text, pleading_type, document_id, attached_labels=attached_labels)
            )
        elif kind in CHECKERS:
            findings.extend(CHECKERS[kind](spec, text, pleading_type, document_id))
    return sort_and_condense_findings(findings)
