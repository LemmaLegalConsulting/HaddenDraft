"""Automatable entry point for the managed legal-source publication pipeline."""
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.sources.models import ManagedSource
from apps.sources.publication import import_version, publish_version, retire_source, rollback_source


class Command(BaseCommand):
    help = "Import, publish, retire, or roll back an operator-maintained legal source."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=("import", "publish", "retire", "rollback"))
        parser.add_argument("slug")
        parser.add_argument("file", nargs="?")
        parser.add_argument("--kind", choices=[value for value, _label in ManagedSource.KIND_CHOICES])
        parser.add_argument("--title")
        parser.add_argument("--label", default="")
        parser.add_argument("--version", type=int)
        parser.add_argument("--publish", action="store_true")
        parser.add_argument("--username", help="Attribute the operation to this existing Django user.")
        parser.add_argument("--source-locator", default="")
        parser.add_argument("--source-system-id", default="")
        parser.add_argument("--source-etag", default="")

    def handle(self, *args, **options):
        actor = None
        if options["username"]:
            actor = get_user_model().objects.filter(username=options["username"]).first()
            if not actor:
                raise CommandError(f"Unknown user: {options['username']}")
        source = ManagedSource.objects.filter(slug=options["slug"]).first()
        if options["action"] == "import":
            if not options["file"] or not options["kind"] or not options["title"]:
                raise CommandError("import requires file, --kind, and --title")
            path = Path(options["file"]).expanduser()
            if not path.is_file():
                raise CommandError(f"Source file does not exist: {path}")
            source, _created = ManagedSource.objects.get_or_create(
                slug=options["slug"],
                defaults={
                    "kind": options["kind"], "title": options["title"], "created_by": actor,
                    "source_locator": options["source_locator"],
                    "source_system_id": options["source_system_id"],
                },
            )
            version, created = import_version(
                source=source, content=path.read_bytes(), filename=path.name,
                label=options["label"], actor=actor, source_etag=options["source_etag"],
                publish=options["publish"],
            )
            self.stdout.write(
                f"{source.slug} version {version.number}: {version.status} "
                f"({'created' if created else 'unchanged'})"
            )
            if version.status == "failed":
                raise CommandError(version.error)
            return
        if not source:
            raise CommandError(f"Unknown source: {options['slug']}")
        if options["action"] == "retire":
            retire_source(source, actor=actor)
            self.stdout.write(self.style.SUCCESS(f"Retired {source.slug}"))
            return
        version_number = options["version"]
        if options["action"] == "rollback" and not version_number:
            raise CommandError("rollback requires --version")
        version = (
            source.versions.filter(number=version_number).first()
            if version_number else source.versions.order_by("-number").first()
        )
        if not version:
            raise CommandError("No matching version exists.")
        if options["action"] == "rollback":
            rollback_source(source, version, actor=actor)
        else:
            publish_version(version, actor=actor)
        self.stdout.write(self.style.SUCCESS(f"Published {source.slug} version {version.number}"))
