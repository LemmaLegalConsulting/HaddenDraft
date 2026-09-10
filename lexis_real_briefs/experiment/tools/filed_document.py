"""Recover the filed document, and its record, from either delivery shape.

Lexis delivers a filing one of two ways:

  * a .docx carrying a transcription of the filed text (clean, no exhibits), or
  * a .docx that is only a metadata card, with the real filing as a scanned PDF
    that also contains the exhibits filed with it.

For the second shape the scan is transcribed by Azure Document Intelligence (see
ocr_scans.py) and split here into the brief under test and the case record.

## Why this does not use ingestion.split_brief_and_exhibits

The Gym's splitter takes the first page whose opening two lines mention an
exhibit as the start of the attachments. In running prose that fires on an
ordinary inline reference: in the Notarian motion, page 3 begins mid-sentence
with "...See attached Exhibit 2." and the splitter therefore reports a 2-page
brief for a filing whose own footer says "Page 3 of 13". The certificate of
service on page 12 does not rescue it, because the certificate only wins when it
precedes the exhibit marker.

That is a defect worth reporting against the Gym, but it must not silently
decide what a fixture contains, so the rule here is stricter:

  1. the brief ends at the FIRST page bearing a certificate or proof of service --
     the conventional end of the argument, and first rather than last because
     the exhibits behind it are often court filings with certificates of their own;
  2. failing that, at the page before the first exhibit COVER SHEET -- a page
     that is almost nothing but the words "Exhibit A", not a page that mentions
     one;
  3. failing both, at the page cap.

Every filing is recorded with the rule that decided it, so a wrong split is
visible rather than assumed.
"""

import json
import re
from pathlib import Path

CORPUS = Path(__file__).resolve().parents[3] / "lexis_real_briefs"
OUT = CORPUS / "experiment"

PAGE_CAP = 40

# A certificate of service, as it appears where the document actually ends:
# either the heading standing alone on its own line, or the sentence beneath it.
# Matching the bare phrase anywhere fires on the table of contents -- the line
# "CERTIFICATE OF SERVICE ....... 12" in an appellate brief's front matter --
# and reports a 2-page brief for a 15-page filing.
_CERT_HEADING = re.compile(r"^\s*(certificate|proof)\s+of\s+service\s*[.:]?\s*$", re.IGNORECASE)
_CERT_SENTENCE = re.compile(
    r"(hereby certif\w+|copy of the foregoing|a copy of the foregoing|"
    r"was (?:served|mailed|sent)\b.{0,60}\bupon\b)",
    re.IGNORECASE,
)


def _has_certificate(text):
    for line in (text or "").splitlines():
        if _CERT_HEADING.match(line):
            return True
    return bool(_CERT_SENTENCE.search(text or ""))
# A cover sheet is a page that says an exhibit's name and essentially nothing
# else. The length test is what separates it from a page that cites one.
_COVER = re.compile(r"^\s*(exhibit|attachment|appendix)\s+[A-Z0-9]{1,4}\b[.:\s-]*$", re.IGNORECASE)
# Filing-system furniture repeated on every page of an e-filed scan.
_EFILE_STAMP = re.compile(
    r"^.{0,40}(?:CLERK OF COURTS|ELECTRONICALLY FILED|EFILED|E-FILED).{0,140}$",
    re.IGNORECASE,
)
_PAGE_FOOTER = re.compile(r"^\s*(?:Page\s+\d+\s+of\s+\d+|\d{1,3})\s*$", re.IGNORECASE)


def _is_cover_sheet(text):
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if not lines or len(" ".join(lines)) > 120:
        return None
    for line in lines[:3]:
        if _COVER.match(line):
            return re.sub(r"\s+", " ", line).strip(" .:-").title()
    return None


def split_filed_document(pages, *, page_cap=PAGE_CAP):
    """Where the filed brief stops and the record filed with it begins."""
    if not pages:
        return {"brief_page_count": 0, "rule": "empty", "exhibits": []}

    # The FIRST certificate, not the last: a filing's own certificate sits at the
    # end of its argument, and the exhibits behind it are frequently other court
    # filings that carry certificates of their own. Taking the last one swallows
    # the whole record into the brief.
    certificate = next(
        (page["page"] for page in pages if _has_certificate(page["text"])), None
    )

    cover = next(
        (page["page"] for page in pages
         if page["page"] > 1 and _is_cover_sheet(page["text"])),
        None,
    )

    if certificate:
        boundary, rule = certificate, f"certificate of service on page {certificate}"
    elif cover:
        boundary, rule = cover - 1, f"exhibit cover sheet on page {cover}"
    else:
        boundary, rule = len(pages), "no boundary marker; whole document read as the brief"

    if boundary > page_cap:
        boundary, rule = page_cap, f"no boundary found; first {page_cap} pages read as the brief"

    exhibits, current = [], None
    for page in pages:
        if page["page"] <= boundary:
            continue
        label = _is_cover_sheet(page["text"])
        if label or current is None:
            current = {"label": label or "Record", "start_page": page["page"],
                       "end_page": page["page"], "text": page["text"] or ""}
            exhibits.append(current)
        else:
            current["end_page"] = page["page"]
            current["text"] += "\n\n" + (page["text"] or "")
    return {"brief_page_count": boundary, "rule": rule, "exhibits": exhibits}


def strip_page_furniture(pages):
    """Remove the e-filing stamp and page footer repeated on every scanned page.

    These are stamped on by the court's filing system and by the scanner, not
    written by counsel, and they repeat identically on every page. Nothing else
    is touched: OCR misreadings, typos and citation errors in the filed text are
    left exactly as transcribed, because they are properties of the document
    under test.
    """
    kept, removed_stamps, removed_footers = [], 0, 0
    for page in pages:
        lines = []
        for line in (page["text"] or "").splitlines():
            if _EFILE_STAMP.match(line.strip()):
                removed_stamps += 1
                continue
            if _PAGE_FOOTER.match(line):
                removed_footers += 1
                continue
            lines.append(line.rstrip())
        kept.append({"page": page["page"], "text": "\n".join(lines).strip()})
    return kept, {"efile_stamp_lines_removed": removed_stamps,
                  "page_footer_lines_removed": removed_footers}


def ocr_records():
    index_path = OUT / "ocr_index.json"
    if not index_path.exists():
        return {}
    return {entry["source_file"]: entry for entry in json.loads(index_path.read_text())}


def load_ocr(entry):
    return json.loads((OUT / entry["cache"]).read_text())


def filing_from_scan(entry):
    """The filed brief and the record, recovered from a transcribed scan."""
    record = load_ocr(entry)
    pages, furniture = strip_page_furniture(record["pages"])
    split = split_filed_document(pages)
    brief_pages = [p for p in pages if p["page"] <= split["brief_page_count"]]
    return {
        "brief": "\n\n".join(p["text"] for p in brief_pages if p["text"]).strip() + "\n",
        "brief_page_count": split["brief_page_count"],
        "split_rule": split["rule"],
        "exhibits": [
            {"label": e["label"],
             "page_range": [e["start_page"], e["end_page"]],
             "text": e["text"].strip()}
            for e in split["exhibits"]
        ],
        "furniture_removed": furniture,
        "ocr": {
            "engine": record["engine"],
            "transcribed_on": record["transcribed_on"],
            "source_sha256": record["source_sha256"],
            "scan_pages": record["page_count"],
            "scan_chars": record["char_count"],
        },
    }
