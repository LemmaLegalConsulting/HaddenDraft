#!/usr/bin/env python3
"""Create auditable, hierarchy-preserving Markdown retrieval chunks from source PDFs.

Run one document or all configured documents:
  python scripts/chunk_legal_sources.py --document ohio-eviction-landlord-tenant-law-6e
  python scripts/chunk_legal_sources.py --all
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import yaml
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
CONTENT, SOURCE_ROOT, OUTPUT_ROOT = ROOT / "content", ROOT / "content" / "treatises" / "source", ROOT / "content" / "treatises" / "markdown"
MAX_WORDS = 1250

@dataclass(frozen=True)
class Profile:
    slug: str; title: str; version: str; source: str; kind: str

PROFILES = {
 "ohio-eviction-landlord-tenant-law-6e": Profile("ohio-eviction-landlord-tenant-law-6e", "Ohio Eviction and Landlord-Tenant Law", "2022-06 (Sixth Edition)", "2022-06.pdf", "ohio"),
 "hud-4350-3-rev-1": Profile("hud-4350-3-rev-1", "HUD Handbook 4350.3 REV-1: Occupancy Requirements of Subsidized Programs", "2013-11 (Change 4)", "2013-11-change-4.pdf", "hud"),
}

@dataclass
class Section:
    heading: str; level: int; page_start: int; page_end: int; path: list[str]
    lines: list[str] = field(default_factory=list)

OHIO_MAIN = re.compile(r"^[IVXLCDM]+\.\s+(?:Eviction Action|Ohio Landlord-Tenant Act|Rental Agreement|Rent Depositing|Tenant Claims|Security Deposit|Landlord Claim|Attorney’s Fees|Jurisdiction|Landlord-Tenant Law|Miscellaneous|Land Installment|HUD-Assisted|Table of Cases|Index)" )
OHIO_UPPER = re.compile(r"^[A-Z]\.\s+(?!\d).+")
OHIO_NUMBER = re.compile(r"^([1-9]|1\d|2[0-5])\.\s+[A-Z].+")
OHIO_LOWER = re.compile(r"^[a-u]\.\s+[A-Z].+")
HUD_CHAPTER = re.compile(r"^CHAPTER\s+(\d+)\.\s*(.+)$", re.I)
HUD_SPECIAL = re.compile(r"^(?:GLOSSARY|APPENDIX(?:\s+[A-Z0-9-]+)?|EXHIBIT\s+[A-Z0-9-]+)\s*$", re.I)
HUD_PARA = re.compile(r"^(\d+-\d+(?:\.\d+)?)(?:\s+|\.\s*)(.+)$")
HUD_SECTION = re.compile(r"^SECTION\s+\d+\s*:\s*(.+)$", re.I)

def clean_lines(text: str, p: Profile) -> list[str]:
    """Remove only repeat page furniture; substantive citations/lists survive verbatim."""
    result = []
    for raw in text.replace("\u00ad", "").splitlines():
        line = re.sub(r"[ \t]+", " ", raw).strip()
        if not line: result.append(""); continue
        if p.kind == "ohio" and "Ohio Eviction and Landlord-Tenant Law (6th ed.)" in line:
            line = re.sub(r"^(?:[ivxlcdm]+|\d+)?\s*Ohio Eviction and Landlord-Tenant Law \(6th ed\.\)\s*", "", line, flags=re.I)
        if p.kind == "hud" and ("HUD Occupancy Handbook" in line or "4350.3 REV-1" in line or re.match(r"^Chapter \d+:", line)): continue
        if line: result.append(line)
    return result

def normalize(lines: Iterable[str]) -> list[str]:
    """Join wrapped prose only; preserve list/citation lines as boundaries."""
    out = []
    for line in lines:
        if not line:
            if out and out[-1] != "": out.append("")
            continue
        item = bool(re.match(r"^(?:[•]|[-–—]|\(?[a-zA-Z0-9]+[.)])\s+", line))
        if not out or out[-1] == "" or item: out.append(line)
        elif out[-1].endswith((".", ";", ":", "?", "!")): out.extend(["", line])
        else: out[-1] += " " + line
    while out and out[-1] == "": out.pop()
    return out

def heading(line: str, p: Profile) -> tuple[int, str] | None:
    if p.kind == "ohio":
        if OHIO_MAIN.match(line): return 1, line
        if OHIO_UPPER.match(line): return 2, line
        if OHIO_NUMBER.match(line): return 3, line
        # Excluding "v." avoids treating case citations as subheadings.
        if OHIO_LOWER.match(line): return 4, line
        return None
    if m := HUD_CHAPTER.match(line): return 1, f"Chapter {m.group(1)}. {m.group(2).title()}"
    if HUD_SPECIAL.match(line): return 1, line.title()
    if m := HUD_SECTION.match(line): return 2, f"Section: {m.group(1).title()}"
    if m := HUD_PARA.match(line): return 3, f"{m.group(1)} {m.group(2)}"
    return None

def body_start(pages: list[list[str]], p: Profile) -> int:
    for index, lines in enumerate(pages):
        joined = " ".join(lines)
        if p.kind == "ohio" and "R.C. Chapter 1923 establishes" in joined: return index
        # The contents pages also enumerate 1-1. The substantive opening
        # page is the first one that carries the chapter title and an
        # undotted 1-1 paragraph heading.
        if p.kind == "hud" and any(HUD_CHAPTER.match(x) for x in lines) and any(x.startswith("1-1 ") and "." not in x for x in lines): return index
    raise ValueError(f"Could not locate substantive body for {p.slug}; inspect heading conventions.")

def extract_sections(p: Profile, source: Path) -> tuple[list[Section], int]:
    reader = PdfReader(source)
    pages = [clean_lines(page.extract_text() or "", p) for page in reader.pages]
    sections, ancestors, current = [], [], None
    for page_index in range(body_start(pages, p), len(pages)):
        for line_index, line in enumerate(pages[page_index]):
            found = heading(line, p)
            # HUD's glossary is a two-column PDF. Its definitions have a term
            # on one line followed by a parenthesized scope on the next; turn
            # each into a retrieval unit while retaining "Glossary" in its path.
            next_line = pages[page_index][line_index + 1] if line_index + 1 < len(pages[page_index]) else ""
            if p.kind == "hud" and not found and ancestors and ancestors[0] == "Glossary" and re.match(r"^[A-Z][A-Za-z /-]{2,60}$", line) and next_line.startswith("("):
                found = (2, line)
            if found:
                level, label = found
                # Chapter 1 has no printed sections, while later chapters do.
                # Paragraphs are therefore chapter children unless a Section
                # heading is currently active.
                if p.kind == "hud" and level == 3 and not any(x.startswith("Section:") for x in ancestors): level = 2
                ancestors = ancestors[:level - 1] + [label]
                if current: current.page_end = page_index + 1; sections.append(current)
                current = Section(label, level, page_index + 1, page_index + 1, ancestors.copy())
            elif current: current.lines.append(line)
        if current: current.page_end = page_index + 1
    if current: sections.append(current)
    if not sections: raise ValueError(f"No sections found in {source}")
    return sections, len(reader.pages)

def split_section(section: Section) -> list[list[str]]:
    lines, pieces, count = normalize(section.lines), [[]], 0
    for line in lines:
        words = len(line.split())
        # Split only at a pre-existing blank: lists and citation strings remain intact.
        if count + words > MAX_WORDS and pieces[-1] and pieces[-1][-1] == "": pieces.append([]); count = 0
        pieces[-1].append(line); count += words
    return [x for x in pieces if any(line.strip() for line in x)]

def front(data: dict) -> str:
    return "---\n" + yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip() + "\n---\n"

def slugify(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.casefold())).strip("-") or "section"

def kind(section: Section, p: Profile) -> str:
    if p.kind != "hud": return "substantive-section"
    path = " ".join(section.path).casefold()
    return "glossary-definition" if "glossary" in path else "appendix-or-exhibit" if "appendix" in path or "exhibit" in path else "substantive-section"

def generate(p: Profile) -> dict:
    source = SOURCE_ROOT / p.slug / p.source
    if not source.is_file(): raise FileNotFoundError(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    sections, pages = extract_sections(p, source)
    out, chunks = OUTPUT_ROOT / p.slug / source.stem, OUTPUT_ROOT / p.slug / source.stem / "chunks"
    if out.exists(): shutil.rmtree(out)
    chunks.mkdir(parents=True)
    common = {"document_slug": p.slug, "document_title": p.title, "document_version": p.version, "source_path": source.relative_to(CONTENT).as_posix(), "source_sha256": digest, "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "generator": "scripts/chunk_legal_sources.py"}
    full, inventory, ordinal = [front({**common, "pdf_pages": pages, "derivative": "full-markdown"}), f"# {p.title}", "", f"Version: {p.version}", ""], [], 0
    for section in sections:
        full.extend(["#" * min(section.level + 1, 6) + " " + section.heading, "", *normalize(section.lines), ""])
        parts = split_section(section)
        for part, text in enumerate(parts, 1):
            ordinal += 1; ident = f"{ordinal:04d}-{slugify(section.heading)[:72]}-{part:02d}"; filename = f"{ident}.md"
            data = {**common, "chunk_id": ident, "chunk_ordinal": ordinal, "section_heading": section.heading, "section_path": section.path, "pdf_page_start": section.page_start, "pdf_page_end": section.page_end, "chunk_part": part, "chunk_parts_in_section": len(parts), "content_kind": kind(section, p)}
            toc = "\n".join(f"{'  ' * depth}- {item}" for depth, item in enumerate(section.path))
            body = [front(data), f"# {section.heading}", "", "## Table-of-contents context", "", toc, "", "## Source text", "", *text]
            (chunks / filename).write_text("\n".join(body).rstrip() + "\n", encoding="utf-8")
            inventory.append({"id": ident, "file": f"chunks/{filename}", "heading": section.heading, "path": section.path, "pages": [section.page_start, section.page_end], "content_kind": data["content_kind"]})
    (out / f"{source.stem}.md").write_text("\n".join(full).rstrip() + "\n", encoding="utf-8")
    manifest = {**common, "pdf_pages": pages, "chunk_count": len(inventory), "chunks": inventory}
    (out / "manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return manifest

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--document", choices=sorted(PROFILES)); parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    if args.all == bool(args.document): parser.error("choose exactly one of --document or --all")
    chosen = PROFILES.values() if args.all else [PROFILES[args.document]]
    result = [generate(p) for p in chosen]
    print(json.dumps([{k: x[k] for k in ("document_slug", "source_sha256", "chunk_count")} for x in result], indent=2))
    return 0

if __name__ == "__main__": raise SystemExit(main())
