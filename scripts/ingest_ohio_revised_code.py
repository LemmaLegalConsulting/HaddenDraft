#!/usr/bin/env python3
"""Fetch, provenance-stamp, chunk, and differentially refresh selected Ohio statutes.

Examples:
  python scripts/ingest_ohio_revised_code.py --ring 1
  python scripts/ingest_ohio_revised_code.py --chapter 5321
  python scripts/ingest_ohio_revised_code.py --section 5321.04
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from decimal import Decimal
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "content" / "statutes" / "ohio-revised-code"
SCOPE_PATH = LIBRARY / "scope.yaml"
MANIFEST_PATH = LIBRARY / "manifest.yaml"
JSONL_PATH = LIBRARY / "ohio_orc_housing_consumer.jsonl"
SECTIONS_DIR = LIBRARY / "sections"
CHUNKS_DIR = LIBRARY / "chunks"
MAX_WORDS = 1100
SECTION_RE = re.compile(r"^Section\s+(\d+\.\d+)(?:\s*\|\s*(.+))?$", re.I)
LAST_UPDATED_RE = re.compile(r"^Last updated\s+(.+)$", re.I)


class OhioCodeParser(HTMLParser):
    """Extract rendered main-content text and official section/PDF links without a site-specific DOM dependency."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.main_depth = 0
        self.text: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._anchor_href = ""
        self._anchor_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "main":
            self.main_depth += 1
        if self.main_depth and tag == "a":
            self._anchor_href, self._anchor_text = values.get("href", ""), []

    def handle_endtag(self, tag):
        if self.main_depth and tag == "a" and self._anchor_href:
            self.links.append((" ".join(self._anchor_text).strip(), self._anchor_href))
            self._anchor_href, self._anchor_text = "", []
        if tag == "main" and self.main_depth:
            self.main_depth -= 1

    def handle_data(self, data):
        if self.main_depth:
            value = " ".join(data.split())
            if value:
                self.text.append(value)
                if self._anchor_href:
                    self._anchor_text.append(value)


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def front(data: dict) -> str:
    return "---\n" + yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip() + "\n---\n"


def section_sort_key(number: str) -> Decimal:
    return Decimal(number)


def in_range(number: str, lower: str, upper: str) -> bool:
    return Decimal(lower) <= Decimal(number) <= Decimal(upper)


def fetch(session: requests.Session, url: str) -> tuple[str, OhioCodeParser]:
    response = None
    for attempt in range(4):
        response = session.get(url, timeout=30, headers={"User-Agent": "agentic-housing-drafting statute indexer/1.0"})
        if response.status_code not in {429, 502, 503, 504}:
            break
        retry_after = response.headers.get("Retry-After", "")
        try:
            delay = min(float(retry_after), 60)
        except ValueError:
            delay = 2**attempt
        time.sleep(delay)
    assert response is not None
    response.raise_for_status()
    parser = OhioCodeParser()
    parser.feed(response.text)
    if not parser.text:
        raise ValueError(f"No rendered main content found at {url}")
    return response.text, parser


def chapter_sections(parser: OhioCodeParser, base_url: str) -> dict[str, str]:
    result = {}
    for _label, href in parser.links:
        match = re.search(r"/section-(\d+\.\d+)$", href)
        if match:
            result[match.group(1)] = urljoin(base_url, href)
    return result


def target_sections(target: dict, session: requests.Session, base_url: str) -> dict[str, str]:
    chapter = str(target["chapter"])
    selected = set(str(number) for number in target.get("sections", []))
    if target.get("all_sections") or target.get("ranges"):
        _raw, parser = fetch(session, f"{base_url}/chapter-{chapter}")
        # A chapter page also links to cross-referenced statutes. Its own
        # inventory is identified by the same chapter-number prefix.
        available = {number: url for number, url in chapter_sections(parser, base_url).items() if number.startswith(f"{chapter}.")}
        if target.get("all_sections"):
            selected.update(available)
        for lower, upper in target.get("ranges", []):
            selected.update(number for number in available if in_range(number, str(lower), str(upper)))
    return {number: f"{base_url}/section-{number}" for number in selected}


