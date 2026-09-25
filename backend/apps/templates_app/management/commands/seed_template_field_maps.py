from django.core.management.base import BaseCommand
from apps.templates_app.fill_mappings import seed_mappings


class Command(BaseCommand):
    help = "Seed missing template-to-LegalServer mappings without replacing admin edits."

    def handle(self, *args, **options):
        self.stdout.write(f"Added {seed_mappings()} template field mappings.")
