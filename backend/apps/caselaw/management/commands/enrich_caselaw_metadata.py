"""Summarize staged case bundles the way the rest of the corpus was summarized.

The existing corpus was built in two passes: one model read the text and drafted
the metadata, a second model checked that draft against the text and corrected
it, and a marker file recorded that the second pass happened.  ``.verified.json``
means "a second model reviewed this", not "a lawyer approved this", and
ingestion treats a reviewed bundle as fit for search.

Bundles fetched from an official reporter arrive knowing things the old pipeline
had to guess: the title, the citation, the deciding court, the decision date.
Those are passed to both models as facts to repeat rather than fields to infer,
and are re-asserted afterwards, so a summarizer cannot talk the corpus out of a
date the reporter printed.

    python manage.py enrich_caselaw_metadata --dry-run
    python manage.py enrich_caselaw_metadata
    python manage.py ingest_caselaw --from-raw-storage
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.core.management.base import BaseCommand

from apps.ai.openai_client import OpenAIBackendError, OpenAICompatibleClient
from apps.ai.prompt_catalog import render_prompt
from apps.caselaw.storage import get_caselaw_raw_storage

EXTRACT_CHARS = 20000
VERIFY_CHARS = 15000
VERIFIED_MARKER = "Verified by {model}"

# Facts an official reporter supplies. The summarizers are told to repeat these,
# and they are written back afterwards, because a model that "corrects" a
# reporter's citation is wrong by construction.
AUTHORITATIVE_FIELDS = (
    "title",
    "short_title",
    "citation_string",
    "parallel_citations",
    "decision_date",
    "court",
    "jurisdiction",
    "docket_number",
    "external_source_id",
    "publication_status",
    "precedential_status",
    "is_unpublished",
)

# The analytical fields the pipeline exists to produce.
SCHEMA_FIELDS = (
    "normalized_title", "case_number", "court_division", "county", "judge", "magistrate",
    "parties", "party_roles", "entry_date", "filed_date", "hearing_date", "service_date",
    "authority_level", "court_level", "is_trial_court", "is_administrative", "is_persuasive_only",
    "case_type", "claim_type", "motion_type", "procedural_stage", "posture", "appeal_status",
    "tenant_landlord_role", "subsidy_program", "housing_type",
    "issues", "holdings", "rules_applied", "statutes_cited", "regulations_cited", "cases_cited",
    "key_facts", "outcome", "relief_granted", "relief_denied", "disposition",
    "treatment_status", "treatment_notes",
)

SCHEMA_HINT = json.dumps(
    {
        **{field: "" for field in SCHEMA_FIELDS if field not in {
            "parties", "party_roles", "issues", "holdings", "rules_applied",
            "statutes_cited", "regulations_cited", "cases_cited",
            "is_trial_court", "is_administrative", "is_persuasive_only",
        }},
        **{field: [] for field in (
            "parties", "party_roles", "issues", "holdings", "rules_applied",
            "statutes_cited", "regulations_cited", "cases_cited",
        )},
        **{field: False for field in ("is_trial_court", "is_administrative", "is_persuasive_only")},
    },
    indent=1,
)


def _json_object(response):
    text = (response or "").strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        text = text.split("\n", 1)[1] if "\n" in text else text
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("model did not return a JSON object")
    payload = json.loads(text[start:end + 1])
    if not isinstance(payload, dict):
        raise ValueError("model returned JSON that is not an object")
    return payload


def known_facts(sidecar):
    return {field: sidecar[field] for field in AUTHORITATIVE_FIELDS if sidecar.get(field) not in (None, "", [])}


def merge(sidecar, drafted):
    """Drafted analysis over the existing sidecar, with reporter facts restored."""
    merged = {**sidecar, **{key: value for key, value in drafted.items() if key in SCHEMA_FIELDS}}
    merged.update(known_facts(sidecar))
    return merged


class Command(BaseCommand):
    help = "Draft and then verify metadata for staged case bundles, as the rest of the corpus was built."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report what would run without calling a model.")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--workers", type=int, default=5, help="Parallel bundles. The original pipeline used 5 to stay under the rate limit.")
        parser.add_argument("--prefix", default="cap-", help="Only bundles whose name starts with this.")
        parser.add_argument("--reverify", action="store_true", help="Run again for bundles already carrying a marker.")

    def _bundles(self, storage, options):
        names = sorted(
            key[: -len(".pdf.txt")]
            for key in storage.iter_keys("")
            if key.endswith(".pdf.txt") and key.startswith(options["prefix"])
        )
        if not options["reverify"]:
            names = [name for name in names if not storage.exists(f"{name}.verified.json")]
        return names[: options["limit"]] if options["limit"] else names

    def _enrich(self, storage, name):
        text = storage.open(f"{name}.pdf.txt").read().decode("utf-8", "replace")
        sidecar = json.loads(storage.open(f"{name}.pdf.json").read().decode("utf-8", "replace"))
        facts = json.dumps(known_facts(sidecar), ensure_ascii=False, indent=1)
        client = OpenAICompatibleClient()

        drafted = render_prompt(
            "caselaw.metadata_extract",
            known_facts=facts,
            schema=SCHEMA_HINT,
            text=text[:EXTRACT_CHARS],
        )
        draft = _json_object(client.complete(
            system=drafted.system,
            user=drafted.user,
            temperature=0,
            model=drafted.default_model,
            reasoning_level=drafted.default_reasoning_level,
        ))

        checked = render_prompt(
            "caselaw.metadata_verify",
            known_facts=facts,
            schema=SCHEMA_HINT,
            text=text[:VERIFY_CHARS],
            draft=json.dumps(draft, ensure_ascii=False, indent=1),
        )
        verified = _json_object(client.complete(
            system=checked.system,
            user=checked.user,
            temperature=0,
            model=checked.default_model,
            reasoning_level=checked.default_reasoning_level,
        ))

        merged = merge(sidecar, verified)
        merged["metadata_review"] = {
            "drafted_by": drafted.default_model,
            "verified_by": checked.default_model,
            "authoritative_fields_from": sidecar.get("source_url") or sidecar.get("metadata_source", ""),
        }
        storage.put_bytes(
            content=json.dumps(merged, ensure_ascii=False, indent=1).encode("utf-8"),
            key=f"{name}.pdf.json",
            content_type="application/json",
        )
        storage.put_bytes(
            content=VERIFIED_MARKER.format(model=checked.default_model).encode("utf-8"),
            key=f"{name}.verified.json",
            content_type="text/plain",
        )
        return merged

    def handle(self, *args, **options):
        storage = get_caselaw_raw_storage()
        names = self._bundles(storage, options)
        self.stdout.write(f"Bundles to summarize: {len(names)}")
        if options["dry_run"] or not names:
            for name in names[:10]:
                self.stdout.write(f"  {name}")
            return

        done = failed = 0
        errors = []
        with ThreadPoolExecutor(max_workers=max(1, options["workers"])) as pool:
            futures = {pool.submit(self._enrich, storage, name): name for name in names}
            for index, future in enumerate(as_completed(futures), start=1):
                name = futures[future]
                try:
                    future.result()
                    done += 1
                except (OpenAIBackendError, ValueError, json.JSONDecodeError, OSError) as error:
                    failed += 1
                    errors.append((name, str(error)[:140]))
                if index % 25 == 0 or index == len(names):
                    self.stdout.write(f"  {index}/{len(names)} ({done} summarized, {failed} failed)")

        self.stdout.write(f"Summarized and marked verified: {done}")
        if errors:
            self.stdout.write(f"Failed: {failed}; first 10:")
            for name, error in errors[:10]:
                self.stdout.write(f"  {name}: {error}")
            self.stdout.write("Re-running processes only what has no marker yet, so failures can be retried.")
        self.stdout.write("Run `manage.py ingest_caselaw --from-raw-storage` to import them.")
