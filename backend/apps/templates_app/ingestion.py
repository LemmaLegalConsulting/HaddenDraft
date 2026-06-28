"""Loss-minimizing conversion of ordinary DOCX files into prepared templates.

The converter edits WordprocessingML in place. It does not round-trip through
HTML, Markdown, or plain text, so styles, numbering, tables, headers, footers,
images, section settings, and relationships remain in the package.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from django.utils.text import slugify


MANIFEST_VERSION = 1
HEADING_WORDS = {
    "background",
    "caption",
    "certificate of service",
    "client goals",
    "conclusion",
    "deadlines",
    "defenses & strategy",
    "desired outcomes",
    "facts",
    "introduction",
    "law and argument",
    "memorandum in support",
    "prayer for relief",
    "relevant facts",
    "respectfully submitted",
    "signature",
    "statement of facts",
    "statement of relevant facts",
    "tasks (delete as you complete each task)",
}
ROMAN_HEADING_RE = re.compile(r"^(?:[IVXLCDM]+|[A-Z]|\d+)[.)]\s+", re.I)
BRACKET_RE = re.compile(r"\[([^\[\]]*)\]")
LIST_PROMPT_RE = re.compile(
    r"(?:insert|add|describe|list|synopsis).*(?:fact|event|allegation|question|document|section)|case specific facts",
    re.I,
)

PLACEHOLDER_ALIASES = {
    "name": "defendant",
    "client name": "defendant",
    "defendant": "defendant",
    "defendant name": "defendant",
    "attorney name": "advocate_name",
    "email": "advocate_email",
    "attorney email": "advocate_email",
    "phone": "advocate_phone",
    "phone number": "advocate_phone",
    "attorney telephone": "advocate_phone",
    "case number": "case_number",
    "case no.": "case_number",
}


@dataclass
class BlockDefinition:
    key: str
    label: str
    block_type: str
    start: int
    end: int
    heading_index: int | None
    expects_list: bool = False

    @property
    def body_start(self):
        return self.start + 1 if self.heading_index == self.start else self.start


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_label(text: str) -> str:
    text = ROMAN_HEADING_RE.sub("", " ".join(text.split())).strip(" -–—:.")
    return text.title() if text.isupper() else text


def is_heading(paragraph) -> bool:
    text = " ".join(paragraph.text.split()).strip()
    if not text or len(text) > 120:
        return False
    if BRACKET_RE.fullmatch(text):
        return False
    style = (paragraph.style.name if paragraph.style else "").lower()
    normalized = ROMAN_HEADING_RE.sub("", text).strip(" -–—:.").lower()
    alpha = "".join(character for character in text if character.isalpha())
    return (
        style.startswith("heading")
        or normalized in HEADING_WORDS
        or (len(alpha) >= 4 and alpha.isupper() and len(text.split()) <= 12)
        or (bool(ROMAN_HEADING_RE.match(text)) and text.upper() == text)
        or text.lower().startswith("case caption")
    )


def classify_block(label: str) -> str:
    lowered = label.lower()
    if "caption" in lowered:
        return "caption"
    if "certificate" in lowered or "service" in lowered:
        return "certificate"
    if "signature" in lowered or "respectfully submitted" in lowered:
        return "signature"
    if "fact" in lowered or "statement of the case" in lowered:
        return "facts"
    if "conclusion" in lowered or "relief" in lowered:
        return "relief"
    if "law" in lowered or "argument" in lowered or "standard" in lowered:
        return "argument"
    return "optional_clause"


def discover_blocks(document) -> list[BlockDefinition]:
    paragraphs = document.paragraphs
    nonempty = [index for index, paragraph in enumerate(paragraphs) if paragraph.text.strip()]
    if not nonempty:
        return [BlockDefinition("body", "Body", "optional_clause", 0, len(paragraphs), None)]

    boundaries = [index for index in nonempty if is_heading(paragraphs[index])]
    if not boundaries or boundaries[0] != nonempty[0]:
        boundaries.insert(0, nonempty[0])
    list_boundaries = set()
    for index in nonempty:
        if not LIST_PROMPT_RE.search(paragraphs[index].text):
            continue
        previous = max((boundary for boundary in boundaries if boundary < index), default=None)
        previous_type = classify_block(normalize_label(paragraphs[previous].text)) if previous is not None else "optional_clause"
        if previous_type != "facts":
            boundaries.append(index)
            list_boundaries.add(index)
    boundaries = sorted(set(boundaries))

    blocks = []
    keys = defaultdict(int)
    for position, start in enumerate(boundaries):
        end = boundaries[position + 1] if position + 1 < len(boundaries) else len(paragraphs)
        heading = is_heading(paragraphs[start]) and start not in list_boundaries
        if start in list_boundaries:
            raw_label = "Facts" if "fact" in paragraphs[start].text.lower() else "List items"
        else:
            raw_label = paragraphs[start].text if heading else ("Document body" if position == 0 else f"Section {position + 1}")
        label = normalize_label(raw_label) or f"Section {position + 1}"
        base_key = slugify(label)[:100] or f"section-{position + 1}"
        keys[base_key] += 1
        key = base_key if keys[base_key] == 1 else f"{base_key}-{keys[base_key]}"
        block_type = "facts" if start in list_boundaries else classify_block(label)
        sample = "\n".join(paragraph.text for paragraph in paragraphs[start:end])
        expects_list = block_type == "facts" or bool(LIST_PROMPT_RE.search(sample))
        blocks.append(BlockDefinition(key, label, block_type, start, end, start if heading else None, expects_list))
    return blocks


def _field_name(label: str, fallback: str) -> str:
    clean = label.strip().strip("*_?.,:;-/ ")
    return slugify(clean).replace("-", "_") or fallback.replace("-", "_")


def placeholder_expression(label: str, fallback: str) -> str:
    normalized = " ".join(label.lower().split()).strip(" .:_-")
    alias = PLACEHOLDER_ALIASES.get(normalized)
    if alias:
        return "{{ " + alias + " }}"
    if "address" in normalized and "attorney" not in normalized:
        return "{{ fields.premises_address }}"
    if normalized == "date" or normalized.endswith(" date"):
        return "{{ fields.filing_date }}"
    if "case caption" in normalized:
        return "{{ fields.case_caption }}"
    if "plaintiff" in normalized:
        return "{{ fields.plaintiff_name }}"
    if "signature block" in normalized:
        return "{{ advocate_contact }}"
    return "{{ fields." + _field_name(label, fallback) + " }}"


def convert_placeholder_text(text: str, fallback_prefix: str) -> tuple[str, list[str]]:
    fields = []
    counter = 0

    def replace(match):
        nonlocal counter
        counter += 1
        expression = placeholder_expression(match.group(1), f"{fallback_prefix}_{counter}")
        if expression.startswith("{{ fields."):
            fields.append(expression[3:-3].strip())
        return expression

    return BRACKET_RE.sub(replace, text), fields


def _set_paragraph_text_preserving_first_run(paragraph, text: str):
    runs = list(paragraph.runs)
    if runs:
        target = next((run for run in runs if run.text), runs[0])
        target.text = text
        for run in runs:
            if run is not target:
                run.text = ""
    else:
        paragraph.add_run(text)


def _marker_paragraph_like(paragraph, text: str):
    marker = deepcopy(paragraph._p)
    for child in list(marker):
        if child.tag != qn("w:pPr"):
            marker.remove(child)
    run = OxmlElement("w:r")
    node = OxmlElement("w:t")
    node.text = text
    run.append(node)
    marker.append(run)
    return marker


def _replace_with_loop(paragraph, expression: str):
    paragraph._p.addprevious(_marker_paragraph_like(paragraph, "{%p for item in " + expression + " %}"))
    _set_paragraph_text_preserving_first_run(paragraph, "{{ item }}")
    paragraph._p.addnext(_marker_paragraph_like(paragraph, "{%p endfor %}"))


def _all_story_paragraphs(document):
    """Yield main, table, header, and footer paragraphs without duplicates."""
    seen = set()

    def emit(paragraphs):
        for paragraph in paragraphs:
            identity = paragraph._p
            if identity not in seen:
                seen.add(identity)
                yield paragraph

    yield from emit(document.paragraphs)
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                yield from emit(cell.paragraphs)
    for section in document.sections:
        yield from emit(section.header.paragraphs)
        yield from emit(section.footer.paragraphs)
        for table in section.header.tables:
            for row in table.rows:
                for cell in row.cells:
                    yield from emit(cell.paragraphs)
        for table in section.footer.tables:
            for row in table.rows:
                for cell in row.cells:
                    yield from emit(cell.paragraphs)


def _converted_block_body(document, block: BlockDefinition) -> str:
    lines = []
    for index in range(block.body_start, block.end):
        text = document.paragraphs[index].text.strip()
        if not text:
            continue
        converted, _fields = convert_placeholder_text(text, f"{block.key}_{index}")
        lines.append(converted)
    return "\n".join(lines)


def annotate_document(document, blocks: list[BlockDefinition]) -> dict:
    """Add Jinja bindings while retaining the original package and paragraph XML."""
    fields = set()
    main_paragraphs = list(document.paragraphs)
    main_ids = {paragraph._p for paragraph in main_paragraphs}

    for block in blocks:
        body_paragraphs = [
            main_paragraphs[index]
            for index in range(block.body_start, block.end)
            if main_paragraphs[index].text.strip()
        ]
        list_prompt = next((p for p in body_paragraphs if LIST_PROMPT_RE.search(p.text)), None)
        if block.expects_list and body_paragraphs:
            loop_target = list_prompt or body_paragraphs[0]
            _replace_with_loop(loop_target, f'blocks["{block.key}"]["items"]')
            for paragraph in body_paragraphs:
                if paragraph is not loop_target and paragraph._p.getparent() is not None:
                    paragraph._p.getparent().remove(paragraph._p)

    for index, paragraph in enumerate(_all_story_paragraphs(document)):
        if not paragraph.text or "{%p " in paragraph.text or paragraph.text.strip() == "{{ item }}":
            continue
        converted, found = convert_placeholder_text(paragraph.text, f"placeholder_{index + 1}")
        fields.update(found)
        if converted != paragraph.text:
            _set_paragraph_text_preserving_first_run(paragraph, converted)

    # Main-story paragraphs that contain no explicit fill-in still bind to the
    # corresponding Lexical block. Headings remain literal structure.
    for block in blocks:
        slot = 0
        last_bound = None
        for index in range(block.body_start, block.end):
            paragraph = main_paragraphs[index]
            if not paragraph.text.strip() or paragraph._p not in main_ids or paragraph._p.getparent() is None:
                continue
            if paragraph.text.strip() == "{{ item }}" or paragraph.text.startswith("{%p "):
                continue
            _set_paragraph_text_preserving_first_run(
                paragraph,
                f'{{{{ blocks["{block.key}"]["paragraphs"][{slot}] }}}}',
            )
            slot += 1
            last_bound = paragraph
        if not block.expects_list and last_bound is not None:
            start = _marker_paragraph_like(
                last_bound,
                f'{{%p for item in blocks["{block.key}"]["paragraphs"][{slot}:] %}}',
            )
            item = _marker_paragraph_like(last_bound, "{{ item }}")
            end = _marker_paragraph_like(last_bound, "{%p endfor %}")
            last_bound._p.addnext(start)
            start.addnext(item)
            item.addnext(end)

    return {"fields": sorted(fields)}


def _copy_block_document(source_path: Path, output_path: Path, block: BlockDefinition):
    document = Document(source_path)
    body = document._body._element
    children = list(body)
    paragraphs = document.paragraphs
    start_element = paragraphs[min(block.start, len(paragraphs) - 1)]._p
    start_position = children.index(start_element)
    if block.end < len(paragraphs):
        end_position = children.index(paragraphs[block.end]._p)
    else:
        end_position = next((index for index, child in enumerate(children) if child.tag == qn("w:sectPr")), len(children))
    keep = set(children[start_position:end_position])
    for child in children:
        if child.tag == qn("w:sectPr"):
            continue
        if child not in keep:
            body.remove(child)
    local_paragraphs = document.paragraphs
    local_block = BlockDefinition(
        key=block.key,
        label=block.label,
        block_type=block.block_type,
        start=0,
        end=len(local_paragraphs),
        heading_index=0 if block.heading_index is not None else None,
        expects_list=block.expects_list,
    )
    annotate_document(document, [local_block])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(output_path)


def infer_kind(title: str) -> str:
    lowered = title.lower()
    if "motion" in lowered:
        return "motion"
    if "appeal" in lowered or "affidavit" in lowered or "notice" in lowered:
        return "brief"
    return "shell"


def ingest_docx(source: Path, prepared_root: Path, snippets_root: Path, *, force=False) -> Path:
    source = source.resolve()
    slug = slugify(source.stem) or "document-template"
    package_dir = prepared_root / slug
    package_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = package_dir / "manifest.yaml"
    source_checksum = sha256_file(source)
    if manifest_path.exists() and not force:
        existing = yaml.safe_load(manifest_path.read_text()) or {}
        if existing.get("source", {}).get("sha256") == source_checksum:
            return manifest_path

    original = Document(source)
    blocks = discover_blocks(original)
    block_bodies = {block.key: _converted_block_body(original, block) for block in blocks}

    annotated = Document(source)
    discovery = annotate_document(annotated, blocks)
    template_path = package_dir / "template.docx"
    annotated.save(template_path)

    block_rows = []
    for order, block in enumerate(blocks, start=1):
        relative_block_path = Path("docx-snippets") / slug / "blocks" / f"{block.key}.docx"
        block_path = snippets_root / slug / "blocks" / f"{block.key}.docx"
        _copy_block_document(source, block_path, block)
        block_rows.append(
            {
                "key": block.key,
                "label": block.label,
                "type": block.block_type,
                "order": order * 10,
                "required": True,
                "editable": True,
                "ai_fill_mode": "constrained_generation" if block.block_type in {"facts", "argument"} else "none",
                "body": block_bodies[block.key],
                "docx": relative_block_path.as_posix(),
                "sha256": sha256_file(block_path),
                "input": {
                    "type": "array" if block.expects_list else "rich_text",
                    "items": {"type": "string"} if block.expects_list else None,
                },
                "lexical": {
                    "node": "list" if block.expects_list else "paragraphs",
                    "listType": "number" if block.expects_list else None,
                    "sourceParagraphRange": [block.start, block.end],
                },
            }
        )

    try:
        source_path = source.relative_to(prepared_root.parent.resolve()).as_posix()
    except ValueError:
        source_path = source.as_posix()
    manifest = {
        "schema_version": MANIFEST_VERSION,
        "slug": slug,
        "title": source.stem,
        "kind": infer_kind(source.stem),
        "description": "Prepared from the maintained original Word template.",
        "jurisdiction": "Ohio",
        "source_label": "Content library",
        "active": True,
        "render": {"strategy": "full_document", "docx": "template.docx"},
        "source": {
            "path": source_path,
            "sha256": source_checksum,
            "converted_at": datetime.now(timezone.utc).isoformat(),
            "converter": "apps.templates_app.ingestion",
            "format_preservation": "in_place_ooxml",
        },
        "fields": discovery["fields"],
        "blocks": block_rows,
    }
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True))
    return manifest_path


def promote_shared_blocks(manifest_paths: list[Path], snippets_root: Path, *, force=False):
    candidates = defaultdict(list)
    for manifest_path in manifest_paths:
        manifest = yaml.safe_load(manifest_path.read_text()) or {}
        for block in manifest.get("blocks", []):
            if block.get("type") not in {"caption", "signature", "certificate"}:
                continue
            normalized = re.sub(r"\s+", " ", block.get("body", "")).strip().lower()
            if normalized:
                candidates[(block["type"], hashlib.sha256(normalized.encode()).hexdigest())].append(block)
    promoted = []
    for (block_type, _digest), rows in candidates.items():
        if len(rows) < 2:
            continue
        source = snippets_root.parent / rows[0]["docx"]
        destination = snippets_root / "_shared" / "blocks" / f"{block_type}.docx"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists() or force:
            shutil.copy2(source, destination)
        promoted.append(destination)
    return promoted


def ingest_directory(source_root: Path, prepared_root: Path, snippets_root: Path, *, force=False):
    manifests = [
        ingest_docx(path, prepared_root, snippets_root, force=force)
        for path in sorted(source_root.rglob("*.docx"))
        if not path.name.startswith("~$")
    ]
    promote_shared_blocks(manifests, snippets_root, force=force)
    return manifests
