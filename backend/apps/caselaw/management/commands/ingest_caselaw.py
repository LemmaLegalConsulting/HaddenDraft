import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.caselaw.importing import ingest_caselaw_directory


class Command(BaseCommand):
    help = "Discover and ingest sidecar-based case-law PDFs into the local caselaw corpus."

    def add_arguments(self, parser):
        parser.add_argument("source_path")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--require-verified", action="store_true")
        parser.add_argument("--allow-missing-pdf", action="store_true")
        parser.add_argument("--allow-missing-metadata", action="store_true")
        parser.add_argument("--allow-missing-text", action="store_true")
        parser.add_argument("--limit", type=int)
        parser.add_argument("--storage-prefix", default="caselaw")
        parser.add_argument("--report-json")

    def handle(self, *args, **options):
        source_path = Path(options["source_path"]).expanduser()
        if not source_path.exists() or not source_path.is_dir():
            raise CommandError(f"Import directory does not exist: {source_path}")

        report = ingest_caselaw_directory(
            source_path,
            dry_run=options["dry_run"],
            force=options["force"],
            require_verified=True if options["require_verified"] else None,
            allow_missing_pdf=options["allow_missing_pdf"],
            allow_missing_metadata=options["allow_missing_metadata"],
            allow_missing_text=options["allow_missing_text"],
            limit=options["limit"],
            storage_prefix=options["storage_prefix"],
        )
        output = json.dumps(report, indent=2, sort_keys=True)
        if options["report_json"]:
            Path(options["report_json"]).write_text(output + "\n", encoding="utf-8")
        self.stdout.write(output)
