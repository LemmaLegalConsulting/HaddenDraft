"""Showing the passage that matched, and saying which words matched it.

A result list is only useful if a reader can judge relevance without opening
every document, and a snippet taken from the top of a section does not do that.
The window here is placed over the densest cluster of query matches, and the
matched spans come back with it so the interface can mark them.

Expansion hits are marked as such. A reader who sees "defective" highlighted in
a search for "deficient" can tell immediately that the match came from the
thesaurus rather than from their own word, which is the difference between a
result they trust and one they have to re-derive.
"""

from __future__ import annotations

import re


WINDOW = 420


def _needle_positions(haystack, needles):
    positions = []
    for needle in needles:
        if not needle:
            continue
        pattern = re.escape(needle)
        # A short token is bounded so "rent" does not light up "current".
        if len(needle) <= 6 and needle.isalnum():
            pattern = rf"\b{pattern}\b"
        for match in re.finditer(pattern, haystack, re.I):
            positions.append((match.start(), match.end(), needle))
    return sorted(positions)


def _best_window(length, positions, window):
    if not positions:
        return 0
    best_start, best_hits = positions[0][0], 0
    for start_index, (start, _end, _needle) in enumerate(positions):
        end = start + window
        hits = 0
        for other_start, _other_end, _other in positions[start_index:]:
            if other_start >= end:
                break
            hits += 1
        if hits > best_hits:
            best_start, best_hits = start, hits
    return max(0, min(best_start - 80, max(0, length - window)))


def build(text, *, terms=(), phrases=(), citations=(), expansions=(), window=WINDOW):
    """A snippet over the densest match cluster, with the spans that matched it."""
    compact = " ".join(str(text or "").split())
    if not compact:
        return {"text": "", "matches": [], "matchedTerms": [], "matchedExpansions": []}

    # Phrases and citations anchor the window ahead of loose terms: they are
    # what the reader asked for literally.
    anchors = _needle_positions(compact, [*phrases, *citations])
    loose = _needle_positions(compact, terms)
    expansion_hits = _needle_positions(compact, expansions)
    start = _best_window(len(compact), anchors or loose or expansion_hits, window)
    end = min(start + window, len(compact))
    body = compact[start:end]
    # A truncated snippet is returned with a leading "\u2026 ", so every span has
    # to be shifted past it. Returning body-relative offsets alongside a
    # separate correction was the same bug with an extra step: the caller has
    # to remember to apply it, and the one caller did not, so every windowed
    # snippet marked two characters to the left of the words that matched.
    lead = 2 if start else 0

    spans = []
    for kind, found in (("exact", anchors), ("term", loose), ("expansion", expansion_hits)):
        for span_start, span_end, needle in found:
            if span_start >= start and span_end <= end:
                spans.append({
                    "start": span_start - start + lead,
                    "end": span_end - start + lead,
                    "kind": kind,
                    "needle": needle,
                })
    spans.sort(key=lambda span: (span["start"], -span["end"]))

    trimmed = []
    for span in spans:
        if trimmed and span["start"] < trimmed[-1]["end"]:
            continue
        trimmed.append(span)

    return {
        "text": f"{'… ' if start else ''}{body}{' …' if end < len(compact) else ''}",
        # Offsets are into ``text`` above, so the leading ellipsis shifts them.
        "offset": 2 if start else 0,
        "matches": trimmed,
        "matchedTerms": sorted({needle for _s, _e, needle in loose}),
        "matchedExpansions": sorted({needle for _s, _e, needle in expansion_hits}),
    }
