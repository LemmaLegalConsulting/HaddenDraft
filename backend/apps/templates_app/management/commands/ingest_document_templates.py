from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.templates_app.content_library import sync_prepared_templates
from apps.templates_app.ingestion import ingest_directory, ingest_docx


class Command(BaseCommand):
    help = "Convert original DOCX files into formatting-preserving Jinja2 template packages."

    def add_arguments(self, parser):
        parser.add_argument("paths", nargs="*", help="DOCX files or directories; defaults to content/original_templates.")
        parser.add_argument("--force", action="store_true", help="Regenerate packages even when the source checksum is unchanged.")
        parser.add_argument("--no-sync", action="store_true", help="Do not update the database index after conversion.")

    def handle(self, *args, **options):
        content_root = Path(settings.CONTENT_LIBRARY_DIR)
        prepared_root = content_root / "document-templates"
        snippets_root = content_root / "docx-snippets"
        requested = [Path(value) for value in options["paths"]] or [content_root / "original_templates"]
        manifests = []
        for path in requested:
            if not path.is_absolute():
                path = Path.cwd() / path
            if not path.exists():
                raise CommandError(f"Input does not exist: {path}")
            if path.is_dir():
                manifests.extend(ingest_directory(path, prepared_root, snippets_root, force=options["force"]))
            elif path.suffix.lower() == ".docx":
                manifests.append(ingest_docx(path, prepared_root, snippets_root, force=options["force"]))
            else:
                self.stderr.write(f"Skipping unsupported template source: {path}")

        if not options["no_sync"]:
            sync_prepared_templates()
        self.stdout.write(self.style.SUCCESS(f"Prepared {len(set(manifests))} DOCX template package(s)."))
