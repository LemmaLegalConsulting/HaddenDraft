from django.core.management.base import BaseCommand, CommandError

from apps.sources.connectors.sharepoint import SharePointError
from apps.sources.models import ManagedSource
from apps.sources.sharepoint_import import import_sharepoint_source


class Command(BaseCommand):
    help = "Stage an approved SharePoint managed source for publication review."

    def add_arguments(self, parser):
        parser.add_argument("slug", help="Existing managed source with an approved SharePoint source_system_id")

    def handle(self, *args, **options):
        try:
            source = ManagedSource.objects.get(slug=options["slug"])
            version, created = import_sharepoint_source(source)
        except (ManagedSource.DoesNotExist, SharePointError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        if version.status == "failed":
            raise CommandError(version.error)
        self.stdout.write(f"Version {version.number}: {version.status} ({'created' if created else 'unchanged'}). Review and publish in managed sources.")
