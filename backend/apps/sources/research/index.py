"""Building the research index once and keeping it until the corpus changes.

The index is derived data: everything in it comes from the generated content
library and the imported case-law corpus, and it is rebuilt rather than edited.
It is held in the process because it is small -- tens of megabytes of postings
over roughly thirty-five megabytes of text -- and because a search that has to
ask the database for candidates cannot honestly report how many documents
matched.

Freshness is reported, never assumed. The index records the corpus fingerprint
it was built from, and a caller can ask whether that still matches what is on
disk and in the database. A stale index that quietly answers as though it were
current would tell an advocate their newly imported decisions are not in the
corpus.
"""

from __future__ import annotations

import hashlib
import threading
import time
from datetime import datetime, timezone

from apps.sources.library import load_manifest, manifest_paths
from apps.sources.research.bm25 import Bm25Index
from apps.sources.research.corpus import case_records, library_records, managed_records
from apps.sources.research.query import index_tokens


class ResearchIndex:
    def __init__(self, records, bm25, fingerprint, *, identity="", build_seconds=0.0):
        self.records = records
        self.bm25 = bm25
        self.fingerprint = fingerprint
        # Which corpus this is, for anything derived from the corpus as a whole
        # rather than from its current rows -- the learned neighbour table.
        self.identity = identity
        self.built_at = datetime.now(timezone.utc).isoformat()
        self.build_seconds = build_seconds

    @property
    def document_count(self):
        return len(self.records)

    def status(self, *, current_fingerprint=None):
        corpora = {}
        for record in self.records:
            corpora[record.corpus] = corpora.get(record.corpus, 0) + 1
        return {
            "builtAt": self.built_at,
            "buildSeconds": round(self.build_seconds, 2),
            "documentCount": self.document_count,
            "vocabularySize": self.bm25.vocabulary_size,
            "documentsByCorpus": corpora,
            "stale": current_fingerprint is not None and current_fingerprint != self.fingerprint,
        }


def corpus_fingerprint():
    """What the index was built from, cheap enough to check on every search."""
    from django.db.models import Max

    from apps.caselaw.models import CaseLawDecision, CaseLawSearchDocument

    manifests = []
    for path in manifest_paths():
        try:
            status = path.stat()
        except OSError:
            continue
        manifests.append((str(path), status.st_mtime_ns, status.st_size))
    cases = CaseLawSearchDocument.objects.filter(decision__approved_for_search=True).count()
    newest = (
        CaseLawSearchDocument.objects.filter(decision__approved_for_search=True)
        .order_by("-id").values_list("id", flat=True).first()
    )
    # A count and a high-water mark miss an edit in place, and those happen:
    # a county normalized onto the shared vocabulary, a treatment status
    # checked, a correction made in the admin. Without this the index keeps
    # answering with the values it was built from, which is the one kind of
    # staleness a reader has no way to notice.
    touched = CaseLawDecision.objects.aggregate(latest=Max("updated_at"))["latest"]
    from apps.sources.models import ManagedSource
    managed_count = ManagedSource.objects.filter(state="published", current_version__isnull=False).count()
    managed_touched = ManagedSource.objects.aggregate(latest=Max("updated_at"))["latest"]
    return (
        tuple(manifests), cases, newest, touched.isoformat() if touched else "",
        managed_count, managed_touched.isoformat() if managed_touched else "",
    )


def index_from_records(records):
    """An index over records supplied directly, for tests and for a partial corpus."""
    bm25 = Bm25Index()
    for record in records:
        bm25.add(index_tokens(record.text))
    return ResearchIndex(
        list(records), bm25, ("supplied", len(records)),
        identity=f"supplied:{len(records)}",
    )


def corpus_identity():
    """What corpus this is, as distinct from what state it is in.

    ``corpus_fingerprint`` answers "has anything changed at all", which is the
    right question for an index that must not serve stale rows, and the wrong
    one for the learned term-neighbour table: that is built from how words
    co-occur across the whole corpus, and one decision having its county
    corrected does not change that. Keyed on the fingerprint, the table would
    be invalidated by the next edit anybody made, which in practice means
    never being usable.

    So this is composition rather than state -- which documents are here and
    how many pieces they are in. It survives an edit and it does not survive a
    re-ingest, a new municipality, or the file being copied from another
    deployment, which are the cases where the table really does describe a
    different corpus than the one being searched.
    """
    from apps.caselaw.models import CaseLawSearchDocument

    documents = []
    for path in manifest_paths():
        manifest = load_manifest(path)
        if not manifest:
            continue
        slug = str(manifest.get("document_slug") or "")
        if slug:
            documents.append((slug, len(manifest.get("chunks") or [])))
    cases = CaseLawSearchDocument.objects.filter(decision__approved_for_search=True).count()
    from apps.sources.models import ManagedSource
    managed = list(
        ManagedSource.objects.filter(state="published", current_version__isnull=False)
        .values_list("slug", "current_version__chunk_count")
    )
    payload = repr((sorted(set(documents)), cases, sorted(managed)))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def build_index():
    started = time.monotonic()
    records = [*library_records(), *case_records(), *managed_records()]
    bm25 = Bm25Index()
    for record in records:
        bm25.add(index_tokens(record.text))
    return ResearchIndex(
        records, bm25, corpus_fingerprint(),
        identity=corpus_identity(), build_seconds=time.monotonic() - started,
    )


class _IndexHolder:
    """The process-wide index, plus whatever is currently building it.

    A build takes seconds, and several requests can arrive during one. The lock
    makes the extra requests wait for the build in flight rather than each
    starting their own, which would multiply the memory as well as the time.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._index = None

    def peek(self):
        return self._index

    def get(self, *, refresh=True):
        index = self._index
        fingerprint = corpus_fingerprint() if refresh else None
        if index is not None and (fingerprint is None or index.fingerprint == fingerprint):
            return index
        with self._lock:
            # Another thread may have finished the rebuild while this one waited.
            index = self._index
            if index is not None and index.fingerprint == corpus_fingerprint():
                return index
            self._index = build_index()
            return self._index

    def warm(self):
        """Start a build in the background and say whether one is running.

        The index takes seconds to build and every gunicorn worker builds its
        own after the fork, so on a deployment that scales to zero the first
        research request of the day pays for it. The interface asks for the
        status when the search view opens -- several seconds before anyone has
        finished typing -- so that request starts the build and returns at
        once, and the search that follows finds it done. A search that arrives
        first still waits, on the same lock, for the build already running
        rather than starting a second one.
        """
        if self._index is not None:
            return False
        if self._lock.locked():
            return True
        thread = threading.Thread(target=self.get, name="research-index-build", daemon=True)
        thread.start()
        return True

    def clear(self):
        with self._lock:
            self._index = None


_HOLDER = _IndexHolder()


def research_index(*, refresh=True):
    return _HOLDER.get(refresh=refresh)


def warm_index():
    """Build the index in the background if it is not built. Returns True if building."""
    return _HOLDER.warm()


def peek_index():
    """The index if it is already built, without building one."""
    return _HOLDER.peek()


def reset_index():
    """Drop the cached index. Tests and the build command use this."""
    _HOLDER.clear()
