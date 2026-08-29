"""Faceted browsing over the whole imported case-law corpus.

``browse`` clusters cases around a question or a seed decision.  This answers a
different question — "what has been imported, and what is in it?" — so it
filters and counts over the entire approved corpus rather than over one query's
results, and it pages instead of truncating at a relevance cutoff.

Everything here works on plain row dictionaries so the filtering, counting, and
sorting rules stay testable without the ORM.
"""

from __future__ import annotations

import re

from apps.caselaw.values import text_values

SCALAR_FACETS = {
    "court": "court",
    "county": "county",
    "judge": "judge",
    "authorityLevel": "authority_level",
    "publicationStatus": "publication_status",
    "treatmentStatus": "treatment_status",
    "caseType": "case_type",
    "subsidyProgram": "subsidy_program",
}
LIST_FACETS = {
    "issue": "issues",
    "statute": "statutes_cited",
    "regulation": "regulations_cited",
    "caseCitation": "cases_cited",
}
DERIVED_FACETS = ("decisionYear",)
FACET_NAMES = (*SCALAR_FACETS, *LIST_FACETS, *DERIVED_FACETS)

FACET_LABELS = {
    "court": "Court",
    "county": "County",
    "judge": "Judge",
    "authorityLevel": "Authority",
    "publicationStatus": "Publication",
    "treatmentStatus": "Treatment",
    "caseType": "Case type",
    "subsidyProgram": "Subsidy program",
    "decisionYear": "Decided",
    "issue": "Issue",
    "statute": "Statute cited",
    "regulation": "Regulation cited",
    "caseCitation": "Case cited",
}

ROW_FIELDS = (
    "id",
    "title",
    "short_title",
    "docket_number",
    "case_number",
    "citation_string",
    "decision_date",
    "imported_at",
    "key_facts",
    "outcome",
    "search_keywords",
    *SCALAR_FACETS.values(),
    *LIST_FACETS.values(),
)

SORTS = ("newest", "oldest", "title")
MAX_FACET_VALUES = 40


def _text(value):
    return str(value or "").strip()


def facet_raw_values(row, facet):
    if facet in LIST_FACETS:
        return text_values(row.get(LIST_FACETS[facet]))
    if facet == "decisionYear":
        date = row.get("decision_date")
        return [str(date.year)] if date else []
    value = _text(row.get(SCALAR_FACETS[facet]))
    return [value] if value else []


def canonical_value(facet, value):
    """Group the spellings the extractor produced for one real-world value.

    Metadata came out of documents, not out of a controlled vocabulary, so the
    same county arrives as "Cuyahoga" and "Cuyahoga County" and the same judge
    with and without the honorific.  Splitting a shelf across those spellings
    hides cases from a reader who narrowed correctly.  The reader still sees the
    wording that came from the documents — only the grouping is normalized.
    """
    text = _text(value).casefold()
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    if facet == "county":
        return re.sub(r"\s+county$", "", text)
    if facet == "judge":
        return re.sub(r"^(judge|magistrate|hon\.?|the honorable)\s+", "", text)
    return text


def facet_values(row, facet):
    return [canonical_value(facet, value) for value in facet_raw_values(row, facet)]


def read_filters(params):
    """Selected facet values from query parameters.

    Values inside one facet are alternatives; facets combine, so narrowing by
    county and by year means both, and picking two counties means either.
    """
    filters = {}
    for facet in FACET_NAMES:
        values = [value.strip() for value in params.getlist(facet) if value.strip()]
        if values:
            filters[facet] = values
    return filters


def row_text(row):
    return " ".join([
        _text(row.get("title")),
        _text(row.get("short_title")),
        _text(row.get("docket_number")),
        _text(row.get("case_number")),
        _text(row.get("citation_string")),
        _text(row.get("court")),
        _text(row.get("county")),
        _text(row.get("judge")),
        _text(row.get("key_facts")),
        _text(row.get("outcome")),
        " ".join(text_values(row.get("issues"))),
        " ".join(text_values(row.get("statutes_cited"))),
        " ".join(text_values(row.get("search_keywords"))),
    ]).casefold()


