from pathlib import Path

import yaml
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from apps.core.content_library import content_library_dir, organization_content_library_dir
from apps.templates_app.letterhead_library import LETTERHEAD_DIR, sync_letterheads
from apps.templates_app.letterheads import prepare_letterhead


class Command(BaseCommand):
    help = (
        "Convert one advocate's Word letterhead into an organization-wide template "
        "whose contact block is filled from the author's profile."
    )

    def add_arguments(self, parser):
        parser.add_argument("source", help="A .docx/.dotx letterhead to parameterize.")
        parser.add_argument("--slug", default="", help="Content-library slug; defaults to the file stem.")
        parser.add_argument("--title", default="", help="Human-readable name shown in admin.")
        parser.add_argument("--organization", default="", help="Whose letterhead this is.")
        parser.add_argument(
            "--public",
            action="store_true",
            help="Write to the public content library instead of the private organization library.",
        )
        parser.add_argument(
            "--placeholder",
            action="store_true",
            help="Mark as the neutral stand-in shipped for fresh installs.",
        )
        parser.add_argument("--default", action="store_true", help="Use this letterhead unless another matches.")
        parser.add_argument("--no-sync", action="store_true", help="Do not index the result afterwards.")

    def handle(self, *args, **options):
        source = Path(options["source"]).expanduser()
        if not source.is_file():
            raise CommandError(f"Letterhead source does not exist: {source}")
        if source.suffix.lower() not in {".docx", ".dotx"}:
            raise CommandError(f"Unsupported letterhead format: {source.suffix}")

        slug = options["slug"] or slugify(source.stem) or "letterhead"
        root = content_library_dir() if options["public"] else organization_content_library_dir()
        package = root / LETTERHEAD_DIR / slug
        output = package / "letterhead.docx"

        report = prepare_letterhead(source, output)

        manifest = {
            "schema_version": 1,
            "slug": slug,
            "title": options["title"] or source.stem,
            "organization": options["organization"],
            "description": (
                "Organization letterhead. The advocate contact block is filled from "
                "the author's profile at render time."
            ),
            "docx": "letterhead.docx",
            "default": bool(options["default"]),
            "placeholder": bool(options["placeholder"]),
            "active": True,
            "variables": report.variables,
            "prepared_from": source.name,
        }
        (package / "manifest.yaml").write_text(
            yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True)
        )

        for line in report.replaced:
            self.stdout.write(f"  replaced {line}")
        for warning in report.warnings:
            self.stderr.write(self.style.WARNING(f"  {warning}"))

        if not options["no_sync"]:
            sync_letterheads()
        self.stdout.write(self.style.SUCCESS(f"Prepared letterhead package at {package}"))
