"""Recognizing a citation in a research query and saying what it could look like in text.

Citation search has to be predictable: an advocate who types ``R.C. 5321.04``
expects every section that carries it, and one who types ``2020-Ohio-1234``
expects that decision, not decisions that merely share the year. Neither is a
relevance judgement, so neither is left to ranking.

A citation is therefore parsed into a canonical form plus the literal spellings
the same authority is written under. The variants are what retrieval searches
for, because a corpus written by many hands spells one section
``R.C. 5321.04``, ``O.R.C. 5321.04``, ``Ohio Rev. Code 5321.04`` and
``Section 5321.04`` on different pages. Matching the canonical form alone would
report the missing spellings as an absence of law.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Citation:
    kind: str
    normalized: str
    matched_text: str
    variants: tuple = field(default_factory=tuple)

    def to_dict(self):
        return {
            "kind": self.kind,
            "normalized": self.normalized,
            "matchedText": self.matched_text,
            "variants": list(self.variants),
        }


def _unique(values):
    return tuple(dict.fromkeys(value for value in values if value))


def _revised_code(match):
    section = match.group("section")
    subdivision = (match.group("subdivision") or "").replace(" ", "")
    normalized = f"R.C. {section}{subdivision}"
    return Citation(
        kind="revised_code",
        normalized=normalized,
        matched_text=match.group(0).strip(),
        # The bare section number is a variant because statutory text cites its
        # neighbours as "division (B) of section 5321.04", with no reporter
        # prefix anywhere on the page.
        variants=_unique([
            f"R.C. {section}",
            f"R.C. §{section}",
            f"R.C. § {section}",
            f"O.R.C. {section}",
            f"Ohio Rev. Code {section}",
            f"Ohio Revised Code {section}",
            f"Revised Code {section}",
            f"section {section}",
            section,
        ]),
    )


def _ohio_public_domain(match):
    year, number = match.group("year"), match.group("number").lstrip("0") or "0"
    normalized = f"{year}-Ohio-{number}"
    return Citation(
        kind="ohio_public_domain",
        normalized=normalized,
        matched_text=match.group(0).strip(),
        variants=_unique([normalized, f"{year} Ohio {number}", f"{year}-ohio-{number}"]),
    )


def _reporter(match):
    volume, series, page = match.group("volume"), match.group("series"), match.group("page")
    reporter = re.sub(r"\s+", " ", match.group("reporter").strip())
    edition = (series or "").strip()
    canonical = f"{volume} {reporter}{edition} {page}" if edition else f"{volume} {reporter} {page}"
    return Citation(
        kind="reporter",
        normalized=re.sub(r"\s+", " ", canonical),
        matched_text=match.group(0).strip(),
        variants=_unique([
            canonical,
            f"{volume} {reporter} {edition} {page}".replace("  ", " ") if edition else canonical,
            f"{volume} {reporter.replace('. ', '.')}{edition} {page}",
        ]),
    )


def _federal_code(match):
    title, section = match.group("title"), match.group("section")
    body = match.group("body").upper().replace(" ", "")
    label = {"USC": "U.S.C.", "U.S.C.": "U.S.C.", "CFR": "C.F.R.", "C.F.R.": "C.F.R."}.get(body, body)
    normalized = f"{title} {label} {section}"
    return Citation(
        kind="federal_code",
        normalized=normalized,
        matched_text=match.group(0).strip(),
        variants=_unique([
            normalized,
            f"{title} {label} § {section}",
            f"{title} {label} §{section}",
            f"{title} {label.replace('.', '')} {section}",
        ]),
    )


# Ordered most specific first: a public-domain cite contains a bare year, and a
# reporter cite contains a bare volume number, so the loose patterns must not
# see the text first.
_PATTERNS = (
    (re.compile(r"\b(?P<year>(?:19|20)\d{2})[-\s]ohio[-\s](?P<number>\d{1,6})\b", re.I), _ohio_public_domain),
    (
        re.compile(
            r"\b(?:o\.?\s?r\.?\s?c\.?|ohio\s+rev(?:ised)?\.?\s+code(?:\s+ann\.?)?|r\.\s?c\.)\s*"
            r"(?:§+\s*)?(?P<section>\d{3,4}\.\d{1,3})(?P<subdivision>(?:\s*\([A-Za-z0-9]{1,3}\))*)",
            re.I,
        ),
        _revised_code,
    ),
    (
        re.compile(
            r"\b(?P<title>\d{1,2})\s+(?P<body>u\.?\s?s\.?\s?c\.?|c\.?\s?f\.?\s?r\.?)\s*"
            r"(?:§+\s*)?(?P<section>\d+[a-z]?(?:\.\d+)?(?:\([a-z0-9]{1,3}\))*)",
            re.I,
        ),
        _federal_code,
    ),
    (
        re.compile(
            r"\b(?P<volume>\d{1,4})\s+(?P<reporter>ohio\s+st\.?|ohio\s+app\.?|ohio\s+misc\.?|ohio|"
            r"n\.\s?e\.|f\.\s?supp\.?|f\.|u\.\s?s\.)\s*(?P<series>\d\s?d|\d\s?th)?\s+(?P<page>\d{1,5})\b",
            re.I,
        ),
        _reporter,
    ),
)


def find_citations(text):
    """Every citation in ``text``, longest match first, without overlaps."""
    consumed = []
    found = []
    for pattern, build in _PATTERNS:
        for match in pattern.finditer(str(text or "")):
            span = match.span()
            if any(span[0] < end and start < span[1] for start, end in consumed):
                continue
            consumed.append(span)
            found.append(build(match))
    return found


def strip_citations(text, citations):
    """Remove matched citation text so its digits do not also rank as loose terms."""
    remaining = str(text or "")
    for citation in citations:
        remaining = remaining.replace(citation.matched_text, " ")
    return remaining
