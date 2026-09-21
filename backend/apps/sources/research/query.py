"""Parsing a research query into the parts a deterministic index can answer.

Research mode promises that a lawyer can tell why a result came back. That
starts here: a query is split into exact phrases, citations, field filters and
loose terms *before* anything is scored, and the parse is returned to the caller
alongside the results. A search that quietly dropped half of what was typed --
because a quotation mark was unbalanced, or a field name was misspelt -- would
report an absence of law that is really an absence of parsing.

Nothing in this module calls a model, and the same string always parses the
same way.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from apps.sources.research.citations import find_citations, strip_citations


# Words that carry no retrieval signal in a legal corpus where nearly every
# document contains them. Kept deliberately small: "notice", "service" and
# "party" look like noise and are terms of art.
STOPWORDS = frozenset({
    "about", "after", "against", "all", "also", "and", "any", "are", "been", "but", "can", "did",
    "does", "for", "from", "had", "has", "have", "how", "into", "its", "may", "must", "not", "now",
    "off", "one", "only", "our", "out", "over", "own", "per", "she", "such", "than", "that", "the",
    "their", "them", "then", "there", "these", "they", "this", "those", "through", "under", "upon",
    "use", "was", "were", "what", "when", "where", "which", "who", "why", "will", "with", "would",
    "you", "your",
})

# A section number is one token: splitting "5321.04" into "5321" and "04" makes
# every section in chapter 5321 an equally good match for one of them.
_TOKEN = re.compile(r"[a-z]+|\d+(?:\.\d+)+|\d+")

FIELDS = {
    "court": "court",
    "county": "county",
    "municipality": "municipality",
    "city": "municipality",
    "district": "appellateDistrict",
    "year": "year",
    "status": "publicationStatus",
    "published": "publicationStatus",
    "source": "sourceType",
    "sourcetype": "sourceType",
    "corpus": "sourceType",
    "type": "sourceType",
    "title": "title",
    "judge": "judge",
    "document": "documentSlug",
}

_FIELD_TERM = re.compile(r'(?P<negate>-?)(?P<field>[a-z]+):(?P<value>"[^"]*"|\S+)', re.I)
_PHRASE = re.compile(r'"([^"]+)"')


def tokenize(text):
    """Index and query tokens, casefolded, with section numbers kept whole."""
    return _TOKEN.findall(str(text or "").casefold())


def index_tokens(text):
    """Tokens as stored in the index.

    A dotted section number is stored under both its whole form and its chapter
    so that ``5321.04`` and ``5321`` each find the section, without ``5321``
    dissolving into every four-digit number in the corpus.
    """
    tokens = []
    for token in tokenize(text):
        tokens.append(token)
        if "." in token:
            tokens.append(token.split(".", 1)[0])
    return tokens


def content_terms(tokens):
    return [token for token in tokens if len(token) > 2 and token not in STOPWORDS]


@dataclass(frozen=True)
class ParsedQuery:
    raw: str
    terms: tuple = field(default_factory=tuple)
    phrases: tuple = field(default_factory=tuple)
    citations: tuple = field(default_factory=tuple)
    filters: tuple = field(default_factory=tuple)
    excluded: tuple = field(default_factory=tuple)
    warnings: tuple = field(default_factory=tuple)

    @property
    def is_empty(self):
        return not (self.terms or self.phrases or self.citations or self.filters)

    @property
    def is_exact(self):
        """True when the query names what it wants rather than describing it.

        An exact query must not be broadened by concept expansion: a lawyer who
        quotes a phrase or types a citation is asking whether the corpus
        contains that, and a near neighbour is a wrong answer, not a helpful one.
        """
        return bool(self.phrases or self.citations)

    def filter_values(self, field_name):
        return tuple(value for name, value in self.filters if name == field_name)

    def to_dict(self):
        return {
            "raw": self.raw,
            "terms": list(self.terms),
            "phrases": list(self.phrases),
            "citations": [citation.to_dict() for citation in self.citations],
            "filters": [{"field": name, "value": value} for name, value in self.filters],
            "excluded": list(self.excluded),
            "warnings": list(self.warnings),
            "isExact": self.is_exact,
        }


def parse_query(text):
    """Split a typed query into phrases, citations, field filters and terms."""
    raw = str(text or "")
    warnings = []
    working = raw

    if working.count('"') % 2:
        warnings.append('An unmatched quotation mark was ignored; only balanced "..." is read as an exact phrase.')
        # The *last* quote is the unmatched one, whichever end the query starts
        # at. Dropping the first instead re-pairs every quote after it, so
        # `"notice to leave" rent "habit` came out asking for the exact phrase
        # `rent` -- a different search, run under a warning that said the mark
        # had been ignored.
        working = "".join(working.rsplit('"', 1))

    filters = []
    excluded_filters = []

    def _take_field(match):
        name = FIELDS.get(match.group("field").casefold())
        if not name:
            return match.group(0)
        value = match.group("value").strip('"').strip()
        if not value:
            return " "
        (excluded_filters if match.group("negate") else filters).append((name, value))
        return " "

    working = _FIELD_TERM.sub(_take_field, working)
    if excluded_filters:
        warnings.append("Negated field filters are not supported yet and were ignored.")

    phrases = tuple(dict.fromkeys(
        " ".join(phrase.split()) for phrase in _PHRASE.findall(working) if phrase.strip()
    ))
    working = _PHRASE.sub(" ", working)

    citations = tuple(find_citations(working))
    working = strip_citations(working, citations)

    excluded = []
    kept = []
    for word in working.split():
        if word.startswith("-") and len(word) > 1:
            excluded.extend(content_terms(tokenize(word[1:])))
        else:
            kept.append(word)

    # Phrase words rejoin the loose terms so a phrase query still ranks; the
    # phrase itself is applied as a filter on top of that ranking.
    terms = content_terms(tokenize(" ".join([*kept, *phrases])))
    return ParsedQuery(
        raw=raw,
        terms=tuple(dict.fromkeys(terms)),
        phrases=phrases,
        citations=citations,
        filters=tuple(filters),
        excluded=tuple(dict.fromkeys(excluded)),
        warnings=tuple(warnings),
    )
