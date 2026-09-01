from django.core.management.base import BaseCommand, CommandError

from apps.matters.triage import sync_triage_rubric_seeds
from apps.rules.court_profiles import sync_court_profile_seeds
from apps.rules.legal_rules import sync_legal_rule_seeds
from apps.templates_app.content_library import sync_prepared_templates


class Command(BaseCommand):
    help = "Seed file-backed legal content defaults into the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--update-triage-rubrics",
            action="store_true",
            help="Intentionally overwrite existing triage rubrics from their YAML files.",
        )
        parser.add_argument(
            "--update-court-rules",
            action="store_true",
            help="Intentionally overwrite court profiles from their YAML files, except ones edited in admin.",
        )
        parser.add_argument(
            "--update-legal-rules",
            action="store_true",
            help="Intentionally overwrite legal rule profiles from their YAML files, except ones edited in admin.",
        )

    def handle(self, *_args, **options):
        try:
            rubrics = sync_triage_rubric_seeds(update_existing=options["update_triage_rubrics"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        created = sum(created for _rubric, created in rubrics)
        updated = len(rubrics) - created if options["update_triage_rubrics"] else 0
        self.stdout.write(self.style.SUCCESS(f"Synced {len(rubrics)} triage rubric(s): {created} created, {updated} updated."))
        try:
            courts = sync_court_profile_seeds(update_existing=options["update_court_rules"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        created_courts = sum(created for _profile, created in courts)
        unverified = sum(1 for profile, _created in courts if profile.verification != "verified")
        self.stdout.write(
            self.style.SUCCESS(
                f"Synced {len(courts)} court profile(s): {created_courts} created. "
                f"{unverified} still unverified; their findings report as warnings."
            )
        )
        try:
            legal_rules = sync_legal_rule_seeds(update_existing=options["update_legal_rules"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        created_rules = sum(created for _profile, created in legal_rules)
        unverified_rules = sum(1 for profile, _created in legal_rules if profile.verification != "verified")
        self.stdout.write(
            self.style.SUCCESS(
                f"Synced {len(legal_rules)} legal rule profile(s): {created_rules} created. "
                f"{unverified_rules} still unverified; their unmet elements report as warnings."
            )
        )
        templates = sync_prepared_templates()
        conflicts = sum(result["status"] == "conflict" for result in templates)
        self.stdout.write(
            self.style.SUCCESS(
                f"Indexed {len(templates) - conflicts} prepared document template(s); {conflicts} slug conflict(s) preserved."
            )
        )
