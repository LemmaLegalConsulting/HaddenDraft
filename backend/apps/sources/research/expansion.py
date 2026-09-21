"""Concept expansion that never calls a model.

Opinions and statutes rarely reuse a researcher's phrasing. Someone looking for
"deficient notice" is looking for text that says "defective", "invalid", or
"failed to comply with R.C. 1923.04". Retrieval has to bridge that gap, and the
obvious bridge -- asking a model at query time -- puts a network call, a bill,
and a non-reproducible answer between a lawyer and their library.

So the bridge is precomputed and file-backed, in two layers that are reported
separately because they are trustworthy in different ways:

``thesaurus``
    Terms of art grouped by hand and reviewed, in
    ``content/research-index/thesaurus.yaml``. A group states its own
    ``verification`` and its source, exactly as a court rule or a legal-rule
    element list does. This is the layer that knows a forcible entry and
    detainer action is an eviction.

``distributional``
    Neighbours learned from how terms co-occur across the corpus itself, built
    offline by ``manage.py build_research_index``. No model is involved in the
    build either: it is counting. This layer catches the vocabulary nobody
    thought to curate, and it is reported as learned rather than reviewed
    because nothing has checked that a neighbour means what a reader will
    assume it means.

Both layers are optional. When the generated table is absent, the caller is told
so; an expansion that silently did not happen reads as a corpus that does not
contain the law, which is the wrong answer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import yaml

from apps.core.content_library import content_path
from apps.sources.research.query import content_terms, tokenize


THESAURUS_PATH = ("research-index", "thesaurus.yaml")
NEIGHBOURS_PATH = ("research-index", "term-neighbors.json")

THESAURUS = "thesaurus"
DISTRIBUTIONAL = "distributional"

# A reviewed group is a statement about the law; a learned neighbour is a
# statement about the corpus. Ranking keeps the difference.
THESAURUS_WEIGHT = 0.6

MODES = ("none", "thesaurus", "distributional", "all")
DEFAULT_MODE = "thesaurus"


@dataclass(frozen=True)
class Expansion:
    """One extra term retrieval will look for, and why."""

    source_term: str
    term: str
    basis: str
    weight: float
    verification: str = ""
    note: str = ""

    def to_dict(self):
        return {
            "sourceTerm": self.source_term,
            "term": self.term,
            "basis": self.basis,
            "weight": round(self.weight, 3),
            "verification": self.verification,
            "note": self.note,
        }


def _file_fingerprint(path):
    try:
        status = path.stat()
    except OSError:
        return None
    return (status.st_mtime_ns, status.st_size)


class _Cache:
    def __init__(self):
        self.thesaurus = None
        self.thesaurus_fingerprint = object()
        self.neighbours = None
        self.neighbours_fingerprint = object()


_CACHE = _Cache()


def _load_thesaurus():
    path = content_path(*THESAURUS_PATH)
    fingerprint = _file_fingerprint(path)
    if fingerprint == _CACHE.thesaurus_fingerprint:
        return _CACHE.thesaurus
    groups = []
    if fingerprint is not None:
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            payload = {}
        for group in payload.get("groups") or []:
            if not isinstance(group, dict):
                continue
            terms = [str(term).strip().casefold() for term in group.get("terms") or [] if str(term).strip()]
            if len(terms) < 2:
                continue
            groups.append({
                "label": str(group.get("label") or ""),
                "terms": terms,
                "verification": str(group.get("verification") or "unverified"),
                "source": str(group.get("source") or ""),
            })
    index = {}
    for group in groups:
        for term in group["terms"]:
            # A multi-word term of art is keyed by each of its content words so
            # a one-word query still reaches the group.
            keys = {term, *content_terms(tokenize(term))}
            for key in keys:
                index.setdefault(key, []).append(group)
    built = {"groups": groups, "index": index, "available": fingerprint is not None, "path": str(path)}
    _CACHE.thesaurus, _CACHE.thesaurus_fingerprint = built, fingerprint
    return built


def _load_neighbours():
    path = content_path(*NEIGHBOURS_PATH)
    fingerprint = _file_fingerprint(path)
    if fingerprint == _CACHE.neighbours_fingerprint:
        return _CACHE.neighbours
    payload = {}
    if fingerprint is not None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8")) or {}
        except (OSError, ValueError):
            payload = {}
    built = {
        "available": bool(payload.get("neighbors")),
        "neighbors": payload.get("neighbors") or {},
        "builtAt": payload.get("built_at", ""),
        "corpusFingerprint": payload.get("corpus_fingerprint", ""),
        "corpusIdentity": payload.get("corpus_identity", ""),
        "documentCount": payload.get("document_count", 0),
        "vocabularySize": len(payload.get("neighbors") or {}),
        "parameters": payload.get("parameters") or {},
        "path": str(path),
    }
    _CACHE.neighbours, _CACHE.neighbours_fingerprint = built, fingerprint
    return built


def _identity_mismatch(neighbours, corpus_identity):
    """Why a built table does not describe the corpus being searched, if it does not.

    The table was reported as usable no matter which corpus it came from: it
    recorded the corpus it was built from and nothing ever compared that with
    the corpus in hand. A file copied between deployments, or left behind by a
    re-ingest, went on being described to the reader as "learned from this
    corpus" -- a claim about provenance that had stopped being true.
    """
    if not corpus_identity or not neighbours["available"]:
        return ""
    stored = neighbours.get("corpusIdentity")
    if not stored:
        return (
            "This term-neighbour table was built before the corpus it came from was "
            "recorded, so it cannot be shown to describe the corpus being searched. "
            "Rebuild it with `manage.py build_research_index`."
        )
    if stored != corpus_identity:
        return (
            "This term-neighbour table was built from a different corpus "
            f"({stored}, against {corpus_identity} here), so it is not used. "
            "Rebuild it with `manage.py build_research_index`."
        )
    return ""


def status(corpus_identity=""):
    """What the two expansion layers can currently do, for the caller to show."""
    thesaurus = _load_thesaurus()
    neighbours = _load_neighbours()
    mismatch = _identity_mismatch(neighbours, corpus_identity)
    return {
        "thesaurus": {
            "available": thesaurus["available"] and bool(thesaurus["groups"]),
            "groupCount": len(thesaurus["groups"]),
            "verifiedGroupCount": sum(1 for group in thesaurus["groups"] if group["verification"] == "verified"),
        },
        "distributional": {
            "available": neighbours["available"] and not mismatch,
            "built": neighbours["available"],
            "matchesCorpus": not mismatch,
            "builtAt": neighbours["builtAt"],
            "corpusFingerprint": neighbours["corpusFingerprint"],
            "corpusIdentity": neighbours["corpusIdentity"],
            "documentCount": neighbours["documentCount"],
            "vocabularySize": neighbours["vocabularySize"],
            "parameters": neighbours["parameters"],
            "reason": (
                mismatch if mismatch
                else "" if neighbours["available"]
                else "Run `manage.py build_research_index` to build the learned term-neighbour table."
            ),
        },
        "modes": list(MODES),
        "usesAi": False,
    }


def expand(terms, *, mode=DEFAULT_MODE, per_term=4, corpus_identity=""):
    """Extra search terms for ``terms``, each labelled with where it came from.

    Expansions never displace the terms that were typed: the caller weights them
    below a literal hit, and the returned records let the reader see which of
    their words a result actually contains.
    """
    if mode not in MODES or mode == "none":
        return []
    typed = {str(term).casefold() for term in terms}
    expansions = []
    seen = set()

    def _add(source_term, term, basis, weight, verification="", note=""):
        key = (term, basis)
        if term in typed or key in seen or not term:
            return
        seen.add(key)
        expansions.append(Expansion(
            source_term=source_term, term=term, basis=basis,
            weight=weight, verification=verification, note=note,
        ))

    if mode in {THESAURUS, "all"}:
        index = _load_thesaurus()["index"]
        for term in terms:
            for group in index.get(str(term).casefold(), []):
                for sibling in group["terms"]:
                    _add(
                        term, sibling, THESAURUS, THESAURUS_WEIGHT,
                        verification=group["verification"],
                        note=group["label"],
                    )

    if mode in {DISTRIBUTIONAL, "all"}:
        loaded = _load_neighbours()
        # A table built from another corpus expands nothing here. Saying so is
        # the caller's job -- `status()` carries the reason -- but using it
        # anyway while calling it "learned from this corpus" is not an option.
        neighbours = {} if _identity_mismatch(loaded, corpus_identity) else loaded["neighbors"]
        for term in terms:
            for entry in (neighbours.get(str(term).casefold()) or [])[:per_term]:
                if not isinstance(entry, (list, tuple)) or len(entry) != 2:
                    continue
                neighbour, similarity = str(entry[0]), float(entry[1])
                _add(
                    term, neighbour, DISTRIBUTIONAL, similarity,
                    verification="learned",
                    note="Learned from how these terms co-occur in this corpus.",
                )

    return expansions
