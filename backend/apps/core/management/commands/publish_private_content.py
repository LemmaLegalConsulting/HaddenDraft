"""Publish private organization content from the raw area to the published area.

Private templates, letterheads, and advice-letter sources are side-loaded rather
than committed, and an operator uploads them into ``raw/private-content/``. This
command is the moment those uploads become visible to the application: it copies
them into ``published/private-content/``, which is what
``ORGANIZATION_CONTENT_LIBRARY_DIR`` points at in a deployed environment.

Separating the two is what makes a slow upload safe. A partially-uploaded
letterhead set sitting in ``raw/`` cannot be picked up by a running replica, and
the content library only ever sees a set that was published in one deliberate
step.
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.core.storage import PUBLISHED, RAW, copy_area, get_document_storage


class Command(BaseCommand):
    help = "Copy private organization content from the raw storage area to the published area."

    def add_arguments(self, parser):
        parser.add_argument(
            "--prefix",
            default=None,
            help="Key prefix within each area. Defaults to PRIVATE_CONTENT_STORAGE_PREFIX.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Re-copy objects that already exist in the published area.",
        )
        parser.add_argument(
            "--verbose-keys",
            action="store_true",
            help="Print every key as it is copied.",
        )

    def handle(self, *args, **options):
        prefix = (options["prefix"] or settings.PRIVATE_CONTENT_STORAGE_PREFIX).strip("/")
        raw = get_document_storage(RAW)
        published = get_document_storage(PUBLISHED)

        self.stdout.write(f"Publishing {prefix}/ from {RAW} to {PUBLISHED} ({raw.backend_name})")

        progress = (lambda key: self.stdout.write(f"  {key}")) if options["verbose_keys"] else None
        copied, skipped = copy_area(
            raw,
            published,
            prefix=prefix,
            skip_existing=not options["overwrite"],
            progress=progress,
        )

        # Not an error: an empty raw area is the normal state for a deployment
        # whose private content still ships in the image. Say so plainly rather
        # than reporting success over a no-op.
        if copied == 0 and skipped == 0:
            self.stdout.write(f"Nothing to publish: {RAW}/{prefix}/ is empty.")
        else:
            self.stdout.write(f"Published {copied} object(s), skipped {skipped} already present.")
