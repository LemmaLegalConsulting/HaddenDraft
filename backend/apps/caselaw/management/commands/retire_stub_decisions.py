"""Delete a citation-only stub once its citation has a full-opinion sibling.

A stub decision is a generated one-page placeholder -- a case name and a
citation, nothing else -- that predates CAP fetching. Once
``fetch_cap_opinions`` and ``enrich_caselaw_metadata`` have produced a real
decision for the same citation, the stub is not a second source of truth; it
is a strictly worse duplicate of a case the corpus already has in full. Left
alone, it shows up beside the real decision in every search and browse view.

Retirement is narrow on purpose, matched two ways at once so neither check has
to carry the whole judgment call on its own:

  - a full sibling exists: another decision whose citation normalizes to the
    same string (ignoring spacing, punctuation, and case) as this one, and
  - this decision looks like a stub: its first page holds less text than any
    real opinion in this corpus does.

A decision that fails either check is left alone. A short decision with no
fuller sibling might be a genuinely short opinion, not a stub, and a full
decision that happens to share a citation with something else is never the
one in the pair that gets removed.

This is not the fix for future imports creating stubs again -- the corpus
directory ``CASELAW_INGEST_DIR`` still holds the original stub bundles, and a
future deploy that re-runs that ingest path will recreate what this command
just removed. That is what makes running this after every caselaw ingest
step, not just once, the correct way to use it: it is a standing cleanup, not
a one-time migration.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.caselaw.cap import normalize_citation
from apps.caselaw.models import CaseLawDecision

STUB_TEXT_CHARS = 400


def _text_length(decision):
    page = decision.pages.first()
    return len(page.text) if page else 0


def stub_replacements(decisions):
    """(stub, fuller_sibling) pairs: a short decision superseded by a longer one
    sharing its citation.

    Grouping is by normalized citation rather than by ``source_sha256``: a stub
    and its CAP-fetched replacement are different files with different hashes,
    so hash equality is exactly the signal that does *not* apply here.
    """
    by_citation = {}
    for decision in decisions:
        key = normalize_citation(decision.citation_string)
        if not key:
            continue
        by_citation.setdefault(key, []).append(decision)

    pairs = []
    for group in by_citation.values():
        if len(group) < 2:
            continue
        scored = sorted(((decision, _text_length(decision)) for decision in group), key=lambda item: -item[1])
        fullest, fullest_length = scored[0]
        if fullest_length < STUB_TEXT_CHARS:
            # Every decision under this citation is stub-length; there is no
            # fuller sibling yet, so nothing here is a replacement target.
            continue
        for decision, length in scored[1:]:
            if length < STUB_TEXT_CHARS:
                pairs.append((decision, fullest))
    return pairs


class Command(BaseCommand):
    help = "Delete citation-only stub decisions that now have a full-opinion sibling."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report what would be removed without deleting.")

    def handle(self, *args, **options):
        decisions = list(CaseLawDecision.objects.all().prefetch_related("pages"))
        pairs = stub_replacements(decisions)

        self.stdout.write(f"Decisions considered: {len(decisions)}")
        self.stdout.write(f"Stubs with a full-text sibling: {len(pairs)}")
        for stub, fuller in pairs[:20]:
            self.stdout.write(
                f"  retire id={stub.id} ({_text_length(stub)} chars) "
                f"-> kept id={fuller.id} ({_text_length(fuller)} chars): {stub.citation_string}"
            )
        if len(pairs) > 20:
            self.stdout.write(f"  ... and {len(pairs) - 20} more")

        if options["dry_run"] or not pairs:
            if not pairs:
                self.stdout.write("Nothing to retire.")
            return

        with transaction.atomic():
            CaseLawDecision.objects.filter(id__in=[stub.id for stub, _fuller in pairs]).delete()
        self.stdout.write(f"Retired {len(pairs)} stub decision(s).")
