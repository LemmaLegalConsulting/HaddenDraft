from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.content_library import content_library_dir, organization_content_library_dir
from apps.templates_app.advice_letter_completions import (
    COMPLETIONS,
    DERIVED_SECTIONS,
    MERGE_REPAIRS,
    RETIRED_SECTIONS,
)
from apps.templates_app.advice_letter_hints import load_selection_hints, seed_selection_hints
from apps.templates_app.advice_letter_library import ADVICE_LETTER_DIR, sync_advice_letters
from apps.templates_app.advice_letters import build_catalog


class Command(BaseCommand):
    help = (
        "Prepare the client advice-letter catalog from the maintained Model Letter, "
        "sub-sections, and spreadsheet."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "source",
            nargs="?",
            default="",
            help="Folder holding Client Letters.xlsx, Model Letter.docx, and Letter Sub-Sections/.",
        )
        parser.add_argument(
            "--public",
            action="store_true",
            help="Write to the public content library instead of the private organization library.",
        )
        parser.add_argument("--no-sync", action="store_true", help="Do not index the result.")
        parser.add_argument(
            "--reseed-hints",
            action="store_true",
            help="Overwrite selection-hints.yaml with the built-in defaults.",
        )

    def handle(self, *args, **options):
        root = content_library_dir() if options["public"] else organization_content_library_dir()
        output_root = root / ADVICE_LETTER_DIR

        source = Path(options["source"]).expanduser() if options["source"] else output_root / "source"
        if not source.is_dir():
            raise CommandError(f"Advice-letter source folder does not exist: {source}")

        seed_selection_hints(output_root, force=options["reseed_hints"])
        hints = load_selection_hints(output_root)

        manifest_path = build_catalog(
            source,
            output_root,
            completions=COMPLETIONS,
            hints=hints,
            repairs=MERGE_REPAIRS,
            derived=DERIVED_SECTIONS,
            retired=RETIRED_SECTIONS,
        )

        import yaml

        data = yaml.safe_load(manifest_path.read_text())
        counts = {}
        for row in data["sections"]:
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        for status in sorted(counts):
            self.stdout.write(f"  {status:13s} {counts[status]}")

        if not options["no_sync"]:
            sync_advice_letters()
        self.stdout.write(
            self.style.SUCCESS(f"Prepared {len(data['sections'])} advice-letter section(s).")
        )
