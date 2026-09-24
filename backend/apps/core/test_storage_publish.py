"""Publishing raw/ to published/ must carry updates, not just new files.

It skipped any key already published, so a regenerated template or a replaced
letterhead uploaded to raw/ never reached the app: every deploy reported it
"already present" and production kept serving the old file.
"""

import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from apps.core.storage import FilesystemDocumentStorage, copy_area


class CopyAreaTests(SimpleTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.raw = FilesystemDocumentStorage(root / "raw")
        self.published = FilesystemDocumentStorage(root / "published")

    def tearDown(self):
        self.directory.cleanup()

    def _put(self, store, key, content):
        store.put_bytes(content=content, key=key)

    def test_an_identical_object_is_skipped(self):
        self._put(self.raw, "private-content/a.docx", b"same")
        self._put(self.published, "private-content/a.docx", b"same")

        self.assertEqual(copy_area(self.raw, self.published, prefix="private-content"), (0, 1))

    def test_a_changed_object_replaces_the_published_one(self):
        self._put(self.raw, "private-content/a.docx", b"regenerated")
        self._put(self.published, "private-content/a.docx", b"stale")

        self.assertEqual(copy_area(self.raw, self.published, prefix="private-content"), (1, 0))
        with self.published.open("private-content/a.docx") as handle:
            self.assertEqual(handle.read(), b"regenerated")

    def test_the_publish_command_carries_an_update(self):
        root = Path(self.directory.name)
        self._put(self.raw, "private-content/letterheads/x/letterhead.docx", b"new stationery")
        self._put(self.published, "private-content/letterheads/x/letterhead.docx", b"old stationery")

        with override_settings(DOCUMENT_STORAGE_BACKEND="filesystem", DOCUMENT_STORAGE_ROOT=root):
            call_command("publish_private_content", stdout=StringIO())

        with self.published.open("private-content/letterheads/x/letterhead.docx") as handle:
            self.assertEqual(handle.read(), b"new stationery")
