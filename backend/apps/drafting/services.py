from apps.ai.services import GenerationContext, drafting_ai
from apps.drafting.models import DraftDocument
from apps.matters.models import MatterFact


STEP_ORDER = ["case", "facts", "template", "law", "draft", "export"]


def advance(session, payload):
    if "selectedFactIds" in payload:
        session.selected_fact_ids = payload["selectedFactIds"]
    if "selectedCuratedFacts" in payload:
        session.selected_curated_facts = payload["selectedCuratedFacts"]
    if "selectedSourceResults" in payload:
        session.selected_source_results = payload["selectedSourceResults"]
    if "selectedBlockKeys" in payload:
        session.selected_block_keys = payload["selectedBlockKeys"]
    if "instructions" in payload:
        session.instructions = payload["instructions"]
    if "template" in payload:
        session.template_id = payload["template"]
    if "status" in payload and payload["status"] in STEP_ORDER:
        session.status = payload["status"]
    elif session.status in STEP_ORDER:
        index = STEP_ORDER.index(session.status)
        session.status = STEP_ORDER[min(index + 1, len(STEP_ORDER) - 1)]
    session.save()
    return session


def initialize_session(session):
    recommended_slugs = drafting_ai.recommend_fact_slugs(session.matter)
    if recommended_slugs and not session.selected_fact_ids:
        session.selected_fact_ids = list(
            MatterFact.objects.filter(matter=session.matter, slug__in=recommended_slugs).values_list("id", flat=True)
        )
    if session.template and not session.selected_block_keys:
        selected_facts = MatterFact.objects.filter(id__in=session.selected_fact_ids)
        selected_slugs = [fact.slug for fact in selected_facts]
        session.selected_block_keys = drafting_ai.recommend_blocks(session.template, selected_slugs)
    session.save()
    return session


def create_draft(session):
    facts = list(MatterFact.objects.filter(id__in=session.selected_fact_ids))
    context = GenerationContext(
        matter=session.matter,
        selected_facts=facts,
        selected_curated_facts=session.selected_curated_facts,
        selected_sources=session.selected_source_results,
        template=session.template,
        mode=session.mode,
        instructions=session.instructions,
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
    session.status = "draft"
    session.save()
    return draft
