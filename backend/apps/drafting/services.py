from apps.ai.services import GenerationContext, drafting_ai
from apps.drafting.models import DraftDocument
from apps.matters.models import MatterFact


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


def recommend_fact_ids(session):
    """Suggest facts from template/block needs, then let a human review them."""
    recommended_slugs = list(drafting_ai.recommend_fact_slugs(session.matter))
    for slug in _selected_fact_slugs_for_blocks(session):
        if slug not in recommended_slugs:
            recommended_slugs.append(slug)
    facts = MatterFact.objects.filter(matter=session.matter).order_by("id")
    selected = [fact.id for fact in facts if fact.selected_by_default or fact.slug in recommended_slugs]
    if selected:
        return selected
    return list(facts.values_list("id", flat=True)[:5])


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


def recommend_support_candidates(session, *, user=None, request=None, limit_per_source=3):
    query = support_query_for_session(session)
    if not query:
        return {"query": "", "candidates": [], "selectedSourceIds": []}

    from apps.sources.registry import connector_registry
    from apps.sources.selection import automatic_source_selection, source_kinds

    selection = automatic_source_selection(query, matter=session.matter)
    results = connector_registry.search(
        query,
        kinds=source_kinds(selection["source_ids"]),
        source_ids=selection["source_ids"],
        matter=session.matter,
        jurisdiction=session.matter.jurisdiction,
        limit_per_source=limit_per_source,
        user=user,
        request=request,
    )
    return {
        "query": query,
        "selectedSourceIds": selection["source_ids"],
        "sourceDecision": selection,
        "candidates": [result_to_support_candidate(result) for result in results],
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
