"""Finding dates in OCR'd decision text, and saying where each one came from.

Metadata sidecars carry dates a model read out of these documents.  A date with
no way back to the page it came from is not checkable, and this corpus is
scanned trial-court paper: the OCR splits digits ("MAR 1 6 2005"), drops
punctuation, and turns years into letters.  So the text is scanned for date-like
strings with the wording around them preserved, and a sidecar date counts as
corroborated only when it is actually found in the text.

Nothing here decides what a date *means* on its own.  A file stamp, a hearing
date, and the date a judge signed an entry all look alike in raw text; the
context word next to the match is recorded so a person can tell them apart.
"""

from __future__ import annotations

import re
from datetime import date

MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2, "febr": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

# Words a court puts next to a date. The match itself cannot tell a file stamp
# from a hearing date, so the nearest label is kept with it.
CONTEXT_LABELS = [
    ("filed", "filed"),
    ("journalized", "entry"),
    ("journal entry", "entry"),
    ("entered", "entry"),
    ("received", "received"),
    ("date:", "dated"),
    ("dated", "dated"),
    ("decided", "decided"),
    ("rendered", "decided"),
    ("hearing", "hearing"),
    ("heard", "hearing"),
    ("trial", "hearing"),
    ("served", "service"),
    ("service", "service"),
    ("mailed", "service"),
    ("signed", "dated"),
]

# A clerk's stamp carries no label word, but its shape is the label: a bare
# "2009 FEB 17" on a court document is when the document was filed.
STAMP_LABEL = "filed"

CONTEXT_WINDOW = 60

# The day may carry an internal space where OCR split the digits, and the
# separators may be missing entirely.
_MONTH_NAMES = "|".join(sorted(MONTHS, key=len, reverse=True))
LONG_FORM = re.compile(
    rf"\b(?P<month>{_MONTH_NAMES})\b\.?,?\s{{0,3}}"
    r"(?P<day>\d\s?\d?)\s{0,3}(?:st|nd|rd|th)?\s{0,3},?\s{0,3}"
    r"(?P<year>(?:19|20)\s?\d\s?\d)\b",
    re.IGNORECASE,
)
DAY_FIRST = re.compile(
    rf"\b(?P<day>\d\s?\d?)(?:st|nd|rd|th)?\s{{1,3}}(?:day\s+of\s+)?(?P<month>{_MONTH_NAMES})\b\.?,?\s{{0,3}}"
    r"(?P<year>(?:19|20)\s?\d\s?\d)\b",
    re.IGNORECASE,
)
# The clerk's stamp, which is where a trial-court decision date usually is:
# "2009 FEB 17 PM 2:47". Year first, and the day often split by the scan.
YEAR_FIRST = re.compile(
    rf"\b(?P<year>(?:19|20)\d{{2}})\s{{1,3}}(?P<month>{_MONTH_NAMES})\b\.?\s{{1,3}}"
    r"(?P<day>\d\s?\d?)\b",
    re.IGNORECASE,
)
NUMERIC = re.compile(
    r"(?<![\d/-])(?P<month>\d{1,2})\s{0,2}[/-]\s{0,2}(?P<day>\d{1,2})\s{0,2}[/-]\s{0,2}(?P<year>\d{2,4})(?![\d/-])"
)
ISO = re.compile(r"(?<!\d)(?P<year>(?:19|20)\d{2})-(?P<month>\d{1,2})-(?P<day>\d{1,2})(?!\d)")


def _digits(value):
    return re.sub(r"\s+", "", value or "")


def _year(value):
    text = _digits(value)
    if len(text) == 4:
        return int(text)
    if len(text) == 2:
        number = int(text)
        # Trial-court paper in this corpus runs from the 1970s forward; a
        # two-digit year past the current century reads as the 1900s.
        return 1900 + number if number > 30 else 2000 + number
    return None


def _build(year, month, day):
    if not year or not month or not day:
        return None
    if not (1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31):
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _context_label(text, start, end):
    """The label word nearest the date, from within its own sentence.

    Windows stop at sentence boundaries. Without that, "heard August 12, 1991.
    Journalized October 25, 1991." labels the hearing date as an entry, because
    the next sentence's word is closer than the current one's.
    """
    before = text[max(0, start - CONTEXT_WINDOW):start].casefold()
    before = re.split(r"[.;\n]", before)[-1]
    after = re.split(r"[.;\n]", text[end:end + 20].casefold())[0]
    for needle, label in CONTEXT_LABELS:
        if needle in before:
            return label
    for needle, label in CONTEXT_LABELS:
        if needle in after:
            return label
    return ""


