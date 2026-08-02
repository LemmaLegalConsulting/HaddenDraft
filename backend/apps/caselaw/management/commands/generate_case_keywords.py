import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.ai.openai_client import OpenAIBackendError, OpenAICompatibleClient
from apps.ai.prompt_catalog import render_prompt
from apps.caselaw.importing import add_search_doc
from apps.caselaw.models import CaseLawDecision

EXCERPT_CHARS = 6000
MAX_KEYWORDS = 15


def _keyword_list(response_text):
    payload = json.loads(response_text)
    if not isinstance(payload, dict) or not isinstance(payload.get("keywords"), list):
        raise ValueError("Response must be a JSON object with a keywords list")
    keywords = []
    for value in payload["keywords"]:
        phrase = " ".join(str(value).casefold().split())
        if phrase and phrase not in keywords:
            keywords.append(phrase)
    return keywords[:MAX_KEYWORDS]


def generate_keywords_for_decision(decision, client):
    excerpt = ""
    first_chunk = decision.chunks.filter(chunk_type="body").order_by("ordinal").first()
    if first_chunk:
        excerpt = first_chunk.text[:EXCERPT_CHARS]
    prompt = render_prompt(
        "caselaw.search_keywords",
        title=decision.title,
        court=decision.court,
        issues=json.dumps(decision.issues, ensure_ascii=False),
        holdings=json.dumps(decision.holdings, ensure_ascii=False),
        rules=json.dumps(decision.rules_applied, ensure_ascii=False),
        statutes=json.dumps(decision.statutes_cited, ensure_ascii=False),
        outcome=decision.outcome,
        key_facts=decision.key_facts,
        excerpt=excerpt or "(no opinion text available)",
    )
    response = client.complete(
        system=prompt.system,
        user=prompt.user,
        temperature=0,
        model=prompt.default_model,
        reasoning_level=prompt.default_reasoning_level,
    )
    return _keyword_list(response)


class Command(BaseCommand):
    help = "Generate researcher-phrased search keywords for ingested case-law decisions."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int)
        parser.add_argument("--force", action="store_true", help="Regenerate keywords that already exist.")
        parser.add_argument("--dry-run", action="store_true", help="Print keywords without saving them.")

    def handle(self, *args, **options):
        if not settings.AI_DRAFTING_ENABLED:
            raise CommandError("AI keyword generation requires AI_DRAFTING_ENABLED; keywords can also be supplied as search_keywords in sidecar metadata JSON.")

        queryset = CaseLawDecision.objects.filter(approved_for_search=True).order_by("id")
        if not options["force"]:
            queryset = queryset.filter(search_keywords=[])
        if options["limit"]:
            queryset = queryset[: options["limit"]]

        client = OpenAICompatibleClient()
        report = {"generated": [], "failed": [], "dry_run": options["dry_run"]}
        for decision in queryset:
            try:
                keywords = generate_keywords_for_decision(decision, client)
            except (OpenAIBackendError, ValueError, json.JSONDecodeError) as exc:
                report["failed"].append({"id": decision.id, "title": decision.title, "error": str(exc)})
                continue
            report["generated"].append({"id": decision.id, "title": decision.title, "keywords": keywords})
            if options["dry_run"]:
                continue
            decision.search_keywords = keywords
            decision.save(update_fields=["search_keywords", "updated_at"])
            decision.search_documents.filter(document_type="keywords").delete()
            add_search_doc(decision, "keywords", decision.title, keywords)
        self.stdout.write(json.dumps(report, indent=2, sort_keys=True))
        if report["failed"] and not report["generated"]:
            raise CommandError("Keyword generation failed for every selected decision.")
