from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.core.legalserver_profile import apply_legalserver_user_to_profile
from apps.core.views import profile_for_user
from apps.sources.connectors.legalserver import LegalServerClient, LegalServerError
from apps.sources.models import UserSourceIdentity


class Command(BaseCommand):
    help = (
        "Fill author profiles (letterhead name, title, phone, fax, email, office, "
        "bar number) from each advocate's LegalServer user record."
    )

    def add_arguments(self, parser):
        parser.add_argument("--username", default="", help="Only sync this Django user.")
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Replace values already set on the profile instead of only filling blanks.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Report changes without saving.")

    def handle(self, *args, **options):
        client = LegalServerClient()
        if not client.configured:
            self.stderr.write(
                self.style.WARNING(
                    "LegalServer is not configured; set LEGALSERVER_BASE_URL and credentials."
                )
            )
            return

        users = get_user_model().objects.all()
        if options["username"]:
            users = users.filter(username=options["username"])

        synced = skipped = 0
        for user in users:
            identifier = UserSourceIdentity.identifier_for(user, "legalserver") or (
                user.email or user.get_username()
            )
            if not identifier:
                skipped += 1
                continue
            try:
                payload = client.find_user(identifier)
            except LegalServerError as error:
                self.stderr.write(f"  {user.get_username()}: LegalServer lookup failed: {error}")
                skipped += 1
                continue
            if not payload:
                self.stdout.write(f"  {user.get_username()}: no LegalServer user matched {identifier}")
                skipped += 1
                continue

            profile = profile_for_user(user)
            changed = apply_legalserver_user_to_profile(
                profile, payload, overwrite=options["overwrite"]
            )
            if not changed:
                self.stdout.write(f"  {user.get_username()}: already current")
                continue
            if not options["dry_run"]:
                profile.save()
            self.stdout.write(
                f"  {user.get_username()}: {'would set' if options['dry_run'] else 'set'} "
                f"{', '.join(changed)}"
            )
            synced += 1

        self.stdout.write(
            self.style.SUCCESS(f"Synced {synced} author profile(s); skipped {skipped}.")
        )
