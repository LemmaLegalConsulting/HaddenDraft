"""Counting what a result set could be narrowed to.

A facet count is taken with every *other* active filter applied but not its own,
which is what makes a facet list usable: once a reader has narrowed to Cuyahoga
County, the county list still has to show the counties they could switch to
rather than collapsing to the one they picked.

Values are compared after the same punctuation-insensitive normalization the
rest of the application uses for court and county names, because one corpus
writes ``Cleveland Municipal Court, Housing Division`` where another writes it
with a hyphen.
"""

from __future__ import annotations

from apps.core.jurisdictions import canonical_county, county_profile
from apps.sources import jurisdiction as jurisdiction_matching
from apps.sources.research.corpus import CORPUS_LABELS


# Fields a reader narrows by, in the order they are offered.  ``exact`` fields
# hold a controlled value; the others hold names that arrive spelled several
# ways, so a filter on them is a contains-match.
FACET_FIELDS = (
    ("sourceType", "Source type", True),
    ("court", "Court", False),
    ("county", "County", False),
    ("appellateDistrict", "Appellate district", True),
    ("municipality", "Municipality", False),
    ("year", "Year", True),
    ("publicationStatus", "Publication status", True),
    ("judge", "Judge", False),
)

FILTER_ONLY_FIELDS = ("title", "documentSlug")

_EXACT_FIELDS = {name for name, _label, exact in FACET_FIELDS if exact} | {"documentSlug"}

_VALUE_LABELS = {"sourceType": CORPUS_LABELS}


def facet_fields():
    return [{"field": name, "label": label, "exact": exact} for name, label, exact in FACET_FIELDS]


def value_label(field, value):
    return _VALUE_LABELS.get(field, {}).get(value, value)


def matches(field, record_value, wanted):
    """Whether one record's value satisfies one requested filter value."""
    if not wanted:
        return True
    if field in _EXACT_FIELDS:
        return str(record_value or "").casefold() == str(wanted).casefold()
    if field == "county" and county_profile(wanted):
        # A county the vocabulary recognizes is compared as a county, so
        # `county:"Cuyahoga County"` finds the records stored as "Cuyahoga".
        # A value it does not recognize -- an out-of-state county, or a reader
        # part-way through typing one -- falls through to the contains match
        # below, which is what makes `county:cuyah` still work.
        return canonical_county(record_value) == canonical_county(wanted)
    return jurisdiction_matching.matches(wanted, record_value or "")


def _passes(record, field, values):
    return not values or any(matches(field, record.facets.get(field, ""), value) for value in values)


def apply(records, filters, *, skip_field=None):
    """Records satisfying every filter except, optionally, one field's."""
    active = [
        (field, values) for field, values in filters.items()
        if values and field != skip_field
    ]
    if not active:
        return list(records)
    return [record for record in records if all(_passes(record, field, values) for field, values in active)]


def counts(records, filters):
    """Facet lists for a result set, each counted without its own filter."""
    facets = []
    for field, label, exact in FACET_FIELDS:
        scoped = apply(records, filters, skip_field=field)
        tally = {}
        unattributed = 0
        for record in scoped:
            value = str(record.facets.get(field, "") or "").strip()
            if not value:
                unattributed += 1
                continue
            tally[value] = tally.get(value, 0) + 1
        values = sorted(
            ({"value": value, "label": value_label(field, value), "count": count} for value, count in tally.items()),
            key=lambda item: (-item["count"], item["value"]),
        )
        facets.append({
            "field": field,
            "label": label,
            "exact": exact,
            "values": values,
            "selected": list(filters.get(field) or []),
            # Reported rather than dropped: a facet that silently omits the
            # records with no value for it makes the counts fail to add up, and
            # "no county recorded" is itself something a reader may want to see.
            "unattributed": unattributed,
        })
    return facets
