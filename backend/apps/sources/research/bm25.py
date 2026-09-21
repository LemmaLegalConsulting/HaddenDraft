"""A small, exact BM25 index built in this process from this corpus.

BM25 rather than the hand-tuned hit counting retrieval grew up on, because term
weighting has to come from the corpus: "habitability" appears in a handful of
sections and "tenant" appears in nearly all of them, and a scorer that cannot
tell those apart ranks the common word's document first. Nothing here is
learned or fitted -- the parameters are the published defaults and the
statistics are counts -- so the same corpus and the same query always produce
the same ordering.

Postings live in ``array('i')`` rather than lists of tuples. The case-law corpus
alone is some twenty-four megabytes of text; held as Python tuples its postings
cost several hundred megabytes, and the array form costs tens.
"""

from __future__ import annotations

import math
from array import array
from collections import Counter


K1 = 1.2
B = 0.75


class Bm25Index:
    """Term postings and lengths for a fixed set of documents.

    Documents are added in order; ``finish`` freezes the statistics. Callers
    address documents by their ordinal, which is what the postings store.
    """

    def __init__(self, *, k1=K1, b=B):
        self.k1 = k1
        self.b = b
        self._postings = {}
        self._lengths = array("i")
        self._total_length = 0

    def add(self, tokens):
        """Index one document's tokens and return its ordinal."""
        ordinal = len(self._lengths)
        counts = Counter(tokens)
        for term, count in counts.items():
            postings = self._postings.get(term)
            if postings is None:
                postings = self._postings[term] = array("i")
            postings.append(ordinal)
            postings.append(count)
        length = sum(counts.values())
        self._lengths.append(length)
        self._total_length += length
        return ordinal

    @property
    def document_count(self):
        return len(self._lengths)

    @property
    def average_length(self):
        return (self._total_length / len(self._lengths)) if len(self._lengths) else 0.0

    @property
    def vocabulary_size(self):
        return len(self._postings)

    def document_frequency(self, term):
        postings = self._postings.get(term)
        return len(postings) // 2 if postings else 0

    def documents_with(self, term):
        """Ordinals containing ``term``, without their frequencies."""
        postings = self._postings.get(term)
        return set(postings[0::2]) if postings else set()

    def idf(self, term):
        frequency = self.document_frequency(term)
        if not frequency:
            return 0.0
        # Lucene's non-negative form: the classic BM25 IDF goes negative for a
        # term in more than half the corpus, which would make a document score
        # worse for containing a word the reader typed.
        return math.log(1 + (self.document_count - frequency + 0.5) / (frequency + 0.5))

    def score(self, weighted_terms, *, restrict_to=None):
        """BM25 over ``(term, weight)`` pairs, as ``{ordinal: (score, matched terms)}``.

        The matched terms come back with the score because research mode has to
        be able to say which of the reader's words a result actually contains,
        and which of them were reached through an expansion.
        """
        scores = {}
        matched = {}
        average_length = self.average_length or 1.0
        for term, weight in weighted_terms:
            postings = self._postings.get(term)
            if not postings or weight <= 0:
                continue
            idf = self.idf(term) * weight
            if idf <= 0:
                continue
            for index in range(0, len(postings), 2):
                ordinal = postings[index]
                if restrict_to is not None and ordinal not in restrict_to:
                    continue
                frequency = postings[index + 1]
                normalized = self._lengths[ordinal] / average_length
                contribution = idf * (frequency * (self.k1 + 1)) / (
                    frequency + self.k1 * (1 - self.b + self.b * normalized)
                )
                scores[ordinal] = scores.get(ordinal, 0.0) + contribution
                matched.setdefault(ordinal, []).append(term)
        return {ordinal: (score, matched[ordinal]) for ordinal, score in scores.items()}

    def state(self):
        """The index as plain data, for persisting a build between processes."""
        return {"k1": self.k1, "b": self.b, "postings": self._postings, "lengths": self._lengths}

    @classmethod
    def from_state(cls, state):
        index = cls(k1=state.get("k1", K1), b=state.get("b", B))
        index._postings = state["postings"]
        index._lengths = state["lengths"]
        index._total_length = sum(index._lengths)
        return index
