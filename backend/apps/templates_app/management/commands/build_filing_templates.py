from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.content_library import content_library_dir
from apps.templates_app.content_library import sync_prepared_templates
from apps.templates_app.filing_templates import FilingTemplateSpecError, build_all


class Command(BaseCommand):
    help = (
        "Generate court-filing template packages (motions, memoranda, replies) from "
        "content/filing-templates/*.yaml into document-templates/ and docx-snippets/."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--content-root",
            default="",
            help="Content provider to read specs from and write packages to; defaults to CONTENT_LIBRARY_DIR.",
        )
        parser.add_argument(
            "--check",
            action="store_true",
            help="Report packages that are out of date with their spec and exit non-zero, writing nothing.",
        )
        parser.add_argument("--no-sync", action="store_true", help="Do not update the template index after building.")

    def handle(self, *args, **options):
        root = Path(options["content_root"]) if options["content_root"] else content_library_dir()
        if options["check"]:
            import shutil
            import tempfile

            with tempfile.TemporaryDirectory() as scratch:
                scratch_root = Path(scratch)
                shutil.copytree(root / "filing-templates", scratch_root / "filing-templates")
                for subdir in ("document-templates", "docx-snippets"):
                    if (root / subdir).exists():
                        shutil.copytree(root / subdir, scratch_root / subdir)
                try:
                    results = build_all(scratch_root)
                except FilingTemplateSpecError as exc:
                    raise CommandError(str(exc)) from exc
            stale = [result["slug"] for result in results if result["written"]]
            if stale:
                raise CommandError(
                    "Out of date with their spec: " + ", ".join(stale) + ". Run manage.py build_filing_templates."
                )
            self.stdout.write(self.style.SUCCESS(f"{len(results)} filing template package(s) are current."))
            return

        try:
            results = build_all(root)
        except FilingTemplateSpecError as exc:
            raise CommandError(str(exc)) from exc
        for result in results:
            status = f"wrote {len(result['written'])} file(s)" if result["written"] else "unchanged"
            self.stdout.write(f"{result['slug']}: {status}")
        if not options["no_sync"]:
            sync_prepared_templates()
        self.stdout.write(self.style.SUCCESS(f"Built {len(results)} filing template package(s)."))
