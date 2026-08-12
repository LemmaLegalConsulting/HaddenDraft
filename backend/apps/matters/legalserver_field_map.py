"""File-backed rules translating a triage outcome into LegalServer case fields.

Which case properties a triage outcome should change is a per-office policy
decision, and the fields it names may not exist on a given site yet. The rules
therefore live in `content/legalserver-field-maps/*.yaml` alongside the triage
rubrics rather than in Python, and a map that names no fields evaluates to no
updates instead of failing.
"""

from dataclasses import dataclass, field
from pathlib import Path
from string import Formatter

import yaml
from django.conf import settings

from apps.core.content_library import content_path


FIELD_MAP_DIRECTORY = "legalserver-field-maps"

PLACEHOLDERS = (
    "case_type",
    "confidence",
    "priority",
    "priority_label",
    "summary",
    "reasoning",
    "rubric_name",
    "rubric_slug",
    "matched_criteria",
    "missing_information",
    "assessed_on",
    "assessed_by",
)

CONDITION_KEYS = (
    "priority",
    "priority_label",
    "confidence",
    "case_type",
    "rubric",
    "matched_criteria_contains",
    "missing_information",
)


@dataclass
class FieldMapResult:
    """What a triage assessment implies for a matter's LegalServer fields."""

    slug: str = ""
    enabled: bool = False
    dry_run: bool = True
    fields: dict = field(default_factory=dict)
    custom_fields: dict = field(default_factory=dict)
    matched_rules: list = field(default_factory=list)
    error: str = ""

    @property
    def has_updates(self):
        return bool(self.fields or self.custom_fields)

    def as_payload(self):
        """Return the body to send to LegalServer, or {} when nothing applies."""
        payload = dict(self.fields)
        if self.custom_fields:
            payload["custom_fields"] = dict(self.custom_fields)
        return payload


def field_map_path(slug):
    return content_path(FIELD_MAP_DIRECTORY, f"{slug}.yaml")


def load_field_map(slug):
    """Load and validate a field map. Returns None when the file is absent."""
    if not slug:
        return None
    path = Path(field_map_path(slug))
    if not path.exists():
        return None
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"Could not read LegalServer field map {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"LegalServer field map {path} must contain a YAML mapping.")
    rules = payload.get("rules") or []
    if not isinstance(rules, list):
        raise ValueError(f"LegalServer field map {path} must provide rules as a list.")
    return {
        "slug": str(payload.get("slug") or slug),
        "name": str(payload.get("name", "")),
        "description": str(payload.get("description", "")),
        "enabled": bool(payload.get("enabled", False)),
        "dry_run": bool(payload.get("dry_run", True)),
        "rules": [_validated_rule(rule, path, index) for index, rule in enumerate(rules, start=1)],
    }


def _validated_rule(rule, path, index):
    if not isinstance(rule, dict):
        raise ValueError(f"Rule {index} in {path} must be a mapping.")
    name = str(rule.get("name") or f"rule-{index}")
    when = rule.get("when") or {}
    if not isinstance(when, dict):
        raise ValueError(f"Rule '{name}' in {path} must express `when` as a mapping.")
    unknown = set(when) - set(CONDITION_KEYS)
    if unknown:
        raise ValueError(
            f"Rule '{name}' in {path} tests unknown conditions: {', '.join(sorted(unknown))}. "
            f"Supported: {', '.join(CONDITION_KEYS)}."
        )
    return {
        "name": name,
        "when": when,
        "set": _validated_values(rule.get("set") or {}, name, path, "set"),
        "custom_fields": _validated_values(rule.get("custom_fields") or {}, name, path, "custom_fields"),
    }


def _validated_values(values, rule_name, path, label):
    if not isinstance(values, dict):
        raise ValueError(f"Rule '{rule_name}' in {path} must express `{label}` as a mapping.")
    for key, value in values.items():
        if isinstance(value, str):
            for _, placeholder, _, _ in Formatter().parse(value):
                if placeholder and placeholder not in PLACEHOLDERS:
                    raise ValueError(
                        f"Rule '{rule_name}' in {path} uses unknown placeholder "
                        f"'{{{placeholder}}}' for field '{key}'. "
                        f"Supported: {', '.join(PLACEHOLDERS)}."
                    )
    return dict(values)


def assessment_context(assessment):
    """Flatten an assessment into the values a rule may substitute."""
    rubric = getattr(assessment, "rubric", None)
    created_by = getattr(assessment, "created_by", None)
    created_at = getattr(assessment, "created_at", None)
    matched = assessment.matched_criteria or []
    missing = assessment.missing_information or []
    return {
        "case_type": assessment.case_type or "",
        "confidence": assessment.confidence or "",
        "priority": "Yes" if assessment.priority else "No",
        "priority_label": assessment.priority_label or "",
        "summary": assessment.summary or "",
        "reasoning": assessment.reasoning or "",
        "rubric_name": getattr(rubric, "name", "") or "",
        "rubric_slug": getattr(rubric, "slug", "") or "",
        "matched_criteria": "; ".join(str(item) for item in matched),
        "missing_information": "; ".join(str(item) for item in missing),
        "assessed_on": created_at.date().isoformat() if created_at else "",
        "assessed_by": getattr(created_by, "get_full_name", lambda: "")() or getattr(created_by, "username", "") or "",
    }


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


def _matches(condition, assessment, context):
    for key, expected in condition.items():
        if key == "priority":
            if bool(assessment.priority) is not bool(expected):
                return False
        elif key == "missing_information":
            wanted = str(expected).casefold().strip()
            present = bool(assessment.missing_information)
            if wanted == "any" and not present:
                return False
            if wanted == "none" and present:
                return False
        elif key in ("priority_label", "confidence"):
            actual = str(context[key]).casefold().strip()
            if actual not in {item.casefold().strip() for item in _as_list(expected)}:
                return False
        elif key == "rubric":
            actual = str(context["rubric_slug"]).casefold().strip()
            if actual not in {item.casefold().strip() for item in _as_list(expected)}:
                return False
        else:
            # case_type and matched_criteria_contains match loosely: a site's
            # problem code and a rubric's criterion wording both vary in ways an
            # exact comparison would miss.
            haystack = str(context["case_type" if key == "case_type" else "matched_criteria"]).casefold()
            if not any(item.casefold().strip() in haystack for item in _as_list(expected)):
                return False
    return True


def triage_outcome_updates(assessment, *, slug=None, field_map=None):
    """Evaluate the configured map against an assessment."""
    slug = slug if slug is not None else getattr(settings, "LEGALSERVER_TRIAGE_FIELD_MAP", "")
    try:
        field_map = field_map if field_map is not None else load_field_map(slug)
    except ValueError as exc:
        return FieldMapResult(slug=slug or "", error=str(exc))
    if not field_map:
        return FieldMapResult(slug=slug or "", error="" if not slug else "no_field_map")

    context = assessment_context(assessment)
    result = FieldMapResult(
        slug=field_map["slug"],
        enabled=field_map["enabled"],
        dry_run=field_map["dry_run"],
    )
    for rule in field_map["rules"]:
        if not _matches(rule["when"], assessment, context):
            continue
        result.matched_rules.append(rule["name"])
        result.fields.update(_rendered(rule["set"], context))
        result.custom_fields.update(_rendered(rule["custom_fields"], context))
    return result


def _rendered(values, context):
    return {
        key: (value.format(**context) if isinstance(value, str) else value)
        for key, value in values.items()
    }
