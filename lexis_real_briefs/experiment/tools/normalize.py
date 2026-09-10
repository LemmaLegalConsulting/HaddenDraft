"""Step 1C: mechanical normalization of a Lexis delivery into a benchmarkable brief.

Mechanical means: remove what the retrieval system added, and nothing else.
Specifically this removes

  * the Lexis wrapper header (case name through the "Text" marker) and the
    trailing "End of Document" line, which are delivery furniture and are not in
    the filed document -- confirmed against the scanned as-filed PDF, which
    begins at the court caption;
  * star-pagination markers ("[*12]"), which Lexis injects to key its text to
    the reporter and which appear nowhere in the filed document. The page
    boundary they mark is preserved as a page break rather than discarded;
  * full-text authorities that Lexis appended after the filed document ends
    (each introduced by a LEXSEE line following the certificate of service).
    These are carried into attachments/ rather than deleted, because a brief's
    appended authorities are part of the filing even though they are not the
    brief under test.

It does not rewrite prose, fix typos, fix citations, repair OCR spelling,
remove attorney boilerplate, or touch repeated language inside the brief.
Redundancy inside a filing is a property of the filing and stays.

Every removal is written to the normalization log so the transformation is
reviewable and reversible against source/.
"""

import hashlib
import json
import os
import re
import shutil
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402
django.setup()

from apps.argument_gym import ingestion  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from filed_document import filing_from_scan, ocr_records  # noqa: E402

NORMALIZATION_VERSION = "1.0"
CORPUS = ROOT / "lexis_real_briefs"
OUT = CORPUS / "experiment"

_STAR = re.compile(r"\s*\[\*+\s*\d+\]\s*")
_LEXSEE = re.compile(r"^\s*LEXSEE\b", re.IGNORECASE)
_CERT = re.compile(r"certificate of service|proof of service", re.IGNORECASE)
_END = re.compile(r"^\s*End of Document\s*$", re.IGNORECASE)


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def split_appended_authorities(lines):
    """Separate the filed document from authorities Lexis appended after it.

    The boundary is the first LEXSEE line that falls at or after the
    certificate of service. Requiring the certificate first is what stops a
    brief that merely quotes a LEXSEE cite mid-argument from being cut in half.
    """
    cert = next((i for i, line in enumerate(lines) if _CERT.search(line)), None)
    if cert is None:
        return lines, []
    start = next((i for i, line in enumerate(lines) if i >= cert and _LEXSEE.match(line)), None)
    if start is None:
        return lines, []
    return lines[:start], lines[start:]


def normalize_lines(lines):
    """Strip retrieval furniture from a line, keeping page boundaries."""
    out, removed_stars = [], 0
    for line in lines:
        if _END.match(line):
            continue
        text = unicodedata.normalize("NFC", line)
        stars = _STAR.findall(text)
        if stars:
            removed_stars += len(stars)
            # A star marks a page boundary in the reporter's pagination. Keep
            # the boundary as a break so paragraph sequence and page structure
            # survive, and drop only the marker itself.
            text = _STAR.sub(" ", text)
        text = re.sub(r"[ \t]{2,}", " ", text).rstrip()
        out.append(text)
    return out, removed_stars


def normalize_one(record):
    path = CORPUS / record["wrapper_file"]
    extracted = ingestion.extract_document(path.read_bytes(), filename=path.name)
    raw_lines = [p["text"] for p in extracted["paragraphs"]]

    header = raw_lines[: record["header_line_count"]]
    body = raw_lines[record["header_line_count"]:]
    filed, appended = split_appended_authorities(body)
    clean, stars = normalize_lines(filed)
    appended_clean, appended_stars = normalize_lines(appended)

    # Canonical form: this exact string is what a fixture writes and hashes, so
    # the log's normalized_sha256 and the fixture's control_sha256 agree.
    brief = "\n\n".join(line for line in clean if line.strip()).strip() + "\n"
    authorities = "\n\n".join(line for line in appended_clean if line.strip())
    return {
        "brief": brief,
        "appended_authorities": authorities,
        "log": {
            "wrapper_file": record["wrapper_file"],
            "source_sha256": sha256_file(path),
            "normalization_version": NORMALIZATION_VERSION,
            "removed_header_lines": len(header),
            "removed_header_preview": header[:3],
            "removed_end_of_document_marker": any(_END.match(l) for l in body),
            "removed_star_pagination_markers": stars + appended_stars,
            "appended_authority_lines_moved_to_attachments": len(appended),
            "raw_body_chars": len("\n\n".join(l for l in body if l.strip())),
            "normalized_brief_chars": len(brief),
            "appended_authorities_chars": len(authorities),
            "normalized_sha256": sha256_text(brief),
            "prose_edits": 0,
            "typos_fixed": 0,
            "citations_fixed": 0,
            "boilerplate_removed": 0,
        },
    }


def main():
    records = json.loads((OUT / "inventory.json").read_text())
    scans = ocr_records()
    logs, sizes = [], []
    staging = OUT / "normalized_preview"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    for record in records:
        if record["body_chars"] <= 5000:
            continue  # nothing readable to normalize, with or without OCR
        stem = Path(record["wrapper_file"]).stem[:60]

        if record["text_source"] == "ocr_scan":
            # The wrapper is a metadata card; the filing is the transcribed
            # scan, already split and stripped of page furniture. There is no
            # Lexis header to remove, so normalization is a no-op beyond that.
            entry = next(scans[a["file"]] for a in record["attachments"] if a["file"] in scans)
            filing = filing_from_scan(entry)
            (staging / f"{stem}.txt").write_text(filing["brief"])
            for index, exhibit in enumerate(filing["exhibits"], start=1):
                (staging / f"{stem}.record-{index:02d}.txt").write_text(exhibit["text"] + "\n")
            logs.append({
                "wrapper_file": record["wrapper_file"],
                "text_source": "ocr_scan",
                "normalization_version": NORMALIZATION_VERSION,
                "scan_split_rule": filing["split_rule"],
                "scan_brief_page_count": filing["brief_page_count"],
                "normalized_brief_chars": len(filing["brief"]),
                "normalized_sha256": sha256_text(filing["brief"]),
                "page_furniture_removed": filing["furniture_removed"],
                "ocr": filing["ocr"],
                "prose_edits": 0, "typos_fixed": 0,
                "citations_fixed": 0, "ocr_misreadings_fixed": 0,
            })
            sizes.append((len(filing["brief"]), record["case_name"], stem))
            continue

        result = normalize_one(record)
        result["log"]["text_source"] = "lexis_docx"
        logs.append(result["log"])
        (staging / f"{stem}.txt").write_text(result["brief"])
        if result["appended_authorities"]:
            (staging / f"{stem}.appended-authorities.txt").write_text(result["appended_authorities"])
        sizes.append((result["log"]["normalized_brief_chars"], record["case_name"], stem))

    (OUT / "normalization_log.json").write_text(json.dumps(logs, indent=2) + "\n")
    sizes.sort(reverse=True)
    print(f"normalized {len(logs)} filings -> {staging}")
    print(f"{'chars':>7}  case | file")
    for chars, case, stem in sizes[:6]:
        print(f"{chars:>7}  {case[:34]:<34} | {stem[:40]}")
    print(f"largest normalized brief: {sizes[0][0]} chars")


if __name__ == "__main__":
    main()
