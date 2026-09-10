"""Inventory every Lexis delivery file: metadata, pairing, extraction status.

This is step 1A of the cleanup plan: collapse a flat Lexis download into
case-level units. It reads only; it never rewrites a source file.

Lexis delivers each result as a .docx wrapper plus, sometimes, a scanned
_Attachment1.pdf. The wrapper carries a fixed header block (case name, docket,
court, filing date, reporter cite, party line, Type, Counsel, Title) followed
either by the document's text or -- for PDF-only results -- by the single line
"Click to view PDF document". Which of the two it is decides whether the filing
can be benchmarked at all, so it is recorded per file rather than assumed.
"""

import json
import os
import re
import sys
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402
django.setup()

from apps.argument_gym import ingestion  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from filed_document import filing_from_scan, ocr_records  # noqa: E402

CORPUS = ROOT / "lexis_real_briefs"
OUT = CORPUS / "experiment"

# The Lexis wrapper's own furniture. Everything from "Text" onward is the filing.
_HEADER_KEYS = ("Reporter", "Type:", "Counsel", "Title", "Text", "Prior History:",
                "Docket Number:", "CASE NO", "Case No", "State:")
_PDF_ONLY = re.compile(r"click to view pdf document", re.IGNORECASE)
_DOCKET = re.compile(r"^(?:Docket Number:\s*|CASE NO\.?\s*|Case No\.?\s*)(.+)$", re.IGNORECASE)
_DATE = re.compile(r"^[A-Z][a-z]+ \d{1,2}, \d{4}(?:, Filed)?$")
_COURT = re.compile(r"COURT|Court", )
_TYPE = re.compile(r"^Type:\s*(.+)$")
_REPORTER = re.compile(r"LEXIS", re.IGNORECASE)
# An appellate filing names an appellate court or an appellate role.
_APPELLATE = re.compile(
    r"court of appeals|appellate district|supreme court|appellant|appellee|"
    r"merit brief|memorandum in support of jurisdiction|assignments? of error",
    re.IGNORECASE,
)
# Eviction/possession centrality, tested against the filing's own text.
_EVICTION = re.compile(
    r"forcible entry and detainer|forcible entry|\bR\.?C\.? ?1923|chapter 1923|"
    r"\bevict(?:ion|ed|s)?\b|writ of restitution|unlawful detainer|"
    r"three[- ]day notice|3[- ]day notice|notice to leave the premises|"
    r"landlord[- ]tenant|\bR\.?C\.? ?5321|tenanc(?:y|ies)|holdover",
    re.IGNORECASE,
)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_header(lines):
    """Split the Lexis wrapper header from the filed document's own text."""
    header, body_start = {}, len(lines)
    for index, line in enumerate(lines):
        if line.strip() == "Text":
            body_start = index + 1
            break
    head = lines[:body_start]
    header["case_name"] = head[0].strip() if head else ""
    for line in head:
        stripped = line.strip()
        if match := _DOCKET.match(stripped):
            header.setdefault("docket", match.group(1).strip())
        elif match := _TYPE.match(stripped):
            header.setdefault("lexis_type", match.group(1).strip())
        elif _DATE.match(stripped):
            header.setdefault("filed", stripped.replace(", Filed", ""))
        elif "COURT" in stripped.upper() and "court" not in header:
            header.setdefault("court", stripped)
        elif _REPORTER.search(stripped) and "reporter_cite" not in header:
            header.setdefault("reporter_cite", stripped)
    header["header_line_count"] = body_start
    return header, "\n".join(lines[body_start:])


def attachment_key(stem):
    """Normalize a delivery filename so a wrapper and its PDF share a key.

    Lexis truncates long names at 100 characters and appends a copy index, so
    "X.docx" can arrive beside "X_Attachment1.pdf", "X_Attach.pdf" or
    "X_Attachment1(2).pdf". The key is the name with the attachment marker and
    the copy index removed, lowercased, trailing punctuation dropped.
    """
    stem = re.sub(r"_Attach(?:ment\d*)?.*$", "", stem)
    copy = ""
    if match := re.search(r"\((\d+)\)\s*$", stem):
        copy = match.group(1)
        stem = stem[: match.start()]
    return re.sub(r"[\s._,-]+$", "", stem).lower(), copy


