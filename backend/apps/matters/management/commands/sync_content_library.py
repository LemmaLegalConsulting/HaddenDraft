from django.core.management.base import BaseCommand, CommandError

from apps.matters.triage import sync_triage_rubric_seeds


class Command(BaseCommand):
    help = "Seed file-backed legal content defaults into the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--update-triage-rubrics",
            action="store_true",
            help="Intentionally overwrite existing triage rubrics from their YAML files.",
        )

    def handle(self, *_args, **options):
        try:
            rubrics = sync_triage_rubric_seeds(update_existing=options["update_triage_rubrics"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        created = sum(created for _rubric, created in rubrics)
        updated = len(rubrics) - created if options["update_triage_rubrics"] else 0
        self.stdout.write(self.style.SUCCESS(f"Synced {len(rubrics)} triage rubric(s): {created} created, {updated} updated."))
