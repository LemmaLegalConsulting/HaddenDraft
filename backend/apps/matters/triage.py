import json
import re
from pathlib import Path

import yaml
from django.conf import settings

from apps.ai.openai_client import OpenAIBackendError, OpenAICompatibleClient
from apps.ai.prompt_catalog import render_prompt
from apps.matters.models import TriageAssessment, TriageRubric
from apps.sources.models import SourceConfiguration
from apps.core.content_library import content_path


DEFAULT_TRIAGE_RUBRIC_SLUG = "cleveland-rtc-priority"
REQUIRED_RUBRIC_FIELDS = {"slug", "name", "standard", "criteria"}


def rubric_seed_path(slug):
    return content_path("triage-rubrics", f"{slug}.yaml")


def load_triage_rubric_file(path):
    """Load and validate a human-maintained triage rubric file."""
    path = Path(path)
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"Could not read triage rubric {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Triage rubric {path} must contain a YAML mapping.")
    missing = REQUIRED_RUBRIC_FIELDS - payload.keys()
    if missing:
        raise ValueError(f"Triage rubric {path} is missing: {', '.join(sorted(missing))}.")
    if not isinstance(payload["criteria"], list) or not all(isinstance(item, str) for item in payload["criteria"]):
        raise ValueError(f"Triage rubric {path} must provide criteria as a list of strings.")
    return {
        "slug": str(payload["slug"]),
        "name": str(payload["name"]),
        "description": str(payload.get("description", "")),
        "standard": str(payload["standard"]),
        "criteria": payload["criteria"],
        "active": bool(payload.get("active", True)),
    }


def triage_rubric_seeds():
    directory = content_path("triage-rubrics")
    if not directory.exists():
        return []
    return [load_triage_rubric_file(path) for path in sorted(directory.glob("*.yaml"))]


def sync_triage_rubric_seeds(*, update_existing=False):
    """Create file-backed defaults without overwriting admin-managed records."""
    synced = []
    for seed in triage_rubric_seeds():
        rubric, created = TriageRubric.objects.get_or_create(slug=seed["slug"], defaults=seed)
        if update_existing and not created:
            for field, value in seed.items():
                if field != "slug":
                    setattr(rubric, field, value)
            rubric.save()
        synced.append((rubric, created))
    return synced


def ensure_default_triage_rubric():
    sync_triage_rubric_seeds()
    return TriageRubric.objects.get(slug=DEFAULT_TRIAGE_RUBRIC_SLUG)


def _flatten_payload(value, prefix=""):
    if isinstance(value, dict):
        for key, nested in value.items():
            label = f"{prefix}.{key}" if prefix else str(key)
            yield from _flatten_payload(nested, label)
    elif isinstance(value, list):
        for index, nested in enumerate(value[:10], start=1):
            yield from _flatten_payload(nested, f"{prefix}[{index}]")
    elif value not in (None, ""):
        yield f"{prefix}: {value}" if prefix else str(value)


def matter_triage_text(matter, *, max_chars=12000):
    sections = [
        f"Client/household: {matter.client_name}",
        f"Legal problem: {matter.matter_type}",
        f"Jurisdiction: {matter.jurisdiction}",
        f"Posture: {matter.posture}",
        f"Risk: {matter.risk}",
        f"Summary: {matter.summary}",
    ]
    facts = [
        f"- {fact.title}: {fact.text} [{fact.source_label}]"
        for fact in matter.facts.all()[:40]
    ]
    if facts:
        sections.append("Facts:\n" + "\n".join(facts))
    raw_lines = list(_flatten_payload(matter.raw_payload or {}))[:80]
    if raw_lines:
        sections.append("Case data:\n" + "\n".join(raw_lines))
    text = "\n\n".join(section for section in sections if section.strip())
    return text[:max_chars]


def _json_from_text(text):
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}


def _keyword_evidence(text, keywords):
    lower = text.lower()
    evidence = []
    for keyword in keywords:
        if keyword in lower:
            evidence.append({"label": keyword, "excerpt": keyword})
    return evidence


