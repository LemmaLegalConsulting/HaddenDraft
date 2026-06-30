import json

from django.conf import settings

from apps.ai.openai_client import OpenAIBackendError, OpenAICompatibleClient
from apps.ai.services import GenerationContext, drafting_ai
from apps.drafting.models import DraftDocument
from apps.matters.models import MatterFact
from apps.sources.models import SourceConfiguration


WORKFLOW_STEPS = [
    {
        "id": "setup",
        "label": "Choose document",
        "help": "Choose what you are drafting and confirm the template or drafting instructions.",
    },
    {
        "id": "facts_review",
        "label": "Review facts",
        "help": "Review the facts the draft may use. Suggested facts are preselected, but a human should confirm them.",
    },
    {
        "id": "support_review",
        "label": "Review support",
        "help": "Confirm authorities, examples, and references the draft may rely on. Case evidence belongs in the facts step.",
    },
    {
        "id": "law_review",
        "label": "Review legal issues",
        "help": "Approve or reject candidate legal issues before they activate draft sections.",
    },
    {
        "id": "outline_review",
        "label": "Approve outline",
        "help": "Review the sections and supporting inputs before generating prose.",
    },
    {
        "id": "draft_review",
        "label": "Review draft",
        "help": "Edit, refine, and save each generated section before validation.",
    },
    {
        "id": "validation",
        "label": "Validate",
        "help": "Run checks for missing facts, tentative language, citations, and length.",
    },
    {
        "id": "export",
        "label": "Export",
        "help": "Export only after the human reviewer is comfortable with the draft and remaining flags.",
    },
]
STEP_ORDER = [step["id"] for step in WORKFLOW_STEPS]

LEGACY_STATUS_MAP = {
    "case": "setup",
    "facts": "facts_review",
    "template": "setup",
    "law": "law_review",
    "draft": "draft_review",
}

SUPPORT_PURPOSE_LABELS = {
    "legal_authority": "Legal authority",
    "example_language": "Example language",
    "background_reference": "Background reference",
}


def normalize_status(status):
    return LEGACY_STATUS_MAP.get(status, status)


def workflow_step_payload():
    return WORKFLOW_STEPS


def _ordered_blocks(session):
    if not session.template:
        return []
    blocks = list(session.template.blocks.all())
    selected = set(session.selected_block_keys or [])
    if not selected:
        return blocks
    return [block for block in blocks if block.required or block.key in selected]


def _selected_fact_slugs_for_blocks(session):
    slugs = []
    for block in _ordered_blocks(session):
        for slug in block.selection_rule.get("fact_slugs", []):
            if slug not in slugs:
                slugs.append(slug)
    return slugs


def _ai_review_enabled():
    config = SourceConfiguration.effective_settings("openai", {"enabled": settings.AI_DRAFTING_ENABLED})
    return str(config.get("enabled", "")).lower() not in {"0", "false", "no", "off"}


