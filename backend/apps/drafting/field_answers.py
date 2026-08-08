"""Answer a template's blanks from the case record before asking the advocate.

Every blank in a prepared template used to become a question, which meant an
advocate retyped the rental address that was already in their own intake notes
and answered "What is the describe occupants?" -- a drafting instruction turned
into a question of fact.

This module asks the model to do the reading first: for each blank the classifier
in :mod:`apps.templates_app.field_questions` did not rule out, decide whether the
case record already answers it, and if it does, supply the answer with the basis
for it. What is left over is the short list of things only the advocate knows.

The answers are suggestions, not commitments. Every one is returned to the
pre-draft review with its basis so a person can correct it before it reaches a
filing, and the model is told to hand a blank back rather than narrow it when the
record is silent, partial, or contradictory.
"""

from __future__ import annotations

from apps.ai.openai_client import OpenAIBackendError, OpenAICompatibleClient
from apps.ai.prompt_catalog import PromptCatalogError, PromptRenderError, render_prompt
from apps.templates_app.field_questions import KIND_UNUSABLE


# The record is the model's only evidence, so it is worth sending generously;
# this bound only keeps one enormous uploaded document from crowding out the
# rest of the case.
MAX_FACT_CHARS = 4000
MAX_FACTS = 40


def _fact_lines(facts, curated_facts):
    lines = []
    for fact in facts:
        text = " ".join((fact.text or "").split())[:MAX_FACT_CHARS]
        label = fact.source_label or "case record"
        lines.append(f"- {fact.title}: {text} [{label}]")
    for fact in curated_facts or []:
        text = " ".join(str(fact.get("text") or "").split())[:MAX_FACT_CHARS]
        if not text:
            continue
        label = fact.get("citation") or fact.get("source") or "curated source"
        lines.append(f"- {text} [{label}]")
    return lines[:MAX_FACTS]


def _request_lines(requests):
    lines = []
    for request in requests:
        parts = [f"- key: {request.key}", f"kind: {request.kind}", f"asks: {request.question}"]
        if request.context:
            parts.append(f'template sentence: "{request.context}"')
        if request.block_label:
            parts.append(f"section: {request.block_label}")
        lines.append("; ".join(parts))
    return lines


def resolvable_requests(requests):
    """The blanks worth spending a model call on."""
    return [request for request in requests if request.kind != KIND_UNUSABLE]


def resolve_field_requests(
    session,
    template,
    requests,
    *,
    facts=(),
    client=None,
    enabled=True,
):
    """Answer what the case record answers, keyed by field name.

    Returns ``{key: {"value": str, "basis": str, "question": str}}``, holding only
    the blanks the model resolved or reworded. A disabled or failing model is not
    an error: the caller falls back to the template's own questions.
    """
    resolvable = resolvable_requests(requests)
    if not resolvable or not enabled:
        return {}
    matter = session.matter
    details = [matter.matter_type, matter.posture, matter.risk]
    try:
        prompt = render_prompt(
            "drafting.template_fields",
            template_title=getattr(template, "title", "Drafting template"),
            jurisdiction=matter.jurisdiction or "not supplied",
            client_name=matter.client_name or "not supplied",
            matter_summary=matter.summary or "not supplied",
            matter_details=", ".join(item for item in details if item) or "not supplied",
            goal=session.goal or session.instructions or "not supplied",
            facts="\n".join(_fact_lines(facts, session.selected_curated_facts)) or "- None",
            requests="\n".join(_request_lines(resolvable)),
        )
    except (PromptCatalogError, PromptRenderError):
        return {}

    from apps.drafting.services import _parse_json_response

    try:
        response = (client or OpenAICompatibleClient()).complete(
            system=prompt.system,
            user=prompt.user,
            model=prompt.default_model,
            reasoning_level=prompt.default_reasoning_level,
        )
    except OpenAIBackendError:
        return {}

    data = _parse_json_response(response)
    if not isinstance(data, dict):
        return {}
    by_key = {request.key: request for request in resolvable}
    resolved = {}
    for entry in data.get("fields") or []:
        if not isinstance(entry, dict):
            continue
        key = str(entry.get("key") or "").strip()
        if key not in by_key:
            continue
        value = " ".join(str(entry.get("value") or "").split())
        question = " ".join(str(entry.get("question") or "").split())
        if not entry.get("answered_from_record"):
            value = ""
        if not value and not question:
            continue
        resolved[key] = {
            "value": value,
            "basis": " ".join(str(entry.get("basis") or "").split()),
            "question": question,
        }
    return resolved