def _query_terms(query):
    return [term for term in re.findall(r"[a-z0-9§.]+", _text(query).casefold()) if len(term) > 1]


def search_rows(rows, query):
    terms = _query_terms(query)
    if not terms:
        return list(rows)
    return [row for row in rows if all(term in row_text(row) for term in terms)]


def _matches(row, facet, selected):
    wanted = {canonical_value(facet, value) for value in selected}
    return bool(set(facet_values(row, facet)) & wanted)


def apply_filters(rows, filters, *, skip=""):
    """Rows matching every selected facet, optionally ignoring one of them.

    ``skip`` is how a facet's own counts stay useful after a value in it is
    picked: the remaining values are still counted against everything else the
    reader narrowed by, so the alternatives on offer are real.
    """
    kept = rows
    for facet, selected in filters.items():
        if facet == skip:
            continue
        kept = [row for row in kept if _matches(row, facet, selected)]
    return kept


def facet_counts(rows, filters):
    facets = {}
    for facet in FACET_NAMES:
        scoped = apply_filters(rows, filters, skip=facet)
        counts = {}
        spellings = {}
        for row in scoped:
            for raw in facet_raw_values(row, facet):
                key = canonical_value(facet, raw)
                if not key:
                    continue
                counts[key] = counts.get(key, 0) + 1
                variants = spellings.setdefault(key, {})
                variants[raw] = variants.get(raw, 0) + 1
        selected = {canonical_value(facet, value): value for value in filters.get(facet, [])}
        for key, raw in selected.items():
            counts.setdefault(key, 0)
            spellings.setdefault(key, {}).setdefault(raw, 0)
        ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        items = [
            {
                "facet": facet,
                # Label the group with the spelling that appears most often, so
                # the chip reads as something a document actually says; ties go
                # to the fuller wording ("Cuyahoga County" over "Cuyahoga").
                "value": max(spellings[key].items(), key=lambda item: (item[1], len(item[0])))[0],
                "count": count,
                "selected": key in selected,
            }
            for key, count in ordered
        ]
        # Keep every selected value visible: a narrowing the reader can see but
        # not undo is worse than a longer list.
        head = [item for item in items[:MAX_FACET_VALUES]]
        tail = [item for item in items[MAX_FACET_VALUES:] if item["selected"]]
        if head or tail:
            facets[facet] = head + tail
    return facets


def _sort_key(row, sort):
    date = row.get("decision_date")
    title = _text(row.get("title")).casefold()
    if sort == "title":
        return (title, date is None, "")
    # Undated decisions sort last either way rather than pretending to be oldest.
    if sort == "oldest":
        return (date is None, date.isoformat() if date else "", title)
    return (date is None, "" if date is None else _reverse_date(date), title)


def _reverse_date(date):
    return f"{9999 - date.year:04d}-{12 - date.month:02d}-{31 - date.day:02d}"


def sort_rows(rows, sort):
    sort = sort if sort in SORTS else "newest"
    return sorted(rows, key=lambda row: _sort_key(row, sort))


def _int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def browse_catalog(rows, *, query="", filters=None, sort="newest", limit=25, offset=0):
    """Page, facet counts, and applied narrowing for one catalog request."""
    filters = filters or {}
    searched = search_rows(rows, query)
    matched = apply_filters(searched, filters)
    ordered = sort_rows(matched, sort)
    limit = max(1, min(_int(limit, 25), 100))
    offset = max(0, _int(offset, 0))
    page = ordered[offset:offset + limit]
    return {
        "ids": [row["id"] for row in page],
        "facets": facet_counts(searched, filters),
        "total": len(ordered),
        "corpusTotal": len(rows),
        "limit": limit,
        "offset": offset,
        "sort": sort if sort in SORTS else "newest",
        "filters": {facet: list(values) for facet, values in filters.items()},
        "facetLabels": FACET_LABELS,
    }