def parse_section_lines(lines: list[str], html: str, url: str, *, acquired_from_url: str = "", pdf_url: str = "") -> dict:
    match = SECTION_RE.match(lines[0]) if lines else None
    if match is None:
        raise ValueError(f"No statutory section heading found at {url}")
    section, title = match.groups()
    # The current Ohio template emits the visual `|` separator as a separate
    # text node; retain support for the older single-node rendering too.
    if not title and len(lines) > 2 and lines[1] == "|":
        title = lines[2]
    if not title:
        raise ValueError(f"No statutory section title found at {url}")
    metadata = {"effective_date": "", "latest_legislation": "", "official_last_updated": ""}
    for index, line in enumerate(lines):
        label = line.casefold().rstrip(":")
        if label == "effective" and index + 1 < len(lines):
            metadata["effective_date"] = lines[index + 1]
        elif label == "latest legislation" and index + 1 < len(lines):
            metadata["latest_legislation"] = lines[index + 1]
        elif found := LAST_UPDATED_RE.match(line):
            metadata["official_last_updated"] = found.group(1)
    pdf_index = next((index for index, line in enumerate(lines) if line.casefold().rstrip(":") == "pdf"), 0)
    end = next(
        (index for index, line in enumerate(lines[pdf_index + 1 :], pdf_index + 1)
         if LAST_UPDATED_RE.match(line) or line.casefold() == "available versions of this section"),
        len(lines),
    )
    body = lines[pdf_index + 1 : end]
    if body and "authenticated pdf" in body[0].casefold():
        body = body[1:]
    text = "\n\n".join(body).strip()
    if not text:
        raise ValueError(f"No statutory text found at {url}")
    return {
        "section": section,
        "title": title,
        "url": url,
        "acquired_from_url": acquired_from_url or url,
        "authenticated_pdf_url": pdf_url,
        "text": text,
        "raw_html_sha256": sha256(html),
        "normalized_text_sha256": sha256(text),
        **metadata,
    }


def parse_section(html: str, parser: OhioCodeParser, url: str) -> dict:
    lines = parser.text
    heading_index = next((index for index, line in enumerate(lines) if SECTION_RE.match(line)), None)
    if heading_index is None:
        raise ValueError(f"No statutory section heading found at {url}")
    pdf_url = next((urljoin(url, href) for label, href in parser.links if "authenticated pdf" in label.casefold()), "")
    return parse_section_lines(lines[heading_index:], html, url, pdf_url=pdf_url)


def parse_chapter(html: str, parser: OhioCodeParser, chapter_url: str, chapter: str) -> list[dict]:
    """Derive section-level records from one official expanded chapter page."""
    starts = [index for index, line in enumerate(parser.text) if SECTION_RE.match(line)]
    pdf_urls = [urljoin(chapter_url, href) for label, href in parser.links if "authenticated pdf" in label.casefold()]
    records = []
    for ordinal, start in enumerate(starts):
        match = SECTION_RE.match(parser.text[start])
        assert match
        section = match.group(1)
        if not section.startswith(f"{chapter}."):
            continue
        end = starts[ordinal + 1] if ordinal + 1 < len(starts) else len(parser.text)
        pdf_url = pdf_urls[len(records)] if len(records) < len(pdf_urls) else ""
        records.append(parse_section_lines(
            parser.text[start:end], html, f"{chapter_url.rsplit('/', 1)[0]}/section-{section}",
            acquired_from_url=chapter_url, pdf_url=pdf_url,
        ))
    if not records:
        raise ValueError(f"No sections for Chapter {chapter} found at {chapter_url}")
    return records


