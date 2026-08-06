"""Punctuation-insensitive jurisdiction matching.

A matter records its jurisdiction as a human types it; a legal source records
its own the way the publisher wrote it. The same court reaches us as
``Cleveland Municipal Court - Housing Division`` from one and
``Cleveland Municipal Court, Housing Division, Cuyahoga County, Ohio`` from the
other. A literal ``icontains`` treats those as unrelated, which silently removes
a whole source from a search rather than merely ranking it lower.

So both sides are reduced to letters and digits before they are compared:
punctuation, spacing, and case stop mattering. Nothing else about the comparison
changes -- it is still "does the source's jurisdiction contain the one we are
searching for", so ``Ohio`` still matches every Ohio court, and a jurisdiction
from a different state still matches nothing.

Two deliberate choices:

* **Normalization happens in Python, not SQL.** Spelling it as a database
  expression means a chain of REPLACE calls, one per stripped character, because
  SQLite has no ``regexp_replace`` and local development runs on SQLite. SQLite's
  parser overflows at roughly twenty nested calls across three fields, so that
  form would break by adding a field or a character -- and it would break as a
  500 at request time, not as a failing test. Doing it here also guarantees that
  a filter and a relevance boost can never disagree about what matches.

* **The comparison removes spaces as well as punctuation**, so in principle a
  needle could straddle a word boundary in the haystack. Court and county names
  make that vanishingly unlikely, and the alternative -- collapsing runs of
  whitespace -- reintroduces exactly the spacing sensitivity being removed.
"""

import re
from functools import lru_cache


_INSIGNIFICANT = re.compile(r"[^0-9a-z]+")


@lru_cache(maxsize=4096)
def normalize(value):
    """Reduce a jurisdiction string to the form used for comparison.

    Cached because a search compares one needle against the same few dozen
    court, county, and jurisdiction strings over and over.
    """
    return _INSIGNIFICANT.sub("", (value or "").casefold())


def matches(needle, *haystacks):
    """True when any haystack contains ``needle``, ignoring punctuation and case.

    A needle that is empty, or that is nothing but punctuation, matches nothing.
    Callers that mean "no jurisdiction given, so search everywhere" must check
    for that themselves rather than relying on this to wave everything through.
    """
    normalized_needle = normalize(needle)
    if not normalized_needle:
        return False
    return any(normalized_needle in normalize(haystack) for haystack in haystacks)


def is_usable(jurisdiction):
    """True when ``jurisdiction`` carries enough signal to narrow a search."""
    return bool(normalize(jurisdiction))