def _parse_json_response(text):
    if not text:
        return None
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(stripped[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


def _ai_json(system, user):
    if not _ai_review_enabled():
        return None
    try:
        response = OpenAICompatibleClient().complete(system=system, user=user, temperature=0.0)
    except OpenAIBackendError:
        return None
    return _parse_json_response(response)


def _fact_review_payload(session, facts):
    blocks = [f"- {block.key}: {block.label} ({block.block_type})" for block in _ordered_blocks(session)]
    fact_lines = [f"- id={fact.id}; slug={fact.slug}; title={fact.title}; text={fact.text}; source={fact.source_label}" for fact in facts]
    return "\n".join(
        [
            f"Matter summary: {session.matter.summary}",
            f"Jurisdiction: {session.matter.jurisdiction}",
            f"Template: {session.template.title if session.template else 'No template'}",
            f"Instructions: {session.instructions or '-'}",
            "Draft sections needing facts:",
            "\n".join(blocks) or "- None",
            "Available facts:",
            "\n".join(fact_lines) or "- None",
        ]
    )


def _ai_recommend_fact_ids(session, facts):
    payload = _fact_review_payload(session, facts)
    data = _ai_json(
        "You select facts for a legal drafting workflow. Select only facts relevant to the selected template, active sections, jurisdiction, and instructions. Return strict JSON.",
        f"{payload}\n\nReturn JSON with this shape: {{\"selected_ids\": [1, 2], \"reason\": \"short explanation\"}}",
    )
    if not isinstance(data, dict):
        return None
    available = {fact.id for fact in facts}
    selected = [int(value) for value in data.get("selected_ids", []) if str(value).isdigit() and int(value) in available]
    return selected or None


def recommend_fact_ids(session):
    """Have AI suggest facts from the template/block needs, with deterministic fallback."""
    facts = list(MatterFact.objects.filter(matter=session.matter).order_by("id"))
    ai_selected = _ai_recommend_fact_ids(session, facts)
    if ai_selected:
        return ai_selected

    recommended_slugs = list(drafting_ai.recommend_fact_slugs(session.matter))
    for slug in _selected_fact_slugs_for_blocks(session):
        if slug not in recommended_slugs:
            recommended_slugs.append(slug)
    selected = [fact.id for fact in facts if fact.selected_by_default or fact.slug in recommended_slugs]
    if selected:
        return selected
    return [fact.id for fact in facts[:5]]


def initialize_session(session):
    if session.status in LEGACY_STATUS_MAP:
        session.status = normalize_status(session.status)
    if session.template and not session.selected_block_keys:
        session.selected_block_keys = drafting_ai.recommend_blocks(session.template, _selected_fact_slugs_for_blocks(session))
    if not session.selected_fact_ids:
        session.selected_fact_ids = recommend_fact_ids(session)
    session.save()
    return session


def _validate_transition(session, target_status):
    if target_status == "support_review" and not session.selected_fact_ids:
        raise ValueError("Review and select facts before choosing drafting support.")
    if target_status in {"law_review", "outline_review", "draft_review"} and not session.selected_fact_ids:
        raise ValueError("Review and select facts before continuing.")
    if target_status in {"outline_review", "draft_review"} and not session.selected_block_keys:
        raise ValueError("Select at least one draft section before continuing.")


def advance(session, payload):
    if "selectedFactIds" in payload:
        session.selected_fact_ids = payload["selectedFactIds"]
    if "selectedCuratedFacts" in payload:
        session.selected_curated_facts = payload["selectedCuratedFacts"]
    if "selectedSourceResults" in payload:
        session.selected_source_results = payload["selectedSourceResults"]
    if "selectedBlockKeys" in payload:
        session.selected_block_keys = payload["selectedBlockKeys"]
    if "authorProfile" in payload:
        session.author_profile = payload["authorProfile"] or {}
    if "instructions" in payload:
        session.instructions = payload["instructions"]
    if "template" in payload:
        session.template_id = payload["template"]

    current_status = normalize_status(session.status)
    requested_status = payload.get("status")
    if requested_status:
        target_status = normalize_status(requested_status)
        if target_status not in STEP_ORDER:
            raise ValueError("Unsupported drafting workflow step.")
    elif current_status in STEP_ORDER:
        index = STEP_ORDER.index(current_status)
        target_status = STEP_ORDER[min(index + 1, len(STEP_ORDER) - 1)]
    else:
        target_status = "setup"

    _validate_transition(session, target_status)
    session.status = target_status
    session.save()
    return session


def _selected_facts(session):
    return list(MatterFact.objects.filter(id__in=session.selected_fact_ids).order_by("id"))


def create_draft(session):
    facts = _selected_facts(session)
    context = GenerationContext(
        matter=session.matter,
        selected_facts=facts,
        selected_curated_facts=session.selected_curated_facts,
        selected_sources=session.selected_source_results,
        template=session.template,
        mode=session.mode,
        instructions=session.instructions,
        author_profile=session.author_profile,
    )
    block_keys = session.selected_block_keys or [block.key for block in session.template.blocks.all()]
    sections = drafting_ai.compose_document(context, block_keys)
    plain_text = "\n\n".join(f"{section['label'].upper()}\n{section['body']}" for section in sections)
    draft = DraftDocument.objects.create(
        session=session,
        title=session.template.title if session.template else "Draft document",
        sections=sections,
        plain_text=plain_text,
        editor_state={"format": "plain_text"},
    )
    session.status = "draft_review"
    session.save()
    return draft


def plain_text_from_sections(sections):
    return "\n\n".join(f"{section.get('label', '').upper()}\n{section.get('body', '')}" for section in sections)


def regeneration_context(session):
    facts = _selected_facts(session)
    return GenerationContext(
        matter=session.matter,
        selected_facts=facts,
        selected_curated_facts=session.selected_curated_facts,
        selected_sources=session.selected_source_results,
        template=session.template,
        mode=session.mode,
        instructions=session.instructions,
        author_profile=session.author_profile,
    )


def regenerate_draft_block(draft, block_key, instruction=""):
    context = regeneration_context(draft.session)
    sections = list(draft.sections or [])
    next_sections = []
    updated = None
    for section in sections:
        if section.get("key") == block_key:
            updated = {
                **section,
                "body": drafting_ai.regenerate_section(section=section, context=context, instruction=instruction),
                "origin": "ai",
            }
            next_sections.append(updated)
        else:
            next_sections.append(section)
    if updated is None:
        return draft
    draft.sections = next_sections
    draft.plain_text = plain_text_from_sections(next_sections)
    draft.editor_state = {"format": "lexical_blocks", "blocks": {}}
    draft.save()
    return draft


def support_query_for_session(session):
    parts = [session.matter.summary, session.matter.jurisdiction, session.instructions]
    if session.template:
        parts.append(session.template.title)
        parts.extend(block.label for block in _ordered_blocks(session))
    for fact in _selected_facts(session)[:8]:
        parts.append(fact.text)
    return " ".join(part for part in parts if part).strip()


def support_purpose_for_result(result):
    title = (getattr(result, "title", "") or "").casefold()
    source_kind = getattr(result, "source_kind", "")
    metadata = getattr(result, "metadata", {}) or {}
    resource_type = str(metadata.get("resourceType") or metadata.get("resource_type") or "").casefold()
    citation = getattr(result, "citation", "") or ""
    if source_kind in {"local_cases", "rag"} and citation:
        return "legal_authority"
    if source_kind in {"sharepoint", "user_resources"} or resource_type in {"brief", "example"}:
        if any(term in title for term in ["answer", "motion", "brief", "pleading", "filing"]):
            return "example_language"
    return "background_reference"


def result_to_support_candidate(result):
    purpose = support_purpose_for_result(result)
    payload = result.to_dict() if hasattr(result, "to_dict") else {
        "id": getattr(result, "id", ""),
        "title": getattr(result, "title", ""),
        "snippet": getattr(result, "snippet", ""),
        "sourceKind": getattr(result, "source_kind", ""),
        "sourceLabel": getattr(result, "source_label", ""),
        "url": getattr(result, "url", ""),
        "citation": getattr(result, "citation", ""),
        "metadata": getattr(result, "metadata", {}) or {},
    }
    return {
        **payload,
        "purpose": purpose,
        "purposeLabel": SUPPORT_PURPOSE_LABELS[purpose],
        "selectedByDefault": purpose in {"legal_authority", "example_language"},
    }


def _source_catalog_for_ai():
    from apps.sources.selection import source_guidance

    sources = source_guidance()["sources"]
    return "\n".join(
        f"- id={source_id}; label={source.get('label', source_id)}; kind={source.get('kind')}; reason={source.get('default_reason', '')}"
        for source_id, source in sources.items()
    )


def _ai_select_source_ids(query, session):
    from apps.sources.selection import source_guidance

    available = set(source_guidance()["sources"])
    data = _ai_json(
        "You select source libraries for a legal drafting support review. Pick only libraries likely to contain relevant authorities, examples, or references. Return strict JSON.",
        "\n".join(
            [
                f"Drafting support query: {query}",
                f"Matter summary: {session.matter.summary}",
                f"Jurisdiction: {session.matter.jurisdiction}",
                "Available source libraries:",
                _source_catalog_for_ai(),
                "Return JSON with this shape: {\"selected_source_ids\": [\"ohio-statutes\"], \"reason\": \"short explanation\"}",
            ]
        ),
    )
    if not isinstance(data, dict):
        return None
    selected = [source_id for source_id in data.get("selected_source_ids", []) if source_id in available]
    return selected or None


def _ai_select_candidate_ids(query, candidates):
    candidate_lines = []
    for candidate in candidates[:20]:
        candidate_lines.append(
            f"- id={candidate.get('id')}; purpose={candidate.get('purpose')}; title={candidate.get('title')}; source={candidate.get('sourceLabel')}; citation={candidate.get('citation')}; snippet={candidate.get('snippet')}"
        )
    data = _ai_json(
        "You select drafting support candidates. Select only sources the draft may rely on. Prefer legal authority and high-value example language. Return strict JSON.",
        "\n".join(
            [
                f"Drafting support query: {query}",
                "Candidate sources:",
                "\n".join(candidate_lines) or "- None",
                "Return JSON with this shape: {\"selected_candidate_ids\": [\"id\"], \"reason\": \"short explanation\"}",
            ]
        ),
    )
    if not isinstance(data, dict):
        return None
    available = {str(candidate.get("id")) for candidate in candidates}
    selected = [str(candidate_id) for candidate_id in data.get("selected_candidate_ids", []) if str(candidate_id) in available]
    return selected or None


def recommend_support_candidates(session, *, user=None, request=None, limit_per_source=3):
    query = support_query_for_session(session)
    if not query:
        return {"query": "", "candidates": [], "selectedSourceIds": []}

    from apps.sources.registry import connector_registry
    from apps.sources.selection import automatic_source_selection, source_kinds

    ai_source_ids = _ai_select_source_ids(query, session)
    selection = automatic_source_selection(query, matter=session.matter)
    source_ids = ai_source_ids or selection["source_ids"]
    results = connector_registry.search(
        query,
        kinds=source_kinds(source_ids),
        source_ids=source_ids,
        matter=session.matter,
        jurisdiction=session.matter.jurisdiction,
        limit_per_source=limit_per_source,
        user=user,
        request=request,
    )
    candidates = [result_to_support_candidate(result) for result in results]
    ai_candidate_ids = _ai_select_candidate_ids(query, candidates)
    if ai_candidate_ids is not None:
        selected = set(ai_candidate_ids)
        candidates = [{**candidate, "selectedByDefault": str(candidate.get("id")) in selected} for candidate in candidates]
    return {
        "query": query,
        "selectedSourceIds": source_ids,
        "sourceDecision": {**selection, "source_ids": source_ids, "aiReviewed": bool(ai_source_ids)},
        "candidates": candidates,
        "aiReviewed": ai_candidate_ids is not None,
    }


def outline_for_session(session):
    issues = []
    try:
        from apps.issues.models import CandidateIssue

        issues = list(CandidateIssue.objects.filter(case_id=session.matter.external_id, status="approved"))
    except Exception:
        issues = []
    approved_issue_blocks = set()
    for issue in issues:
        approved_issue_blocks.update(issue.outputs.get("activate_blocks_after_approval", []))
    selected_keys = set(session.selected_block_keys or []) | approved_issue_blocks
    blocks = []
    template_blocks = list(session.template.blocks.all()) if session.template else []
    for block in template_blocks:
        selected = block.required or block.key in selected_keys
        if not selected:
            continue
        blocks.append(
            {
                "key": block.key,
                "label": block.label,
                "blockType": block.block_type,
                "required": block.required,
                "selected": selected,
                "aiFillMode": block.ai_fill_mode,
                "supportCount": len(block.supporting_sources or []),
            }
        )
    return {
        "blocks": blocks,
        "selectedFactCount": len(session.selected_fact_ids or []),
        "selectedCuratedFactCount": len(session.selected_curated_facts or []),
        "selectedSupportCount": len(session.selected_source_results or []),
        "approvedIssues": [issue.title for issue in issues],
    }
