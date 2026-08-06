"""Punctuation-insensitive jurisdiction comparison.

A matter records its jurisdiction as a person types it; a legal source records
its own the way the publisher wrote it. The same court reaches us as
``Cleveland Municipal Court - Housing Division`` from one and
``Cleveland Municipal Court, Housing Division, Cuyahoga County, Ohio`` from the
other. Compared literally, those look unrelated.

So both sides are reduced to letters and digits before they are compared:
punctuation, spacing, and case stop mattering. The comparison itself is
unchanged -- it still asks whether the source's jurisdiction contains the one
being looked for, so ``Ohio`` matches every Ohio court and another state matches
nothing.

This decides *ranking*, not membership. Trial-court decisions are persuasive
rather than binding, so where one was decided nudges its position in a result
list; it never removes it. A silent punctuation mismatch would still be a bug,
because it would quietly drop the nudge that puts a lawyer's own court first.

Normalization is done in Python rather than as a query expression. In SQL it is
a chain of REPLACE calls, one per stripped character, because SQLite has no
``regexp_replace`` and local development runs on SQLite; SQLite's parser
overflows at roughly twenty nested calls across three fields, so that form would
break by adding a field or a character, and it would break at request time
rather than in a test.

One consequence of removing spaces along with punctuation: a needle could in
principle straddle a word boundary in the haystack. Court and county names make
that vanishingly unlikely, and collapsing runs of whitespace instead would
reintroduce exactly the spacing sensitivity being removed.
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

    A needle that is empty, or that is nothing but punctuation, matches nothing:
    "no jurisdiction given" is not a reason to hand out a relevance bonus.
    """
    normalized_needle = normalize(needle)
    if not normalized_needle:
        return False
    return any(normalized_needle in normalize(haystack) for haystack in haystacks)