def main():
    scans = ocr_records()
    files = sorted(p for p in CORPUS.iterdir() if p.is_file())
    wrappers, attachments = {}, {}
    for path in files:
        key, copy = attachment_key(path.stem)
        if path.suffix.lower() == ".pdf":
            attachments.setdefault((key, copy), []).append(path)
        elif path.suffix.lower() == ".docx":
            wrappers[(key, copy)] = path

    records = []
    for (key, copy), path in sorted(wrappers.items()):
        if path.stem.startswith("Files_") and "doclist" in path.stem:
            continue  # the delivery manifest, not a filing
        extracted = ingestion.extract_document(path.read_bytes(), filename=path.name)
        lines = [p["text"] for p in extracted["paragraphs"]]
        header, body = parse_header(lines)
        pdf_only = bool(_PDF_ONLY.search("\n".join(lines)))

        attached = []
        for pdf in attachments.get((key, copy), []):
            pdf_extract = ingestion.extract_document(pdf.read_bytes(), filename=pdf.name)
            pdf_text = "\n".join(p["text"] for p in pdf_extract["paragraphs"])
            attached.append({
                "file": pdf.name,
                "sha256": sha256(pdf),
                "bytes": pdf.stat().st_size,
                "pages": pdf_extract["pageCount"],
                "extracted_chars": len(pdf_text),
                "text_layer": len(pdf_text) > 500,
            })

        # A PDF-only wrapper carries no filing text. Where the scan has been
        # transcribed (ocr_scans.py), the filing and the record it was filed with
        # are recovered from the scan and used in place of the empty wrapper.
        scan_filing = None
        for attachment in attached:
            entry = scans.get(attachment["file"])
            if entry and not attachment["text_layer"]:
                scan_filing = filing_from_scan(entry)
                attachment["ocr_chars"] = entry["chars"]
                attachment["ocr_cache"] = entry["cache"]
                break
        record_body_from_scan = bool(scan_filing) and len(body) <= 500
        if record_body_from_scan:
            body = scan_filing["brief"]

        court = header.get("court", "")
        appellate = bool(_APPELLATE.search(f"{court} {path.stem} {header.get('lexis_type','')}"))
        searchable = body if len(body) > 500 else "\n".join(
            a_text for a in attached for a_text in [""]
        )
        eviction_hits = sorted({m.group(0).lower() for m in _EVICTION.finditer(body)})

        records.append({
            "wrapper_file": path.name,
            "wrapper_sha256": sha256(path),
            "case_name": header.get("case_name", ""),
            "docket": header.get("docket", ""),
            "court": court,
            "filed": header.get("filed", ""),
            "reporter_cite": header.get("reporter_cite", ""),
            "lexis_type": header.get("lexis_type", ""),
            "title": path.stem,
            "header_line_count": header["header_line_count"],
            "body_chars": len(body),
            "pdf_only_wrapper": pdf_only,
            "level": "appellate" if appellate else "trial",
            "eviction_terms": eviction_hits,
            "eviction_term_count": len(eviction_hits),
            "attachments": attached,
            "attachment_text_layer": any(a["text_layer"] for a in attached),
            "text_source": "ocr_scan" if (scan_filing and record_body_from_scan) else "lexis_docx",
            "scan_filing": {
                "brief_page_count": scan_filing["brief_page_count"],
                "split_rule": scan_filing["split_rule"],
                "brief_chars": len(scan_filing["brief"]),
                "record_exhibits": [
                    {"label": e["label"], "page_range": e["page_range"], "chars": len(e["text"])}
                    for e in scan_filing["exhibits"]
                ],
                "furniture_removed": scan_filing["furniture_removed"],
                "ocr": scan_filing["ocr"],
            } if scan_filing else None,
        })

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "inventory.json").write_text(json.dumps(records, indent=2) + "\n")
    print(f"wrote {OUT / 'inventory.json'}: {len(records)} filings")

    benchable = [r for r in records if r["body_chars"] > 5000]
    print(f"  readable filings          : {len(benchable)}")
    print(f"  text from Lexis .docx     : {sum(1 for r in records if r['text_source'] == 'lexis_docx')}")
    print(f"  text from OCR'd scan      : {sum(1 for r in records if r['text_source'] == 'ocr_scan')}")
    print(f"  with a record attached    : {sum(1 for r in records if (r.get('scan_filing') or {}).get('record_exhibits'))}")
    print(f"  trial level               : {sum(1 for r in records if r['level'] == 'trial')}")
    print(f"  appellate level           : {sum(1 for r in records if r['level'] == 'appellate')}")


if __name__ == "__main__":
    main()
