from dataclasses import dataclass

from django.conf import settings

from apps.ai.openai_client import OpenAIBackendError, OpenAICompatibleClient
from apps.sources.models import SourceConfiguration


@dataclass
class GenerationContext:
    matter: object
    selected_facts: list
    selected_sources: list
    template: object
    mode: str
    instructions: str = ""


class ConstrainedDraftingService:
    """Drafting boundary with deterministic fallbacks and optional LLM calls."""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def recommend_fact_slugs(self, matter):
        summary = matter.summary.lower()
        slugs = []
        if "rent" in summary or "nonpayment" in summary:
            slugs.append("rent-dispute")
        if "repair" in summary or "mold" in summary or "leak" in summary:
            slugs.extend(["repair-issues", "habitability-defense"])
        if "assistance" in summary:
            slugs.append("rental-assistance")
        return slugs

    def recommend_blocks(self, template, selected_fact_slugs):
        recommended = []
        selected = set(selected_fact_slugs)
        for block in template.blocks.all():
            required_slugs = set(block.selection_rule.get("fact_slugs", []))
            if block.required or not required_slugs or required_slugs.intersection(selected):
                recommended.append(block.key)
        return recommended

    def generate_facts_section(self, facts):
        lines = []
        for index, fact in enumerate(facts, start=1):
            lines.append(f"{index}. {fact.text} [{fact.source_label}]")
        return "\n".join(lines) if lines else "No facts selected for this section."

    def generate_constrained_section(self, *, label, context, fallback):
        ai_config = SourceConfiguration.effective_settings("openai", {"enabled": settings.AI_DRAFTING_ENABLED})
        if str(ai_config.get("enabled", "")).lower() in {"0", "false", "no", "off"}:
            return fallback
        client = self.llm_client or OpenAICompatibleClient()
        sources = "\n".join(
            f"- {source.get('title') or source.get('citation')}: {source.get('snippet', '')}"
            for source in context.selected_sources
        )
        facts = "\n".join(f"- {fact.text} [{fact.source_label}]" for fact in context.selected_facts)
        prompt = (
            f"Draft the {label} section for a housing court document.\n"
            f"Matter: {context.matter.summary}\n"
            f"Jurisdiction: {context.matter.jurisdiction}\n"
            f"Client: {context.matter.client_name}\n"
            f"Instructions: {context.instructions}\n"
            f"Selected facts:\n{facts or '- None'}\n"
            f"Selected sources:\n{sources or '- None'}\n"
            "Use only the provided facts and sources. Do not invent citations."
        )
        try:
            return client.complete(
                system="You draft constrained legal document sections from supplied facts and sources.",
                user=prompt,
            )
        except OpenAIBackendError:
            return fallback

    def compose_document(self, context, selected_block_keys):
        selected_facts = context.selected_facts
        selected_sources = context.selected_sources
        sections = []
        for block in context.template.blocks.all():
            if block.key not in selected_block_keys and not block.required:
                continue
            if block.block_type == "facts" or block.ai_fill_mode == "constrained_generation" and block.key == "facts":
                body = self.generate_facts_section(selected_facts)
            elif block.ai_fill_mode == "constrained_generation":
                body = self.generate_constrained_section(label=block.label, context=context, fallback=block.body)
            elif "{{" in block.body:
                body = (
                    block.body.replace("{{ court }}", context.matter.jurisdiction)
                    .replace("{{ plaintiff }}", "Plaintiff")
                    .replace("{{ defendant }}", context.matter.client_name)
                    .replace("{{ case_number }}", context.matter.external_id)
                    .replace("{{ advocate_name }}", "Advocate")
                )
            else:
                body = block.body
            sections.append({"key": block.key, "label": block.label, "body": body, "sources": block.supporting_sources})

        if context.mode == "draft_from_scratch" and context.instructions:
            sections.insert(
                1,
                {
                    "key": "theory",
                    "label": "Theory",
                    "body": context.instructions,
                    "sources": [source.get("citation") for source in selected_sources if source.get("citation")],
                },
            )
        return sections


drafting_ai = ConstrainedDraftingService()
