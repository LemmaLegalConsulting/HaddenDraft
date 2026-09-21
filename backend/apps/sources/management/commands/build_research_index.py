"""Build the learned term-neighbour table research mode expands queries with.

This is counting, not inference. Two terms are neighbours here when they are
characteristic of the same documents across this corpus, which is why the table
can be rebuilt from the corpus alone, checked into nothing, and reproduced
exactly by anyone with the same content library. No model is called during the
build and none is called when the table is read.

The approximation is stated rather than hidden: a term is represented by the
documents it is most characteristic of -- its top ``--top-terms`` positions by
TF-IDF -- rather than by every document it appears in. A term that appears once
in passing in a hundred sections is not described by those sections, and
carrying them costs the square of the vocabulary in memory for no gain.

    manage.py build_research_index
    manage.py build_research_index --status
"""

from __future__ import annotations

import json
import math
import time
from array import array
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.core.content_library import content_library_dir
from apps.sources.research.expansion import NEIGHBOURS_PATH, status as expansion_status
from apps.sources.research.index import research_index, reset_index


SCHEMA_VERSION = 1


class Command(BaseCommand):
    help = "Build the deterministic term-neighbour table used for research-mode query expansion."

    def add_arguments(self, parser):
        parser.add_argument("--output", default="", help="Where to write the table. Defaults to the content library.")
        parser.add_argument("--min-document-frequency", type=int, default=8)
        parser.add_argument(
            "--max-document-ratio", type=float, default=0.15,
            help="Skip terms in more than this share of the corpus; they describe nothing.",
        )
        parser.add_argument("--min-term-length", type=int, default=4)
        parser.add_argument(
            "--max-vocabulary", type=int, default=8000,
            help="Similarity is held as a dense square of this many terms; 8000 costs about 256MB.",
        )
        parser.add_argument("--top-terms", type=int, default=30, help="Terms per document that represent it.")
        parser.add_argument("--neighbors", type=int, default=8)
        parser.add_argument("--min-similarity", type=float, default=0.30)
        parser.add_argument("--status", action="store_true", help="Report the current table and exit.")

    def handle(self, *args, **options):
        if options["status"]:
            self.stdout.write(json.dumps(expansion_status(), indent=2))
            return

        started = time.monotonic()
        reset_index()
        index = research_index()
        self.stdout.write(
            f"Indexed {index.document_count} documents "
            f"({index.bm25.vocabulary_size} distinct terms) in {index.build_seconds:.1f}s."
        )

        vocabulary = self._vocabulary(index, options)
        if len(vocabulary) < 2:
            raise SystemExit("The corpus is too small to learn term neighbours from.")
        self.stdout.write(f"Vocabulary for similarity: {len(vocabulary)} terms.")

        weights_by_document = self._document_weights(index, vocabulary, options["top_terms"])
        similarity, norms = self._accumulate(weights_by_document, len(vocabulary))
        neighbors = self._neighbors(vocabulary, similarity, norms, options)

        payload = {
            "schema_version": SCHEMA_VERSION,
            "built_at": datetime.now(timezone.utc).isoformat(),
            "generator": "manage.py build_research_index",
            "corpus_fingerprint": _fingerprint_digest(index.fingerprint),
            "document_count": index.document_count,
            "parameters": {
                "min_document_frequency": options["min_document_frequency"],
                "max_document_ratio": options["max_document_ratio"],
                "min_term_length": options["min_term_length"],
                "max_vocabulary": options["max_vocabulary"],
                "top_terms": options["top_terms"],
                "neighbors": options["neighbors"],
                "min_similarity": options["min_similarity"],
            },
            "method": (
                "TF-IDF term vectors over the documents each term is most characteristic of, "
                "compared by cosine. Counting only; no model is involved."
            ),
            "neighbors": neighbors,
        }

        output = Path(options["output"]) if options["output"] else content_library_dir().joinpath(*NEIGHBOURS_PATH)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(
            f"Wrote {len(neighbors)} terms with neighbours to {output} "
            f"({output.stat().st_size / 1024:.0f} KB) in {time.monotonic() - started:.1f}s."
        ))

    def _vocabulary(self, index, options):
        """Mid-frequency terms, most common first, capped so the square fits in memory."""
        ceiling = index.document_count * options["max_document_ratio"]
        candidates = []
        for term in index.bm25._postings:
            if len(term) < options["min_term_length"]:
                continue
            frequency = index.bm25.document_frequency(term)
            if frequency < options["min_document_frequency"] or frequency > ceiling:
                continue
            candidates.append((frequency, term))
        candidates.sort(key=lambda item: (-item[0], item[1]))
        return [term for _frequency, term in candidates[: options["max_vocabulary"]]]

    def _document_weights(self, index, vocabulary, top_terms):
        """Per document, its most characteristic vocabulary terms and their TF-IDF."""
        positions = {term: position for position, term in enumerate(vocabulary)}
        per_document = [[] for _ in range(index.bm25.document_count)]
        for term, position in positions.items():
            postings = index.bm25._postings[term]
            idf = index.bm25.idf(term)
            for offset in range(0, len(postings), 2):
                ordinal, frequency = postings[offset], postings[offset + 1]
                per_document[ordinal].append((position, (1 + math.log(frequency)) * idf))
        for ordinal, entries in enumerate(per_document):
            if len(entries) > top_terms:
                entries.sort(key=lambda item: -item[1])
                del entries[top_terms:]
            entries.sort()
        return per_document

    def _accumulate(self, weights_by_document, size):
        similarity = array("f", bytes(4 * size * size))
        norms = array("d", bytes(8 * size))
        for entries in weights_by_document:
            for outer in range(len(entries)):
                position, weight = entries[outer]
                norms[position] += weight * weight
                row = position * size
                for inner in range(outer + 1, len(entries)):
                    other, other_weight = entries[inner]
                    product = weight * other_weight
                    similarity[row + other] += product
                    similarity[other * size + position] += product
        for position in range(size):
            norms[position] = math.sqrt(norms[position])
        return similarity, norms

    def _neighbors(self, vocabulary, similarity, norms, options):
        size = len(vocabulary)
        wanted, floor = options["neighbors"], options["min_similarity"]
        table = {}
        for position, term in enumerate(vocabulary):
            norm = norms[position]
            if not norm:
                continue
            row = position * size
            best = []
            for other in range(size):
                product = similarity[row + other]
                if not product or other == position:
                    continue
                other_norm = norms[other]
                if not other_norm:
                    continue
                cosine = product / (norm * other_norm)
                if cosine >= floor:
                    best.append((round(cosine, 4), vocabulary[other]))
            if not best:
                continue
            best.sort(key=lambda item: (-item[0], item[1]))
            table[term] = [[neighbour, score] for score, neighbour in best[:wanted]]
        return table


def _fingerprint_digest(fingerprint):
    import hashlib

    return hashlib.sha256(repr(fingerprint).encode("utf-8")).hexdigest()[:16]
