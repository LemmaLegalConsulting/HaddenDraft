"""Finding the authorities a filing cites, for its table of authorities.

This reads text and says where each citation is and which authority it names.
It writes nothing: `apps.exporting.table_of_authorities` turns what it finds
into Word TA fields. Keeping the two apart keeps the reading testable on plain
strings and lets validation report the same list the export will mark.

A table of authorities is only as good as its marks, and the two ways it goes
wrong are not equally visible. An authority listed twice under two spellings
looks sloppy and is caught on read-through. An authority silently left out
looks like a complete table. So every recognized citation of one authority is
grouped under the key of its first full citation, and anything that looks like
a citation but could not be tied to an authority is reported rather than
dropped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

import yaml

from apps.core.content_library import content_path
from apps.sources.research.citations import find_citation_spans


CONFIG_PATH = ("drafting-rules", "table-of-authorities.yaml")

# Signals and sentence openers that precede a case name without being part of
# it: "See Dresher v. Burt" names Dresher v. Burt.
_LEADING_WORDS = {
    "see", "also", "accord", "cf.", "but", "compare", "contra", "e.g.,", "e.g.",
    "citing", "quoting", "in", "under", "as", "the", "and", "similarly", "here",
    "like", "unlike", "because", "although", "following", "applying", "discussing",
}
# Lower-case words that may sit inside a case name.
_NAME_CONNECTORS = {
    "of", "the", "and", "for", "de", "du", "la", "in", "on", "to", "at", "ex", "rel.",
    "&", "v.", "et", "al.", "al.,",
}
# What sits between a case name and its reporter citation in Ohio's form:
# "Rowan v. McLaughlin, 8th Dist. Cuyahoga No. 85665, 2005-Ohio-3473".
_VERSUS_RE = re.compile(r"\sv\.?\s")
_DOCKET_RE = re.compile(
    r"(?:,\s*)?(?P<docket>\d{1,2}(?:st|nd|rd|th)\s+Dist\.\s+(?:[A-Z][a-z]+\s+)?(?:Case\s+)?Nos?\.\s+[\w-]+(?:\s*,\s*[\w-]+)*)\s*,\s*$"
)
_YEAR_BEFORE_CITE_RE = re.compile(r"\s*\((?:1[89]|20)\d{2}\)$")
# Between two cites of one decision: a comma, optionally after a pinpoint.
_PARALLEL_GAP_RE = re.compile(r"^(?:,\s*(?:¶+\s*|at\s+|\*)?\d+(?:[-–]\d+)?)*,\s*$")
# After a cite: pinpoints, then an optional parenthetical naming court or year.
_PINPOINTS_RE = re.compile(r"^(?:,?\s*(?:¶+\s*|at\s+|\*)\d+(?:[-–]\d+)?|,\s*\d+(?:[-–]\d+)?(?=[\s,;.)]|$))*")
# An explanatory or subsequent-history parenthetical ("(overruled on other
# grounds by ...)", "(citing ...)") opens with a lower-case word and is not
# part of the table entry; a court-and-year parenthetical never does.
_PARENTHETICAL_RE = re.compile(r"^\s*\((?P<paren>(?![a-z])[^()]{0,120}?(?:\b(?:1[89]|20)\d{2}\b|Dist\.|Cir\.|App\.)[^()]{0,40}?)\)")
# "Younger, 639 N.E.2d at 1256": a short form that names the reporter again.
_SHORT_FORM_RE = re.compile(
    r"\b(?P<volume>\d{1,4})\s+(?P<reporter>Ohio\s+St\.\s?[23]d|Ohio\s+App\.\s?[23]d|Ohio\s+Misc\.\s?[23]d|"
    r"N\.E\.\s?[23]d|F\.\s?(?:Supp\.\s?)?[234]?d?|U\.S\.|S\.\s?Ct\.)\s+at\s+\*?\d+"
)
# Forms that point at an authority without naming one. They are left unmarked
# and reported, never guessed.
# A decision cited only by docket number has no reporter cite to key it on.
# Such a case is reported rather than guessed at.
_DOCKET_ONLY_RE = re.compile(
    r"(?:[A-Z0-9][\w.&'’-]*,?\s+(?:(?:of|the|and|for|ex|rel\.|&)\s+)*)+v\.?\s+[^;()]{1,100}?,"
    r"\s*[^;()]{0,60}?(?:Case\s+)?No\.\s+[^\s,;]+"
)
_UNNAMED_FORM_RE = re.compile(r"\b(?:Id\.|id\.|Ibid\.|supra)(?=[\s,;.]|$)")
_SUBDIVISION_RE = re.compile(r"(?:\s?\([A-Za-z0-9]{1,4}\))+$")


@dataclass
class Authority:
    key: str
    category: str
    long_cite: str
    short_cite: str
    # Span of the case name within ``long_cite``; Word italicizes it in the table.
    italic: tuple | None = None
    name_found: bool = True
    occurrences: int = 0

    def as_dict(self):
        return {
            "key": self.key,
            "category": self.category,
            "longCite": self.long_cite,
            "shortCite": self.short_cite,
            "nameFound": self.name_found,
            "occurrences": self.occurrences,
        }


@dataclass
class Occurrence:
    """One place to mark: after ``end``, the citation of ``key`` finishes."""

    start: int
    end: int
    key: str
    first: bool = False
    # Where the case name sits in the paragraph, when it is written out in full.
    name_span: tuple | None = None


@dataclass
class AuthorityRegistry:
    """The authorities one document cites, in the order they first appear."""

    config: dict
    authorities: dict = field(default_factory=dict)
    aliases: dict = field(default_factory=dict)
    reporter_volumes: dict = field(default_factory=dict)
    unmarked: list = field(default_factory=list)
    unnamed_references: int = 0

    def resolve(self, key):
        return self.aliases.get(key, key)

    def ordered(self):
        return list(self.authorities.values())

    def by_category(self):
        grouped = {}
        for authority in self.authorities.values():
            grouped.setdefault(authority.category, []).append(authority)
        for entries in grouped.values():
            entries.sort(key=lambda item: _sort_key(item.long_cite))
        return grouped

    def report(self):
        unmarked = list(self.unmarked)
        if self.unnamed_references:
            unmarked.append(
                {
                    "text": "Id. / supra",
                    "count": self.unnamed_references,
                    "reason": "Refers back without naming an authority. Word's table lists only the "
                    "citations that name one, so these pages are not listed.",
                }
            )
        return {
            "authorities": [authority.as_dict() for authority in self.ordered()],
            "unmarked": unmarked,
            "pageNumbers": "unmeasured",
            "pageNumbersReason": (
                "Page numbers are filled in by Word when it updates the table's fields. "
                "Nothing here renders the document, so no page number is computed or checked."
            ),
        }


def _sort_key(text):
    # Word sorts a table alphabetically, ignoring case and leading punctuation.
    return re.sub(r"^[^A-Za-z0-9]+", "", text).casefold()


@lru_cache(maxsize=4)
def _load_config(path_str, _mtime):
    with open(path_str, encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    data["_patterns"] = [
        {**row, "compiled": re.compile(row["regex"])} for row in data.get("patterns") or []
    ]
    data["_case_patterns"] = [
        {**row, "compiled": re.compile(row["regex"])} for row in data.get("case_patterns") or []
    ]
    return data


def load_config():
    path = content_path(*CONFIG_PATH)
    return _load_config(str(path), path.stat().st_mtime)


def category_numbers(config=None):
    config = config or load_config()
    return {row["key"]: int(row["number"]) for row in config.get("categories") or []}


def _category_for_parsed(citation, config):
    mapping = (config.get("parser_kinds") or {}).get(citation.kind)
    if isinstance(mapping, dict):
        for label, category in (mapping.get("by_label") or {}).items():
            if f" {label} " in f" {citation.normalized} ":
                return category
        return None
    return mapping


def _strip_leading_words(tokens):
    while tokens:
        word = tokens[0]
        lowered = word.casefold()
        if lowered == "in" and len(tokens) > 1 and tokens[1].casefold() == "re":
            break
        if (
            lowered in _LEADING_WORDS
            or re.fullmatch(r"\d+,", word)
            or not (word[:1].isupper() or word[:1].isdigit())
        ):
            tokens = tokens[1:]
            continue
        break
    return tokens


def _case_name_before(text, start):
    """The case name that ends just before ``start``, and what joins it to the cite.

    Returns ``(name, joiner)``. ``joiner`` is ``", "`` for the common form, or
    carries the docket (", 8th Dist. Cuyahoga No. 85665, ") or the older Ohio
    year (" (1990), ") that sits between name and cite. ``name`` is empty when
    none is found; the citation is still marked, under its reporter cite, and
    reported, so the table never silently loses it.
    """
    prefix = text[max(0, start - 240):start]
    joiner = ", "
    docket_match = _DOCKET_RE.search(prefix)
    if docket_match:
        joiner = f", {docket_match.group('docket')}, "
        prefix = prefix[: docket_match.start()]
    else:
        stripped = re.sub(r",\s*$", "", prefix)
        if stripped == prefix:
            return "", ""
        prefix = stripped
    # The older Ohio form puts the year between name and cite:
    # "Rispo Realty v. Parma (1990), 55 Ohio St.3d 101".
    year_match = _YEAR_BEFORE_CITE_RE.search(prefix)
    if year_match:
        joiner = f" {year_match.group(0).strip()}{joiner}"
        prefix = prefix[: year_match.start()]
    # Only the clause the citation sits in: a name never spans a semicolon,
    # colon, quotation, or an opening parenthesis.
    clause_start = max(prefix.rfind(mark) for mark in (";", ":", "(", ")", "\u201c", '"'))
    clause = prefix[clause_start + 1:]
    versus = [match.start() for match in _VERSUS_RE.finditer(clause)]
    in_re = re.search(r"\bIn re\s", clause)
    if not versus and not in_re:
        return "", ""
    if not versus:
        return re.sub(r"\s+", " ", clause[in_re.start():]).strip(" ,"), joiner
    anchor = versus[-1]
    # Walk back from "v." while the words read as a party name.
    kept = []
    for word in reversed(clause[:anchor].split()):
        bare = word.strip(",")
        if not (bare[:1].isupper() or bare[:1].isdigit() or bare.casefold() in _NAME_CONNECTORS):
            break
        kept.insert(0, word)
    kept = _strip_leading_words(kept)
    if not kept:
        return "", ""
    name = re.sub(r"\s+", " ", " ".join([*kept, clause[anchor:].strip()])).strip(" ,")
    return name, joiner


def _case_cluster(text, cites, index):
    """Extend the cite at ``index`` over its parallel cites, pinpoints, and parenthetical."""
    citation, (start, end) = cites[index]
    members = [citation]
    last = index
    while last + 1 < len(cites):
        next_citation, (next_start, next_end) = cites[last + 1]
        if not next_citation.get("case"):
            break
        if not _PARALLEL_GAP_RE.match(text[end:next_start]):
            break
        members.append(next_citation)
        end = next_end
        last += 1
    tail = text[end:]
    pinpoints = _PINPOINTS_RE.match(tail)
    consumed = pinpoints.end() if pinpoints else 0
    parenthetical = _PARENTHETICAL_RE.match(tail[consumed:])
    paren = ""
    if parenthetical:
        paren = parenthetical.group("paren").strip()
        consumed += parenthetical.end()
    return members, start, end + consumed, paren, last


def _gather_cites(text, config):
    """Every cite in ``text`` as ``(info, span)``, in reading order, without overlaps."""
    cites = []
    for citation, span in find_citation_spans(text):
        category = _category_for_parsed(citation, config)
        if not category:
            continue
        info = {"category": category, "case": category == "cases", "matched": citation.matched_text}
        if category == "cases":
            info["key"] = citation.normalized
        elif citation.subdivision:
            info["key"] = citation.normalized[: -len(citation.subdivision)].strip()
        else:
            info["key"] = _SUBDIVISION_RE.sub("", citation.normalized).strip()
        if citation.kind == "reporter":
            parts = citation.normalized.split()
            info["volume"] = parts[0]
            info["reporter"] = " ".join(parts[1:-1])
        cites.append((info, span))

    def overlaps(span):
        return any(span[0] < end and start < span[1] for _info, (start, end) in cites)

    for row in config["_case_patterns"]:
        for match in row["compiled"].finditer(text):
            if overlaps(match.span()):
                continue
            key = re.sub(r"\s+", " ", match.group("key"))
            cites.append(({"category": "cases", "case": True, "key": key, "matched": match.group(0)}, match.span()))
    for row in config["_patterns"]:
        for match in row["compiled"].finditer(text):
            if overlaps(match.span()):
                continue
            name = re.sub(r"\s+", " ", match.group("name")).strip()
            # "Civ. R. 12" and "Civ.R. 12" are one rule.
            name = re.sub(r"\.\s+(?=(?:App\.\s?)?R\.)", ".", name)
            cites.append(({"category": row["category"], "case": False, "key": name, "matched": match.group(0)}, match.span()))
    return sorted(cites, key=lambda item: item[1][0])


def _normalize_reporter(reporter):
    return re.sub(r"\s+", "", reporter).casefold()


def find_occurrences(text, registry):
    """The places in one paragraph to mark, registering new authorities as met."""
    config = registry.config
    cites = _gather_cites(text, config)
    occurrences = []
    index = 0
    while index < len(cites):
        info, (start, end) = cites[index]
        if not info["case"]:
            key = registry.resolve(info["key"])
            first = key not in registry.authorities
            if first:
                registry.authorities[key] = Authority(
                    key=key,
                    category=info["category"],
                    long_cite=key,
                    short_cite=key,
                )
            registry.authorities[key].occurrences += 1
            occurrences.append(Occurrence(start=start, end=end, key=key, first=first))
            index += 1
            continue

        members, cluster_start, cluster_end, paren, last = _case_cluster(text, cites, index)
        keys = [member["key"] for member in members]
        name, joiner = _case_name_before(text, cluster_start)
        name_at = text.rfind(name, max(0, cluster_start - 300), cluster_start) if name else -1
        name_span = (name_at, name_at + len(name)) if name_at != -1 else None
        known = next((registry.resolve(key) for key in keys if registry.resolve(key) in registry.authorities), None)
        if known:
            key = known
            first = False
        else:
            key = keys[0]
            first = True
            cite_text = ", ".join(re.sub(r"\s+", " ", member["matched"]) for member in members)
            body = f"{cite_text} ({paren})" if paren else cite_text
            long_cite = f"{name}{joiner}{body}" if name else body
            first_party = re.split(r"\s+v\.\s+", name)[0] if name else ""
            registry.authorities[key] = Authority(
                key=key,
                category="cases",
                long_cite=long_cite,
                short_cite=f"{first_party}, {key}" if first_party else key,
                italic=(0, len(name)) if name else None,
                name_found=bool(name),
            )
            if not name:
                registry.unmarked.append(
                    {
                        "text": cite_text,
                        "reason": "Marked without a case name: no name was found before the citation. "
                        "Check this entry in the table.",
                    }
                )
        for member in members:
            registry.aliases.setdefault(member["key"], key)
            if member.get("volume"):
                registry.reporter_volumes.setdefault(
                    (member["volume"], _normalize_reporter(member["reporter"])), set()
                ).add(key)
        registry.authorities[key].occurrences += 1
        occurrences.append(
            Occurrence(start=cluster_start, end=cluster_end, key=key, first=first, name_span=name_span)
        )
        index = last + 1

    marked_spans = [(item.start, item.end) for item in occurrences]
    for match in _SHORT_FORM_RE.finditer(text):
        if any(match.start() < end and start < match.end() for start, end in marked_spans):
            continue
        candidates = registry.reporter_volumes.get((match.group("volume"), _normalize_reporter(match.group("reporter"))), set())
        if len(candidates) == 1:
            key = next(iter(candidates))
            registry.authorities[key].occurrences += 1
            occurrences.append(Occurrence(start=match.start(), end=match.end(), key=key))
        else:
            registry.unmarked.append(
                {
                    "text": match.group(0),
                    "reason": (
                        "Ambiguous short form: multiple decisions share this reporter volume. Mark it in Word."
                        if candidates else "Short form of a decision not cited in full earlier in the document."
                    ),
                }
            )
    for match in _DOCKET_ONLY_RE.finditer(text):
        after = text[match.end():match.end() + 40]
        if any(match.start() <= item.start <= match.end() + 40 for item in occurrences) or re.match(r"\s*,\s*\d", after):
            continue
        registry.unmarked.append(
            {
                "text": " ".join(_strip_leading_words(match.group(0).split())),
                "reason": "Cited by docket number without a reporter citation, so it was not marked. "
                "Mark it in Word (Alt+Shift+I) if it belongs in the table.",
            }
        )
    registry.unnamed_references += len(_UNNAMED_FORM_RE.findall(text))
    return sorted(occurrences, key=lambda item: item.end)


def collect_authorities(paragraphs, config=None):
    """Read a sequence of paragraph texts and return the registry and per-paragraph marks."""
    registry = AuthorityRegistry(config=config or load_config())
    marks = [find_occurrences(text, registry) for text in paragraphs]
    return registry, marks
