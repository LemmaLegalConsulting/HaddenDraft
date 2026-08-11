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

    Returns ``(payload, artifact, reason)``. The reason distinguishes failures
    that look identical in a total but are not the same problem at all: no
    artifact row, a key the store cannot open, content that is not JSON, and a
    sidecar that is perfectly readable but carries no dates. Reporting those as
    one number is what made a production run of this command unreadable.

    Every artifact row of each type is tried, not just the first: a corpus that
    has been re-ingested can carry more than one row per type, and giving up on
    the first unreadable one hides a readable sibling.
    """
    reason = "no_artifact"
    for artifact_type in METADATA_ARTIFACTS:
        for artifact in decision.artifacts.filter(artifact_type=artifact_type):
            try:
                raw = storage.open(artifact.storage_key).read()
            except (OSError, ValueError):
                reason = "unreadable_key"
                continue
            try:
                payload = json.loads(raw.decode("utf-8", "replace"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                # The verified sidecar is a reviewer's note rather than metadata
                # in most of this corpus, so this is expected, not a failure.
                reason = "not_json" if reason == "no_artifact" else reason
                continue
            if isinstance(payload, dict) and isinstance(payload.get("metadata"), dict):
                payload = {**payload["metadata"], **{k: v for k, v in payload.items() if k != "metadata"}}
            if not isinstance(payload, dict):
                reason = "not_an_object"
                continue
            if any(payload.get(field) for field in PROVENANCE_FIELDS):
                return payload, artifact, "ok"
            reason = "sidecar_has_no_dates"
    return None, None, reason


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

        counts = {"scanned": 0, "dated": 0, "skipped_existing": 0}
        reasons = {}
        examples = []
        corroborated = 0
        provenance_rows = 0

        for decision in decisions:
            counts["scanned"] += 1
            metadata, artifact, reason = metadata_for(decision, storage)
            if not metadata:
                reasons[reason] = reasons.get(reason, 0) + 1
                if len(examples) < 10:
                    keys = list(decision.artifacts.values_list("artifact_type", "storage_key"))
                    examples.append((decision.id, reason, keys[:2]))
                continue

            updates = {}
            skipped_as_existing = False
            unparsable = False
            for field in PROVENANCE_FIELDS:
                raw = as_text(metadata_value(metadata, field))
                if not raw:
                    continue
                value = as_date(raw)
                if getattr(decision, field) and not options["overwrite"]:
                    counts["skipped_existing"] += 1
                    skipped_as_existing = True
                    continue
                if not value:
                    # A non-empty field the sidecar carried that as_date could
                    # not read, distinct from a decision that is simply already
                    # dated -- the two look identical as an empty `updates`.
                    unparsable = True
                    continue
                updates[field] = value
            if not updates:
                if skipped_as_existing and not unparsable:
                    label = "already_dated"
                elif unparsable:
                    label = "unparsable_dates"
                else:
                    label = "sidecar_has_no_dates"
                reasons[label] = reasons.get(label, 0) + 1
                if label != "already_dated" and len(examples) < 10:
                    raw_fields = {f: metadata.get(f) for f in PROVENANCE_FIELDS if metadata.get(f)}
                    examples.append((decision.id, label, raw_fields))
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
        self.stdout.write(f"  left alone (had dates): {counts['skipped_existing']}")
        for reason, count in sorted(reasons.items(), key=lambda item: -item[1]):
            self.stdout.write(f"  {reason:24s}{count}")
        if examples and counts["dated"] == 0 and counts["skipped_existing"] == 0:
            # A run that dated nothing AND found nothing already dated has to
            # say why, per decision -- that combination means every decision
            # hit a real failure. Aggregate counters alone cannot be diagnosed
            # from a deployment log.
            self.stdout.write("")
            self.stdout.write("Nothing was dated. First few, with what was found:")
            for decision_id, reason, detail in examples:
                self.stdout.write(f"  decision {decision_id}: {reason} {detail}")
        if not options["dry_run"]:
            self.stdout.write(f"Provenance rows written:  {provenance_rows}")
            share = f" ({corroborated / provenance_rows:.0%})" if provenance_rows else ""
            self.stdout.write(
                f"  corroborated in OCR text: {corroborated}{share}"
            )
            self.stdout.write(
                "A date that is not corroborated is not wrong: it means the document does not "
                "print it in a form the scan preserved."
            )
