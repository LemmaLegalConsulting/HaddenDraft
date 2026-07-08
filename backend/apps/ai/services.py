import re
from dataclasses import dataclass

from django.conf import settings
from jinja2 import ChainableUndefined

from apps.ai.openai_client import OpenAIBackendError, OpenAICompatibleClient
from apps.ai.prompt_catalog import render_prompt
from apps.sources.models import SourceConfiguration
from apps.templates_app.template_variables import normalize_docxtpl_blocks, template_field_values
from apps.templates_app.jinja_filters import TEMPLATE_HELPERS_GUIDE, listify, template_environment


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
    template_data: dict | None = None


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
        if any(
            phrase in summary
            for phrase in ("rental assistance", "emergency rental assistance", "erap", "assistance application")
        ):
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
        text = re.sub(r"<br\s*/?>", "\n", text or "", flags=re.IGNORECASE)
        text = re.sub(r"(?m)^\s*```(?:\w+)?\s*$", "", text)
        text = re.sub(r"(?m)^\s*#{1,6}\s+", "", text)
        text = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", text)
        text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
        return text.strip()

    @staticmethod
    def _without_duplicate_heading(text, label):
        lines = text.splitlines()
        if not lines:
            return text
        normalized_label = re.sub(r"[^a-z0-9]+", "", (label or "").casefold())
        normalized_first = re.sub(r"[^a-z0-9]+", "", lines[0].casefold())
        if normalized_label and normalized_first == normalized_label:
            return "\n".join(lines[1:]).lstrip()
        return text

    def render_template_body(self, body, context):
        author = context.author_profile or {}
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
        template_data = template_field_values(context.template_data)
        client = {
            "name": context.matter.client_name,
            "pronouns": (context.template_data or {}).get("client_pronouns", ""),
            "title": (context.template_data or {}).get("client_title", ""),
        }
        household = listify((context.template_data or {}).get("other_occupants", []))
        values = {
            "fields": template_data,
            "matter": context.matter,
            "client": client,
            "household": household,
            "author": author,
            "court": context.matter.jurisdiction or getattr(context.template, "jurisdiction", ""),
            "plaintiff": template_data["plaintiff_name"],
            "defendant": context.matter.client_name,
            "case_number": (context.template_data or {}).get("court_case_number") or "[Court Case Number]",
            "advocate_name": author.get("displayName") or "Advocate",
            "advocate_signoff": author.get("signoff") or "Respectfully submitted,",
            "advocate_salutation": author.get("salutation") or "",
            "advocate_organization": author.get("organization") or "",
            "advocate_email": author.get("email") or "",
            "advocate_phone": author.get("phone") or "",
            "advocate_address": author.get("address") or "",
            "advocate_contact": contact,
            "advocate_signature_image": "[signature image]" if author.get("signatureImage") else "",
        }
        normalized_body = normalize_docxtpl_blocks(body)
        return template_environment(undefined=ChainableUndefined).from_string(normalized_body).render(values)

    def generate_curated_facts_section(self, facts, curated_facts):
        def clean_fact_text(value):
            value = re.sub(r"(?m)^\s*(?:[-•]|\d+[.)])\s*", "", value or "")
            return re.sub(r"\s+", " ", value).strip()

        lines = []
        index = 1
        for fact in facts:
            lines.append(f"{index}. {clean_fact_text(fact.text)} [{fact.source_label}]")
            index += 1
        for fact in curated_facts:
            source = fact.get("citation") or fact.get("source") or "curated source"
            lines.append(f"{index}. {clean_fact_text(fact.get('text', ''))} [{source}]")
            index += 1
        return "\n".join(lines) if lines else "No facts selected for this section."

    def generate_constrained_section(
        self,
        *,
        label,
        context,
        fallback,
        template_text=None,
        section_kind="section",
    ):
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
            section_kind=section_kind,
            template_title=getattr(context.template, "title", "Drafting template"),
            matter_summary=context.matter.summary,
            jurisdiction=context.matter.jurisdiction,
            client_name=context.matter.client_name,
            client_pronouns=(context.template_data or {}).get("client_pronouns") or "not supplied",
            household=", ".join(listify((context.template_data or {}).get("other_occupants", []))) or "not supplied",
            instructions=context.instructions,
            facts=facts or "- None",
            sources=sources or "- None",
            template_text=template_text or fallback or "- None",
            template_helpers=TEMPLATE_HELPERS_GUIDE,
        )
        try:
            generated = self.normalize_generated_text(client.complete(
                system=prompt.system,
                user=prompt.user,
                model=prompt.default_model,
                reasoning_level=prompt.default_reasoning_level,
            ))
            return self._without_duplicate_heading(generated, label)
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
                template_data=context.template_data,
            )
        else:
            scoped_context = context
        return self.generate_constrained_section(
            label=label,
            context=scoped_context,
            fallback=fallback,
            template_text=fallback,
            section_kind=section.get("blockType") or "section",
        )

    def compose_document(self, context, selected_block_keys):
        selected_facts = context.selected_facts
        selected_sources = context.selected_sources
        sections = []
        for block in context.template.blocks.all():
            if block.key not in selected_block_keys and not block.required:
                continue
            if block.block_type == "facts" and block.ai_fill_mode == "constrained_generation":
                evidence_fallback = self.generate_curated_facts_section(
                    selected_facts,
                    context.selected_curated_facts,
                )
                template_text = self.render_template_body(block.body, context)
                body = self.generate_constrained_section(
                    label=block.label,
                    context=context,
                    fallback=evidence_fallback,
                    template_text=template_text,
                    section_kind="facts",
                )
            elif block.block_type == "facts":
                body = self.generate_curated_facts_section(selected_facts, context.selected_curated_facts)
            elif block.ai_fill_mode == "constrained_generation":
                fallback = self.render_template_body(block.body, context) if "{{" in block.body or "{%" in block.body else block.body
                body = self.generate_constrained_section(
                    label=block.label,
                    context=context,
                    fallback=fallback,
                    template_text=fallback,
                    section_kind=block.block_type,
                )
            elif "{{" in block.body or "{%" in block.body:
                body = self.render_template_body(block.body, context)
            else:
                body = block.body
            section_sources = list(block.supporting_sources)
            if block.ai_fill_mode == "constrained_generation":
                section_sources.extend(selected_sources)
            if block.block_type == "facts":
                section_sources.extend(
                    fact.source_label for fact in selected_facts if fact.source_label
                )
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
