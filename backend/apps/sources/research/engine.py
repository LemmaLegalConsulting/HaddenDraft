"""Deterministic research search.

Nothing in this module imports ``apps.ai``, and that is deliberate rather than
incidental. Research mode's promise is that the corpus can be searched with
generative AI switched off entirely, so the code path that answers a search
cannot reach a model even by accident. Reranking and synthesis are applied by
the caller, on top of a result set that already exists, and are reported
separately -- a reader must be able to tell what the library said from what a
model said about it.

The pipeline:

1. Parse the query into phrases, citations, field filters and loose terms.
2. Require what was named literally. A quoted phrase and a citation are
   requirements, not hints: they narrow the candidate set to documents whose
   text actually contains them, and when nothing does, the search says so
   instead of ranking something else to the top.
3. Score the rest with BM25 over the typed terms plus file-backed expansions,
   each weighted below a literal hit and each labelled with where it came from.
4. Drop what matched too little of the question to be an answer, collapse the
   passages of one authority into one result, then narrow and count facets.

Every step is a pure function of the corpus and the query string.
"""

from __future__ import annotations

import math
import time

from apps.sources.research import expansion as expansion_module
from apps.sources.research import facets as facets_module
from apps.sources.research import snippets
from apps.sources.research.corpus import CORPORA, CORPUS_LABELS
from apps.sources.research.index import corpus_fingerprint, research_index
from apps.sources.research.query import index_tokens, parse_query


DEFAULT_LIMIT = 20
MAX_LIMIT = 100

# A literal hit is worth more than any amount of term overlap: it is what the
# reader asked for, and the only thing a phrase or citation query can mean. The
# logarithm is what keeps a treatise section that discusses R.C. 5321.04 thirty
# times from outranking R.C. 5321.04 itself.
EXACT_WEIGHT = 40.0
# A document that *is* the cited authority, rather than one that mentions it.
# Set above any reachable occurrence score, because the section a reader cited
# belongs above the chapter of commentary that discusses it thirty times.
IDENTITY_WEIGHT = 500.0
# Where a matter's court decided a near-tie, but never membership: trial-court
# decisions are persuasive everywhere, so another county's case stays in the
# list where the reader can see it.
#
# Both adjust the score by a proportion rather than by a number of points. A
# fixed penalty is a different thing at different scales: on a large corpus it
# nudges a reversed decision down the page, and on a small one it drives the
# score below zero and deletes it. Demoting a superseded decision is right;
# hiding it is not, because the reader may be looking for exactly that history.
JURISDICTION_FACTOR = 1.15
SUPERSEDED_FACTOR = 0.55

# How much of a question a document has to answer to be listed at all. Without
# a floor, a query of four ideas returns every document containing any one of
# them, which on this corpus is nearly all of them -- a result count that is
# accurate and useless. Half, rounded up, keeps a one-word query working
# through expansion alone while stopping a four-word query from matching on
# "rent".
COVERAGE_RATIO = 0.5


def _identifying_tokens(tokens):
    """The parts of a citation that identify the authority rather than the reporter.

    ``R.C. 5321.04`` tokenizes to ``r``, ``c`` and ``5321.04``. The letters
    belong to one spelling of the reporter -- ``Ohio Rev. Code 5321.04`` has no
    ``r`` at all -- so narrowing the candidate pool by them looks for the
    abbreviation instead of the section, and finds only the documents that
    happen to use it.
    """
    numbers = [token for token in tokens if any(character.isdigit() for character in token)]
    return numbers or [token for token in tokens if len(token) > 3] or list(tokens)


def _whole_number(value, default, *, minimum=0, maximum=None):
    """A paging value from a URL, which is a string a person may have edited.

    A shareable link is a link: it gets truncated, hand-edited and pasted back.
    ``?limit=20.5`` reaching ``int()`` unguarded is a 500 on a research search,
    which is the one thing this endpoint is supposed not to do.
    """
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        number = default
    number = max(minimum, number)
    return min(number, maximum) if maximum is not None else number


def _rarest_token(bm25, tokens):
    present = [(bm25.document_frequency(token), token) for token in tokens]
    present = [item for item in present if item[0]]
    return min(present)[1] if present else ""


def _citation_candidates(index, citation):
    """Documents that could contain a citation, narrowed by its rarest identifier."""
    token = _rarest_token(index.bm25, _identifying_tokens(index_tokens(citation.normalized)))
    return index.bm25.documents_with(token) if token else set()


