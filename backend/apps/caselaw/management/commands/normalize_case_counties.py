"""Bring already-imported decisions onto the shared county vocabulary.

Ingestion writes the canonical name, so material imported from now on needs
nothing. This is for the corpus that arrived before the vocabulary existed, in
which the same county is spelled two ways and a reader who narrows to one of
them is shown half the cases and told that is all of them.

What does not match the vocabulary is left exactly as it is and reported. A
corpus reaches here holding "Miami-Dade County" and "Durham County, North
Carolina", and those are not Ohio counties with untidy spelling -- they are
out-of-state decisions, and rewriting one to the nearest Ohio name would file
it on the wrong shelf. An unrecognized value is either that or a gap in
`content/jurisdictions/ohio-counties.yaml`; both want a person's eye, so both
are printed rather than quietly skipped.

    manage.py normalize_case_counties --report
    manage.py normalize_case_counties --dry-run
    manage.py normalize_case_counties
"""

from __future__ import annotations

from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.caselaw.models import CaseLawDecision
from apps.core.jurisdictions import canonical_county, is_known_county, vocabulary_status


class Command(BaseCommand):
    help = "Rewrite stored county values to the canonical spelling in the shared vocabulary."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would change and write nothing.")
        parser.add_argument(
            "--report", action="store_true",
            help="Only list the stored spellings and which of them the vocabulary does not hold.",
        )

    def handle(self, *args, **options):
        status = vocabulary_status()
        if not status["available"]:
            raise SystemExit(f"No county vocabulary was found at {status['path']}.")
        self.stdout.write(f"Vocabulary: {status['countyCount']} counties, {status['spellingCount']} spellings.")

        stored = Counter(
            value for value in CaseLawDecision.objects.values_list("county", flat=True) if (value or "").strip()
        )
        unknown = {value: count for value, count in stored.items() if not is_known_county(value)}
        changes = {
            value: canonical_county(value)
            for value in stored
            if is_known_county(value) and canonical_county(value) != value
        }

        if unknown:
            self.stdout.write(self.style.WARNING(
                f"\n{len(unknown)} spelling(s) are not in the vocabulary and are left unchanged:"
            ))
            for value, count in sorted(unknown.items(), key=lambda item: (-item[1], item[0])):
                self.stdout.write(f"  {count:5}  {value!r}")
            self.stdout.write(
                "  Add a county or an alias to content/jurisdictions/ohio-counties.yaml if one of these "
                "is an Ohio county. Leave it if the decision is from another state."
            )

        if options["report"]:
            self.stdout.write(f"\n{len(stored)} distinct spelling(s) across the corpus; {len(changes)} would change.")
            for value, canonical in sorted(changes.items()):
                self.stdout.write(f"  {stored[value]:5}  {value!r} -> {canonical!r}")
            return

        if not changes:
            self.stdout.write(self.style.SUCCESS("\nEvery recognized county is already stored canonically."))
            return

        total = sum(stored[value] for value in changes)
        for value, canonical in sorted(changes.items()):
            self.stdout.write(f"  {stored[value]:5}  {value!r} -> {canonical!r}")
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(
                f"\nDry run: {total} decision(s) across {len(changes)} spelling(s) would be rewritten."
            ))
            return

        with transaction.atomic():
            updated = sum(
                CaseLawDecision.objects.filter(county=value).update(county=canonical)
                for value, canonical in changes.items()
            )
        self.stdout.write(self.style.SUCCESS(
            f"\nRewrote the county on {updated} decision(s) across {len(changes)} spelling(s)."
        ))