def chunk_text(text: str) -> list[str]:
    chunks, current, words = [], [], 0
    for paragraph in text.split("\n\n"):
        count = len(paragraph.split())
        if current and words + count > MAX_WORDS:
            chunks.append("\n\n".join(current))
            current, words = [], 0
        current.append(paragraph)
        words += count
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def existing_manifest() -> dict:
    if not MANIFEST_PATH.is_file():
        return {"schema_version": 1, "document_slug": "ohio-revised-code", "sections": []}
    return yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8")) or {}


def write_section(record: dict, *, dry_run: bool) -> list[dict]:
    section = record["section"]
    prefix = section.replace(".", "-")
    source_text = record.pop("text")
    chunks = chunk_text(source_text)
    section_path = SECTIONS_DIR / f"{prefix}.md"
    inventory = []
    for part, text in enumerate(chunks, 1):
        ident = f"orc-{prefix}-{part:02d}"
        filename = f"{ident}.md"
        chunk_record = {**record, "chunk_id": ident, "chunk_part": part, "chunk_parts_in_section": len(chunks)}
        content = front(chunk_record) + f"# Ohio Rev. Code § {section} — {record['title']}\n\n## Source text\n\n{text}\n"
        inventory.append({
            "id": ident, "file": f"chunks/{filename}", "heading": f"Ohio Rev. Code § {section} — {record['title']}",
            "path": ["Ohio Revised Code", f"Chapter {section.split('.')[0]}", f"§ {section}"],
            "content_kind": "statute-section", "section": section, "chapter": section.split(".")[0],
            "citation": f"Ohio Rev. Code § {section}", "url": record["url"], "effective_date": record["effective_date"],
        })
        if not dry_run:
            (CHUNKS_DIR / filename).write_text(content, encoding="utf-8")
    if not dry_run:
        for path in CHUNKS_DIR.glob(f"orc-{prefix}-*.md"):
            if path.name not in {item["file"].split("/", 1)[1] for item in inventory}:
                path.unlink()
        section_content = front(record) + f"# Ohio Rev. Code § {section} — {record['title']}\n\n{source_text}\n"
        section_path.write_text(section_content, encoding="utf-8")
    return inventory


def select_targets(scope: dict, args: argparse.Namespace) -> list[dict]:
    targets = scope.get("targets", [])
    if args.ring:
        return [target for target in targets if str(target.get("ring")) == args.ring]
    if args.chapter:
        selected = [target for target in targets if str(target.get("chapter")) == args.chapter]
        if not selected:
            raise ValueError(f"Chapter {args.chapter} is not configured in {SCOPE_PATH}")
        return selected
    if args.section:
        return [{"chapter": args.section.split(".", 1)[0], "sections": [args.section], "ring": "ad-hoc"}]
    if args.all:
        return targets
    raise ValueError("Choose --all, --ring, --chapter, or --section.")


def record_is_selected(record: dict, target: dict) -> bool:
    if target.get("all_sections"):
        return True
    section = record["section"]
    if section in {str(value) for value in target.get("sections", [])}:
        return True
    return any(in_range(section, str(lower), str(upper)) for lower, upper in target.get("ranges", []))