def _phrase_candidates(index, phrase):
    candidates = None
    for token in index_tokens(phrase):
        documents = index.bm25.documents_with(token)
        candidates = documents if candidates is None else (candidates & documents)
        if not candidates:
            return set()
    return candidates or set()


def _first_occurrence_count(haystack, needles):
    for needle in needles:
        count = haystack.count(needle.casefold())
        if count:
            return count
    return 0


def _requirements(index, parsed):
    """Ordinals literally containing every phrase and citation, and what missed.

    ``(ordinals or None, hits per ordinal, identity per ordinal, unmatched)``.
    ``None`` means nothing literal was asked for, so nothing is required.
    """
    required = None
    hits = {}
    identity = {}
    unmatched = []

    for phrase in parsed.phrases:
        needle = phrase.casefold()
        found = set()
        for ordinal in _phrase_candidates(index, phrase):
            occurrences = index.records[ordinal].text.casefold().count(needle)
            if occurrences:
                found.add(ordinal)
                hits[ordinal] = hits.get(ordinal, 0) + occurrences
        if not found:
            unmatched.append({"kind": "phrase", "value": phrase})
        required = found if required is None else (required & found)

    for citation in parsed.citations:
        found = set()
        for ordinal in _citation_candidates(index, citation):
            record = index.records[ordinal]
            occurrences = _first_occurrence_count(record.text.casefold(), citation.variants)
            if not occurrences:
                continue
            found.add(ordinal)
            hits[ordinal] = hits.get(ordinal, 0) + occurrences
            # The section whose own citation is the one being looked up is the
            # answer; a treatise paragraph citing it is commentary on the
            # answer. Only a record that carries its own authority citation can
            # be the former -- a treatise chunk's citation is a location, and
            # its heading names every section it discusses.
            if record.authority_citation and _first_occurrence_count(
                record.authority_citation.casefold(), citation.variants
            ):
                identity[ordinal] = identity.get(ordinal, 0) + 1
        if not found:
            unmatched.append({"kind": "citation", "value": citation.normalized})
        required = found if required is None else (required & found)

    return required, hits, identity, unmatched


def _concepts(parsed, expansions):
    """One concept per typed term, carrying the tokens that stand in for it.

    Coverage is measured in concepts rather than tokens so that reaching a
    document through a synonym counts exactly as much as reaching it through
    the word the reader typed -- which is the only reading under which
    expansion helps rather than distorts.
    """
    concepts = []
    for term in parsed.terms:
        concepts.append({"term": term, "tokens": set(index_tokens(term))})
    by_term = {concept["term"]: concept for concept in concepts}
    for item in expansions:
        concept = by_term.get(item.source_term)
        if concept:
            concept["tokens"].update(index_tokens(item.term))
    return concepts


def _weighted_terms(parsed, expansions):
    weights = {}
    for item in expansions:
        for token in index_tokens(item.term):
            weights[token] = max(weights.get(token, 0.0), item.weight)
    # A typed word always outweighs anything reached through it.
    for term in parsed.terms:
        for token in index_tokens(term):
            weights[token] = 1.0
    return sorted(weights.items())


def _merge_filters(parsed, filters):
    merged = {field: list(values) for field, values in (filters or {}).items() if values}
    for field, value in parsed.filters:
        merged.setdefault(field, []).append(value)
    return {field: list(dict.fromkeys(values)) for field, values in merged.items() if values}


def _jurisdiction_match(jurisdiction, record):
    from apps.sources import jurisdiction as jurisdiction_matching

    return jurisdiction_matching.matches(
        jurisdiction,
        record.facets.get("court", ""),
        record.facets.get("county", ""),
        record.metadata.get("jurisdiction", ""),
    )


def ai_report(*, rerank=None, synthesis=None):
    """What a model did to this result set, stated whether or not one was asked for.

    Always present, always explicit. A reader should never have to infer from a
    missing field that nothing generative ran, and should never have to infer
    from a generic icon that something did.
    """
    return {
        "retrieval": "deterministic-bm25",
        "rerank": rerank or {
            "requested": False, "applied": False,
            "reason": "Results are in deterministic relevance order; no model was asked to reorder them.",
        },
        "synthesis": synthesis or {
            "requested": False, "applied": False,
            "reason": "No answer was generated; every line below is text from the corpus.",
        },
    }