def fallback_triage_payload(matter, rubric, text):
    lower = text.lower()
    displacement_terms = ("eviction", "evict", "lockout", "forcible entry", "notice to leave", "termination")
    place_terms = ("cleveland", "cuyahoga", "housing court")
    priority_terms = (
        "child",
        "children",
        "minor",
        "disability",
        "disabled",
        "senior",
        "pregnant",
        "voucher",
        "section 8",
        "subsid",
        "public housing",
        "rental assistance",
        "lockout",
        "hearing",
        "default",
        "mold",
        "no heat",
        "domestic violence",
        "retaliation",
        "discrimination",
    )
    matched = []
    if any(term in lower for term in displacement_terms):
        matched.append("Eviction, termination, lockout, or displacement risk")
    if any(term in lower for term in place_terms):
        matched.append("Cleveland or Cuyahoga County housing forum")
    if any(term in lower for term in priority_terms):
        matched.append("Priority vulnerability or urgency indicator")
    priority = len(matched) >= 2 and any(term in lower for term in displacement_terms)
    missing = []
    if not any(term in lower for term in place_terms):
        missing.append("Confirm whether the case is in Cleveland or Cuyahoga County.")
    if not any(term in lower for term in priority_terms):
        missing.append("Ask about household composition, subsidy, disability, deadlines, and health or safety risks.")
    return {
        "case_type": "Eviction defense" if any(term in lower for term in displacement_terms) else matter.matter_type,
        "priority": priority,
        "priority_label": "priority_full_representation" if priority else "needs_review",
        "confidence": "medium" if priority else "needs_review",
        "summary": "Initial triage based on available case notes and facts.",
        "reasoning": (
            "The available information matches priority screening indicators."
            if priority
            else "The available information is incomplete or does not clearly satisfy the priority standard."
        ),
        "matched_criteria": matched,
        "missing_information": missing,
        "evidence": _keyword_evidence(text, [*displacement_terms, *place_terms, *priority_terms])[:8],
    }


def llm_triage_payload(matter, rubric, text):
    ai_config = SourceConfiguration.effective_settings("openai", {"enabled": settings.AI_DRAFTING_ENABLED})
    if str(ai_config.get("enabled", "")).lower() in {"0", "false", "no", "off"}:
        return {}
    client = OpenAICompatibleClient()
    criteria = "\n".join(f"- {item}" for item in (rubric.criteria or []))
    prompt = render_prompt(
        "triage.apply_rubric",
        rubric_name=rubric.name,
        standard=rubric.standard,
        criteria=criteria or "- None",
        case_information=text,
    )
    try:
        response = client.complete(
            system=prompt.system,
            user=prompt.user,
            temperature=0,
            model=prompt.default_model,
            reasoning_level=prompt.default_reasoning_level,
        )
    except OpenAIBackendError:
        return {}
    return _json_from_text(response)


def normalize_triage_payload(payload, fallback):
    merged = {**fallback, **{key: value for key, value in (payload or {}).items() if value not in (None, "")}}
    return {
        "case_type": str(merged.get("case_type") or "")[:255],
        "priority": bool(merged.get("priority")),
        "priority_label": str(merged.get("priority_label") or ("priority_full_representation" if merged.get("priority") else "needs_review"))[:120],
        "confidence": str(merged.get("confidence") or "needs_review")[:80],
        "summary": str(merged.get("summary") or ""),
        "reasoning": str(merged.get("reasoning") or ""),
        "matched_criteria": merged.get("matched_criteria") if isinstance(merged.get("matched_criteria"), list) else [],
        "missing_information": merged.get("missing_information") if isinstance(merged.get("missing_information"), list) else [],
        "evidence": merged.get("evidence") if isinstance(merged.get("evidence"), list) else [],
    }


def run_triage(matter, *, rubric=None, user=None):
    rubric = rubric or ensure_default_triage_rubric()
    text = matter_triage_text(matter)
    fallback = fallback_triage_payload(matter, rubric, text)
    llm_payload = llm_triage_payload(matter, rubric, text)
    normalized = normalize_triage_payload(llm_payload, fallback)
    return TriageAssessment.objects.create(
        matter=matter,
        rubric=rubric,
        created_by=user if getattr(user, "is_authenticated", False) else None,
        llm_payload=llm_payload,
        **normalized,
    )