def write_jsonl(sections: list[dict]):
    with JSONL_PATH.open("w", encoding="utf-8") as output:
        for item in sections:
            record_path = LIBRARY / item["record_path"]
            source = record_path.read_text(encoding="utf-8")
            body = source.split("---\n", 2)[-1].strip() if source.startswith("---\n") else source.strip()
            output.write(json.dumps({
                "id": f"orc-{item['section']}", "citation": f"Ohio Rev. Code § {item['section']}",
                "title": item["title"], "url": item["url"], "chapter_source_url": item["acquired_from_url"],
                "effective_date": item["effective_date"], "latest_legislation": item["latest_legislation"],
                "text": body,
            }, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true", help="Refresh every configured non-empty target.")
    selection.add_argument("--ring", choices=["1", "2", "3", "secondary"])
    selection.add_argument("--chapter")
    selection.add_argument("--section", help="One section, e.g. 5321.04")
    parser.add_argument("--force", action="store_true", help="Rewrite selected records even when normalized text has not changed.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pause", type=float, default=2.0, help="Seconds to wait between official page requests.")
    args = parser.parse_args()
    if args.section and not re.fullmatch(r"\d+\.\d+", args.section):
        parser.error("--section must be an Ohio Revised Code section number, e.g. 5321.04")

    scope = yaml.safe_load(SCOPE_PATH.read_text(encoding="utf-8")) or {}
    source = scope.get("source", {})
    base_url = str(source["base_url"]).rstrip("/")
    targets = select_targets(scope, args)
    session = requests.Session()
    manifest = existing_manifest()
    prior = {item["section"]: item for item in manifest.get("sections", []) if item.get("section")}
    if not args.dry_run:
        SECTIONS_DIR.mkdir(parents=True, exist_ok=True)
        CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    changed, unchanged, failures, requested, page_requests = [], [], [], 0, 0
    selected_numbers = set()
    for target in targets:
        chapter = str(target["chapter"])
        if not args.section and not (target.get("all_sections") or target.get("ranges") or target.get("sections")):
            continue
        try:
            page_requests += 1
            if args.section:
                url = f"{base_url}/section-{args.section}"
                html, parsed = fetch(session, url)
                records = [parse_section(html, parsed, url)]
            else:
                chapter_url = f"{base_url}/chapter-{chapter}"
                html, parsed = fetch(session, chapter_url)
                records = [record for record in parse_chapter(html, parsed, chapter_url, chapter) if record_is_selected(record, target)]
            requested += len(records)
            for record in records:
                number = record["section"]
                selected_numbers.add(number)
                old = prior.get(number, {})
                if not args.force and old.get("normalized_text_sha256") == record["normalized_text_sha256"]:
                    unchanged.append(number)
                    continue
                record["fetched_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
                record["source_name"] = source["name"]
                record["publisher"] = source["publisher"]
                record["jurisdiction"] = source["jurisdiction"]
                record["content_kind"] = source["content_kind"]
                record["record_path"] = f"sections/{number.replace('.', '-')}.md"
                prior[number] = {**record, "chunks": write_section(record.copy(), dry_run=args.dry_run)}
                changed.append(number)
        except (requests.RequestException, ValueError) as exc:
            failures.append({"chapter": chapter, "error": str(exc)})
        time.sleep(max(args.pause, 0))

    if not args.dry_run:
        # A complete configured refresh is authoritative for its declared
        # scope. Prune records that were previously admitted by an erroneous
        # range interpretation or removed from that scope; targeted refreshes
        # deliberately preserve unrelated records.
        if args.all:
            retired = [item for number, item in prior.items() if number not in selected_numbers]
            for item in retired:
                record_path = LIBRARY / item.get("record_path", "")
                if record_path.is_file():
                    record_path.unlink()
                for chunk in item.get("chunks", []):
                    chunk_path = LIBRARY / chunk.get("file", "")
                    if chunk_path.is_file():
                        chunk_path.unlink()
            prior = {number: item for number, item in prior.items() if number in selected_numbers}
        sections = [prior[number] for number in sorted(prior, key=section_sort_key)]
        chunks = [chunk for item in sections for chunk in item.get("chunks", [])]
        output = {
            "schema_version": 1, "document_slug": "ohio-revised-code", "document_title": "Ohio Revised Code",
            "jurisdiction": "Ohio", "content_kind": "statute", "source_name": source["name"],
            "publisher": source["publisher"], "source_base_url": base_url,
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "generator": "scripts/ingest_ohio_revised_code.py", "section_count": len(sections),
            "chunk_count": len(chunks), "sections": sections, "chunks": chunks,
        }
        MANIFEST_PATH.write_text(yaml.safe_dump(output, sort_keys=False, allow_unicode=True), encoding="utf-8")
        write_jsonl(sections)
    print(json.dumps({"requested_sections": requested, "chapter_requests": page_requests, "changed": changed, "unchanged": unchanged, "failures": failures, "dry_run": args.dry_run}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
