"""Fetch the opinions behind citation-only records from the Caselaw Access Project.

Part of this corpus is citation stubs: a generated page carrying a case name and
a reporter citation, with the opinion never obtained. The citation still earns
its place — it lets the tool confirm a cited case exists — but a stub cannot be
read, quoted, or checked.

This stages real bundles into the raw storage area, in the naming
``ingest_caselaw`` already reads. Nothing is imported here and nothing existing
is modified: staging and ingestion stay separate steps so an operator can look
at what arrived before it reaches the database.

    python manage.py fetch_cap_opinions --dry-run
    python manage.py fetch_cap_opinions
    python manage.py ingest_caselaw --from-raw-storage
"""

import json
import re

from django.core.management.base import BaseCommand

from apps.caselaw.cap import CapClient, CapError, parse_citation
from apps.caselaw.models import CaseLawDecision
from apps.caselaw.storage import get_caselaw_raw_storage

# Below this, a document is a citation stub rather than an opinion: the longest
# stub in this corpus is a caption plus a citation line.
STUB_TEXT_CHARS = 400


def citation_for(decision):
    """The citation to look up, from the record or from its own stub page."""
    if decision.citation_string:
        return decision.citation_string
    page = decision.pages.first()
    match = re.search(r"Citation:\s*(.+)", page.text) if page else None
    return match.group(1).strip() if match else ""


def stub_decisions(queryset):
    """Records whose document is a citation without an opinion behind it."""
    for decision in queryset.prefetch_related("pages"):
        page = decision.pages.first()
        if page and len(page.text) >= STUB_TEXT_CHARS:
            continue
        if citation_for(decision):
            yield decision


def bundle_stem(resolved):
    return f"cap-{resolved['reporter']}-{resolved['volume']}-{resolved['file_name']}"


class Command(BaseCommand):
    help = "Stage opinions for citation-only records from the Caselaw Access Project bulk files."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Resolve citations without writing anything.")
        parser.add_argument("--limit", type=int, default=0, help="Only process this many records.")
        parser.add_argument("--citation", action="append", default=[], help="Look up a citation directly, ignoring the database.")
        parser.add_argument(
            "--citations-file",
            help="Newline-separated citations to look up instead of reading the database.",
        )
        parser.add_argument("--base-url", default=None, help="Override the CAP static file base URL.")
        parser.add_argument(
            "--refetch",
            action="store_true",
            help="Stage again even where a bundle for that case is already present.",
        )

    def _targets(self, options):
        """(citation, decision) pairs to resolve, from wherever the operator pointed."""
        if options["citation"]:
            return [(citation, None) for citation in options["citation"]]
        if options["citations_file"]:
            with open(options["citations_file"], encoding="utf-8") as handle:
                return [(line.strip(), None) for line in handle if line.strip()]
        return [(citation_for(decision), decision) for decision in stub_decisions(CaseLawDecision.objects.all())]

    def handle(self, *args, **options):
        client = CapClient(**({"base": options["base_url"]} if options["base_url"] else {}))
        storage = get_caselaw_raw_storage()
        targets = self._targets(options)
        if options["limit"]:
            targets = targets[: options["limit"]]

        counts = {}
        staged = 0
        unresolved = []
        for citation, decision in targets:
            if not parse_citation(citation):
                counts["unparsed_citation"] = counts.get("unparsed_citation", 0) + 1
                unresolved.append((citation, "unparsed_citation"))
                continue
            try:
                resolved = client.resolve(citation)
            except CapError as error:
                counts["fetch_failed"] = counts.get("fetch_failed", 0) + 1
                unresolved.append((citation, str(error)[:120]))
                continue

            counts[resolved["status"]] = counts.get(resolved["status"], 0) + 1
            if resolved["status"] != "found":
                unresolved.append((citation, resolved["status"]))
                continue
            if options["dry_run"]:
                continue

            stem = bundle_stem(resolved)
            if storage.exists(f"{stem}.pdf.txt") and not options["refetch"]:
                counts["already_staged"] = counts.get("already_staged", 0) + 1
                continue

            metadata = dict(resolved["metadata"])
            if decision is not None:
                # Say which citation-only record this answers, so the stub can be
                # retired deliberately rather than left as a silent duplicate.
                metadata["replaces_source_sha256"] = decision.source_sha256
                metadata["replaces_decision_title"] = decision.title
            storage.put_bytes(
                content=resolved["text"].encode("utf-8"),
                key=f"{stem}.pdf.txt",
                content_type="text/plain",
            )
            storage.put_bytes(
                content=json.dumps(metadata, ensure_ascii=False, indent=1).encode("utf-8"),
                key=f"{stem}.pdf.json",
                content_type="application/json",
            )
            pdf = None
            try:
                pdf = client.case_pdf(resolved["reporter"], resolved["volume"], resolved["file_name"])
            except CapError:
                pdf = None
            if pdf:
                storage.put_bytes(content=pdf, key=f"{stem}.pdf", content_type="application/pdf")
            else:
                # The text is what makes the case readable; a missing scan is
                # worth recording but is not a reason to drop the opinion.
                counts["staged_without_pdf"] = counts.get("staged_without_pdf", 0) + 1
            staged += 1

        self.stdout.write(f"Citations considered: {len(targets)}")
        for status, count in sorted(counts.items(), key=lambda item: -item[1]):
            self.stdout.write(f"  {status:24s} {count}")
        if not options["dry_run"]:
            self.stdout.write(f"Bundles staged in raw storage: {staged}")
            self.stdout.write("Run `manage.py ingest_caselaw --from-raw-storage` to import them.")
            # These bundles carry no .verified.json, because nobody has verified
            # them: they are what CAP published, not what a person checked. So
            # they import with approved_for_search off and stay out of research
            # until someone says otherwise. That is the honest default, but it
            # has to be said out loud or the cases look like they never arrived.
            self.stdout.write(
                "Imported cases will have approved_for_search off, because no one has reviewed "
                "them. Approve them at Case law > Case law decisions in admin, or ingest with "
                "CASELAW_IMPORT_APPROVE_UNVERIFIED_FOR_SEARCH=true if that is the policy you want."
            )
        if unresolved:
            self.stdout.write("")
            self.stdout.write(f"Unresolved ({len(unresolved)}); first 10:")
            for citation, reason in unresolved[:10]:
                self.stdout.write(f"  {citation:32s} {reason}")
            self.stdout.write(
                "A citation CAP does not publish stays a citation-only record. That still "
                "confirms the case exists; it just cannot be read here."
            )