def _result_dict(record, *, score, parsed, concepts, matched_concepts, expansion_terms, exact_hits, passages):
    snippet = snippets.build(
        record.text,
        terms=parsed.terms,
        phrases=parsed.phrases,
        citations=[variant for citation in parsed.citations for variant in citation.variants[:2]],
        expansions=expansion_terms,
    )
    return {
        "id": record.key,
        "groupId": record.group_key,
        "title": record.title,
        "citation": record.citation,
        "url": record.url,
        "corpus": record.corpus,
        "corpusLabel": CORPUS_LABELS.get(record.corpus, record.corpus),
        "snippet": snippet["text"],
        "snippetMatches": snippet["matches"],
        "matchedTerms": snippet["matchedTerms"],
        "matchedExpansions": snippet["matchedExpansions"],
        "matchedConcepts": sorted(matched_concepts),
        # The reader's own ideas this document does *not* carry. Saying so is
        # how a partial match stays honest about being partial.
        "missingConcepts": sorted({concept["term"] for concept in concepts} - matched_concepts),
        "exactMatches": exact_hits,
        # Other passages of the same authority that also matched, so collapsing
        # them is visible rather than silent.
        "passages": passages,
        "facets": dict(record.facets),
        "metadata": dict(record.metadata),
        "open": dict(record.open_target),
        "score": round(score, 4),
    }


def _coverage_note(browse, required, concepts, required_coverage):
    if browse:
        return "Everything matching these filters is listed, in alphabetical order."
    if required is not None:
        return "Every result contains the phrase or citation that was asked for."
    if concepts:
        return (
            "A result had to carry at least "
            f"{required_coverage} of the {len(concepts)} ideas in this question."
        )
    return ""


def _empty(parsed, merged_filters, expansion_mode, limit, offset, index, fingerprint, started):
    return {
        "query": parsed.to_dict(),
        "results": [],
        "total": 0,
        "limit": limit,
        "offset": offset,
        "facets": facets_module.counts([], merged_filters),
        "filters": merged_filters,
        "coverage": {"conceptCount": 0, "required": 0},
        "expansion": {
            "mode": expansion_mode, "applied": [], "suppressed": False,
            "suppressedReason": "", "status": expansion_module.status(),
        },
        "unmatched": [],
        "ai": ai_report(),
        "index": index.status(current_fingerprint=fingerprint),
        "tookMs": round((time.monotonic() - started) * 1000, 1),
    }


