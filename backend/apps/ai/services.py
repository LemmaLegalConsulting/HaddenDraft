import re
from dataclasses import dataclass

from django.conf import settings

from apps.ai.openai_client import OpenAIBackendError, OpenAICompatibleClient
from apps.ai.prompt_catalog import render_prompt
from apps.sources.models import SourceConfiguration


@dataclass
class GenerationContext:
    matter: object
    selected_facts: list
    selected_curated_facts: list
    selected_sources: list
    template: object
    mode: str
    instructions: str = ""
    author_profile: dict | None = None


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

    def normalize_generated_text(self, text):
        return re.sub(r"<br\s*/?>", "\n", text or "", flags=re.IGNORECASE)

    def generate_curated_facts_section(self, facts, curated_facts):
        lines = []
        index = 1
        for fact in facts:
            lines.append(f"{index}. {fact.text} [{fact.source_label}]")
            index += 1
        for fact in curated_facts:
            source = fact.get("citation") or fact.get("source") or "curated source"
            lines.append(f"{index}. {fact.get('text', '')} [{source}]")
            index += 1
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
        model_facts = [f"- {fact.text} [{fact.source_label}]" for fact in context.selected_facts]
        for fact in context.selected_curated_facts:
            source = fact.get("citation") or fact.get("source") or "curated source"
            excerpt = fact.get("sourceExcerpt", "")
            model_facts.append(f"- {fact.get('text', '')} [{source}]{f' Evidence: {excerpt}' if excerpt else ''}")
        facts = "\n".join(model_facts)
        prompt = render_prompt(
            "drafting.constrained_section",
            label=label,
            matter_summary=context.matter.summary,
            jurisdiction=context.matter.jurisdiction,
            client_name=context.matter.client_name,
            instructions=context.instructions,
            facts=facts or "- None",
            sources=sources or "- None",
        )
        try:
            return self.normalize_generated_text(client.complete(
                system=prompt.system,
                user=prompt.user,
                model=prompt.default_model,
                reasoning_level=prompt.default_reasoning_level,
            ))
        except OpenAIBackendError:
            return fallback

    def regenerate_section(self, *, section, context, instruction=""):
        fallback = section.get("body", "")
        label = section.get("label", "Draft block")
        if instruction:
            scoped_context = GenerationContext(
                matter=context.matter,
                selected_facts=context.selected_facts,
                selected_curated_facts=context.selected_curated_facts,
                selected_sources=context.selected_sources,
                template=context.template,
                mode=context.mode,
                instructions=f"{context.instructions}\n\nBlock refinement instruction: {instruction}".strip(),
                author_profile=context.author_profile,
            )
        else:
            scoped_context = context
        return self.generate_constrained_section(label=label, context=scoped_context, fallback=fallback)

    def compose_document(self, context, selected_block_keys):
        selected_facts = context.selected_facts
        selected_sources = context.selected_sources
        sections = []
        for block in context.template.blocks.all():
            if block.key not in selected_block_keys and not block.required:
                continue
            if block.block_type == "facts" or block.ai_fill_mode == "constrained_generation" and block.key == "facts":
                body = self.generate_curated_facts_section(selected_facts, context.selected_curated_facts)
            elif block.ai_fill_mode == "constrained_generation":
                body = self.generate_constrained_section(label=block.label, context=context, fallback=block.body)
            elif "{{" in block.body:
                author = context.author_profile or {}
                author_name = author.get("displayName") or "Advocate"
                author_signoff = author.get("signoff") or "Respectfully submitted,"
                contact = "\n".join(
                    item
                    for item in [
                        author.get("organization", ""),
                        author.get("address", ""),
                        author.get("phone", ""),
                        author.get("email", ""),
                    ]
                    if item
                )
                signature_marker = "[signature image]" if author.get("signatureImage") else ""
                body = (
                    block.body.replace("{{ court }}", context.matter.jurisdiction)
                    .replace("{{ plaintiff }}", "Plaintiff")
                    .replace("{{ defendant }}", context.matter.client_name)
                    .replace("{{ case_number }}", context.matter.external_id)
                    .replace("{{ advocate_name }}", author_name)
                    .replace("{{ advocate_signoff }}", author_signoff)
                    .replace("{{ advocate_salutation }}", author.get("salutation") or "")
                    .replace("{{ advocate_organization }}", author.get("organization") or "")
                    .replace("{{ advocate_email }}", author.get("email") or "")
                    .replace("{{ advocate_phone }}", author.get("phone") or "")
                    .replace("{{ advocate_address }}", author.get("address") or "")
                    .replace("{{ advocate_contact }}", contact)
                    .replace("{{ advocate_signature_image }}", signature_marker)
                )
            else:
                body = block.body
            section_sources = list(block.supporting_sources)
            if block.ai_fill_mode == "constrained_generation":
                section_sources.extend(selected_sources)
            sections.append({
                "key": block.key,
                "label": block.label,
                "body": self.normalize_generated_text(body),
                "sources": section_sources,
                "blockType": block.block_type,
                "aiFillMode": block.ai_fill_mode,
                "origin": "ai" if block.ai_fill_mode == "constrained_generation" else "template",
                "format": {
                    "style": "numbered" if block.block_type in {"facts", "argument", "optional_clause"} else "plain",
                    "headingNumbering": "none",
                },
            })

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