def _snippet(text, start, end, *, width=70):
    left = max(0, start - width)
    right = min(len(text), end + width)
    return re.sub(r"\s+", " ", text[left:right]).strip()


def scan_dates(text):
    """Every date-like string in OCR'd text, with where and how it was read.

    Overlapping matches from different patterns are kept once, preferring the
    earliest start, so a long-form date is not also reported as a numeric one.
    """
    if not text:
        return []
    found = {}
    for pattern, kind in (
        (ISO, "iso"),
        (YEAR_FIRST, "file-stamp"),
        (LONG_FORM, "long-form"),
        (DAY_FIRST, "day-first"),
        (NUMERIC, "numeric"),
    ):
        for match in pattern.finditer(text):
            groups = match.groupdict()
            month = groups["month"]
            month_number = MONTHS.get(month.casefold().rstrip(".")) if not month.isdigit() else int(month)
            value = _build(_year(groups["year"]), month_number, int(_digits(groups["day"]) or 0))
            if not value:
                continue
            span = (match.start(), match.end())
            if any(start < span[1] and span[0] < end for start, end in found):
                continue
            label = _context_label(text, match.start(), match.end())
            found[span] = {
                "value": value,
                "kind": kind,
                "label": label or (STAMP_LABEL if kind == "file-stamp" else ""),
                "matchedText": re.sub(r"\s+", " ", match.group(0)).strip(),
                "start": match.start(),
                "snippet": _snippet(text, match.start(), match.end()),
            }
    return [found[span] for span in sorted(found)]


def corroborate(value, text):
    """The first place a known date appears in the text, or None.

    This is the difference between a date a model asserted and a date a reader
    can check: it returns the page wording that supports it.
    """
    if not value or not text:
        return None
    for candidate in scan_dates(text):
        if candidate["value"] == value:
            return candidate
    return None


def candidates_for(field, scanned):
    """Scanned dates whose surrounding wording suits a particular date field."""
    wanted = {
        "decision_date": {"decided", "dated", "entry", "filed"},
        "entry_date": {"entry", "journalized", "filed"},
        "filed_date": {"filed", "received"},
        "hearing_date": {"hearing"},
        "service_date": {"service"},
    }.get(field, set())
    return [item for item in scanned if item["label"] in wanted]


# The date fields a sidecar can carry, in the order a reader would check them.
PROVENANCE_FIELDS = (
    "decision_date",
    "entry_date",
    "filed_date",
    "hearing_date",
    "service_date",
    "finality_date",
)


def record_date_provenance(decision, metadata, *, source_key="", source_sha256="", text=""):
    """Write one provenance row per date the sidecar carried for this decision.

    Corroboration is against the document's own OCR text, so a date survives as
    checkable rather than merely asserted. Rows are replaced wholesale on a
    re-run: provenance describes the current import, and a stale row claiming a
    page supports a date it no longer carries would be worse than none.
    """
    from apps.caselaw.importing import as_date, as_text, metadata_value
    from apps.caselaw.models import CaseLawDateProvenance

    scanned = scan_dates(text)
    rows = []
    for field in PROVENANCE_FIELDS:
        raw = as_text(metadata_value(metadata, field))
        value = as_date(raw)
        if not value:
            continue
        # A date can appear several times in one document for different
        # reasons. Prefer the occurrence whose surrounding wording suits this
        # field, so the snippet shown to a reader is the supporting passage
        # rather than the first coincidence.
        occurrences = [item for item in scanned if item["value"] == value]
        match = next(
            (item for item in candidates_for(field, occurrences)),
            occurrences[0] if occurrences else None,
        )
        rows.append(CaseLawDateProvenance(
            decision=decision,
            field=field,
            value=value,
            raw_value=raw[:255],
            source="metadata_sidecar",
            source_key=source_key,
            source_sha256=source_sha256,
            corroborated=bool(match),
            page_number=1 if match else None,
            matched_text=(match["matchedText"] if match else "")[:255],
            match_kind=match["kind"] if match else "",
            context_label=match["label"] if match else "",
            snippet=match["snippet"] if match else "",
        ))
    CaseLawDateProvenance.objects.filter(decision=decision).delete()
    CaseLawDateProvenance.objects.bulk_create(rows)
    return rows