def search(
    query_text,
    *,
    filters=None,
    corpora=None,
    expansion_mode=expansion_module.DEFAULT_MODE,
    limit=DEFAULT_LIMIT,
    offset=0,
    jurisdiction="",
    index=None,
):
    """Run one deterministic search and report everything it did."""
    started = time.monotonic()
    parsed = parse_query(query_text)
    limit = _whole_number(limit, DEFAULT_LIMIT, minimum=1, maximum=MAX_LIMIT)
    offset = _whole_number(offset, 0)
    merged_filters = _merge_filters(parsed, filters)
    wanted_corpora = [corpus for corpus in (corpora or []) if corpus in CORPORA]
    if wanted_corpora:
        merged_filters["sourceType"] = wanted_corpora

    # A caller that supplied its own index owns its freshness. Asking the
    # database about a corpus this search is not reading would be a query that
    # buys nothing -- and in a test without a database, one that cannot run.
    supplied = index is not None
    index = index or research_index()
    fingerprint = None if supplied else corpus_fingerprint()
    if parsed.is_empty:
        return _empty(parsed, merged_filters, expansion_mode, limit, offset, index, fingerprint, started)

    # An exact query asks whether the corpus contains a specific thing.
    # Broadening it with near neighbours answers a question nobody asked.
    suppressed = parsed.is_exact and expansion_mode != "none"
    expansions = [] if suppressed else expansion_module.expand(parsed.terms, mode=expansion_mode)
    expansion_terms = [item.term for item in expansions]
    concepts = _concepts(parsed, expansions)
    required_coverage = max(1, math.ceil(len(concepts) * COVERAGE_RATIO)) if concepts else 0

    required, exact_hits, identity, unmatched = _requirements(index, parsed)
    # `court:cleveland` with nothing else is a browse: the reader has named a
    # set rather than described one, and every record in that set is an answer.
    # Scoring it as a query of no terms returned an empty list under the note
    # "every result contains the phrase that was asked for", for a query that
    # asked for no phrase -- and `court:cleveland` is the example the status
    # endpoint offers.
    browse = not (parsed.terms or parsed.phrases or parsed.citations)
    scored = (
        {ordinal: (0.0, []) for ordinal in range(len(index.records))} if browse
        else index.bm25.score(_weighted_terms(parsed, expansions), restrict_to=required)
    )
    if required is not None:
        # A citation or phrase query may name nothing else; those documents
        # still matched, and a zero BM25 score must not drop them.
        for ordinal in required:
            scored.setdefault(ordinal, (0.0, []))

    excluded_ordinals = set()
    for term in parsed.excluded:
        for token in index_tokens(term):
            excluded_ordinals |= index.bm25.documents_with(token)

    ranked = []
    for ordinal, (score, matched_tokens) in scored.items():
        if ordinal in excluded_ordinals:
            continue
        tokens = set(matched_tokens)
        matched_concepts = {concept["term"] for concept in concepts if concept["tokens"] & tokens}
        # A literal requirement has already established relevance; asking it to
        # also cover half the loose terms would drop the exact hit it found.
        if required is None and len(matched_concepts) < required_coverage:
            continue
        record = index.records[ordinal]
        total = score * record.weight
        if exact_hits.get(ordinal):
            total += EXACT_WEIGHT * (1 + math.log(exact_hits[ordinal]))
        total += IDENTITY_WEIGHT * identity.get(ordinal, 0)
        if jurisdiction and _jurisdiction_match(jurisdiction, record):
            total *= JURISDICTION_FACTOR
        if record.metadata.get("supersededOrCriticized"):
            total *= SUPERSEDED_FACTOR
        # A browse has no relevance to speak of, so zero is its ordinary score
        # rather than a reason to drop the record.
        if total <= 0 and not browse:
            continue
        ranked.append((total, ordinal, matched_concepts))

    ranked.sort(key=lambda item: (-item[0], index.records[item[1]].title, index.records[item[1]].key))

    grouped = []
    seen_groups = {}
    for score, ordinal, matched_concepts in ranked:
        record = index.records[ordinal]
        position = seen_groups.get(record.group_key)
        if position is None:
            seen_groups[record.group_key] = len(grouped)
            grouped.append([score, ordinal, matched_concepts, []])
            continue
        best = grouped[position]
        best[2] = best[2] | matched_concepts
        best[3].append({
            "id": record.key,
            "label": record.metadata.get("documentTypeLabel") or record.metadata.get("heading") or "Passage",
        })

    # Facets are counted over everything the query matched, before narrowing,
    # so each facet can still offer the values a reader could switch to. Each
    # one then leaves out its own filter; narrowing to Cuyahoga must not make
    # Cuyahoga the only county the list knows about.
    facets = facets_module.counts([index.records[item[1]] for item in grouped], merged_filters)
    if merged_filters:
        keep = {id(record) for record in facets_module.apply([index.records[item[1]] for item in grouped], merged_filters)}
        grouped = [item for item in grouped if id(index.records[item[1]]) in keep]

    page = grouped[offset : offset + limit]
    results = [
        _result_dict(
            index.records[ordinal],
            score=score,
            parsed=parsed,
            concepts=concepts,
            matched_concepts=matched_concepts,
            expansion_terms=expansion_terms,
            exact_hits=exact_hits.get(ordinal, 0),
            passages=passages,
        )
        for score, ordinal, matched_concepts, passages in page
    ]

    applied = {}
    for item in expansions:
        applied.setdefault(item.source_term, []).append(item.to_dict())

    return {
        "query": parsed.to_dict(),
        "results": results,
        "total": len(grouped),
        "limit": limit,
        "offset": offset,
        "facets": facets,
        "filters": merged_filters,
        "coverage": {
            "conceptCount": len(concepts),
            "required": 0 if required is not None or browse else required_coverage,
            "note": _coverage_note(browse, required, concepts, required_coverage),
        },
        "expansion": {
            "mode": expansion_mode,
            "applied": [{"term": term, "expansions": items} for term, items in sorted(applied.items())],
            "suppressed": suppressed,
            "suppressedReason": (
                "This query names an exact phrase or citation, so it was run literally without concept expansion."
                if suppressed else ""
            ),
            "status": expansion_module.status(),
        },
        "unmatched": unmatched,
        "ai": ai_report(),
        "index": index.status(current_fingerprint=fingerprint),
        "tookMs": round((time.monotonic() - started) * 1000, 1),
    }
