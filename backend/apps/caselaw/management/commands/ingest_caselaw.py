import json
import tempfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.caselaw.importing import ingest_caselaw_directory
from apps.caselaw.storage import get_caselaw_raw_storage


class Command(BaseCommand):
    help = "Discover and ingest sidecar-based case-law PDFs into the local caselaw corpus."

    def add_arguments(self, parser):
        parser.add_argument("source_path", nargs="?")
        parser.add_argument(
            "--from-raw-storage",
            action="store_true",
            help=(
                "Ingest from raw/caselaw/ in the configured document storage instead of a "
                "local directory. Objects are staged to a temporary directory first, because "
                "ingestion hashes and parses real files."
            ),
        )
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
        if options["from_raw_storage"] == bool(options["source_path"]):
            raise CommandError("Give either a source_path or --from-raw-storage, not both or neither.")

        if options["from_raw_storage"]:
            with tempfile.TemporaryDirectory() as staging:
                staged = self._stage_raw_storage(Path(staging))
                if staged == 0:
                    self.stdout.write("Nothing to ingest: raw/caselaw/ is empty.")
                    return
                self._ingest(Path(staging), options)
            return

        source_path = Path(options["source_path"]).expanduser()
        if not source_path.exists() or not source_path.is_dir():
            raise CommandError(f"Import directory does not exist: {source_path}")
        self._ingest(source_path, options)

    def _stage_raw_storage(self, staging_dir):
        storage = get_caselaw_raw_storage()
        self.stdout.write(f"Staging raw/caselaw/ from {storage.backend_name} storage...")
        count = 0
        for key in storage.iter_keys():
            # Keys come from the store, not from us. A key containing ".." would
            # otherwise write outside the staging directory.
            target = (staging_dir / key).resolve()
            if staging_dir.resolve() not in target.parents:
                raise CommandError(f"Refusing to stage key outside the staging directory: {key}")
            storage.download_to(key, target)
            count += 1
        self.stdout.write(f"Staged {count} object(s).")
        return count

    def _ingest(self, source_path, options):
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
