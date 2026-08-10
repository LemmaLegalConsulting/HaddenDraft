"""Fill in decision dates that an earlier import dropped, and say where they came from.

``as_date`` was a stub that answered None for every value, so every date field
in the corpus imported empty and the absence looked like documents that had no
dates. The dates were in the metadata sidecars the whole time.

Re-ingesting the corpus would fix it, but re-ingestion needs the whole artifact
bundle staged and rewrites every decision. This reads the metadata artifact each
decision already points at, sets only the date fields, and records where each
date came from — corroborated against the decision's own OCR text.
"""

import json

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.caselaw.dates import PROVENANCE_FIELDS, record_date_provenance
from apps.caselaw.importing import as_date, as_text, metadata_value
from apps.caselaw.models import CaseLawDecision
from apps.caselaw.storage import get_caselaw_storage

METADATA_ARTIFACTS = ("verified_metadata_json", "metadata_json")


def metadata_for(decision, storage):
    """The decision's metadata sidecar, preferring the verified one.

    A verified sidecar that holds only a reviewer's note rather than metadata
    falls back to the unverified one, exactly as ingestion does.
    """
    for artifact_type in METADATA_ARTIFACTS:
        artifact = decision.artifacts.filter(artifact_type=artifact_type).first()
        if not artifact:
            continue
        try:
            raw = storage.open(artifact.storage_key).read()
        except (OSError, ValueError):
            continue
        try:
            payload = json.loads(raw.decode("utf-8", "replace"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(payload, dict) and isinstance(payload.get("metadata"), dict):
            payload = {**payload["metadata"], **{k: v for k, v in payload.items() if k != "metadata"}}
        if isinstance(payload, dict) and any(payload.get(field) for field in PROVENANCE_FIELDS):
            return payload, artifact
    return None, None


class Command(BaseCommand):
    help = "Backfill decision dates from metadata sidecars, with provenance against the OCR text."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report what would change without writing.")
        parser.add_argument("--limit", type=int, default=0, help="Only process this many decisions.")
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Replace dates already set. Off by default so a corrected date is not undone by a re-run.",
        )

    def handle(self, *args, **options):
        storage = get_caselaw_storage()
        decisions = CaseLawDecision.objects.all().prefetch_related("artifacts", "pages")
        if options["limit"]:
            decisions = decisions[: options["limit"]]

        counts = {"scanned": 0, "no_sidecar": 0, "no_dates": 0, "dated": 0, "skipped_existing": 0}
        corroborated = 0
        provenance_rows = 0

        for decision in decisions:
            counts["scanned"] += 1
            metadata, artifact = metadata_for(decision, storage)
            if not metadata:
                counts["no_sidecar"] += 1
                continue

            updates = {}
            for field in PROVENANCE_FIELDS:
                value = as_date(as_text(metadata_value(metadata, field)))
                if not value:
                    continue
                if getattr(decision, field) and not options["overwrite"]:
                    counts["skipped_existing"] += 1
                    continue
                updates[field] = value
            if not updates:
                counts["no_dates"] += 1
                continue

            page = decision.pages.first()
            text = page.text if page else ""
            if options["dry_run"]:
                counts["dated"] += 1
                continue

            with transaction.atomic():
                for field, value in updates.items():
                    setattr(decision, field, value)
                decision.save(update_fields=[*updates, "updated_at"])
                rows = record_date_provenance(
                    decision,
                    metadata,
                    source_key=artifact.storage_key if artifact else "",
                    source_sha256=artifact.sha256 if artifact else "",
                    text=text,
                )
            provenance_rows += len(rows)
            corroborated += sum(1 for row in rows if row.corroborated)
            counts["dated"] += 1

        self.stdout.write(f"Decisions scanned:        {counts['scanned']}")
        self.stdout.write(f"  dated from sidecar:     {counts['dated']}")
        self.stdout.write(f"  no readable sidecar:    {counts['no_sidecar']}")
        self.stdout.write(f"  sidecar carried none:   {counts['no_dates']}")
        self.stdout.write(f"  left alone (had dates): {counts['skipped_existing']}")
        if not options["dry_run"]:
            self.stdout.write(f"Provenance rows written:  {provenance_rows}")
            share = f" ({corroborated / provenance_rows:.0%})" if provenance_rows else ""
            self.stdout.write(
                f"  corroborated in OCR text: {corroborated}{share}"
            )
            self.stdout.write(
                "A date that is not corroborated is not wrong: this corpus holds no readable "
                "text for many scans. It means the document cannot confirm it."
            )
