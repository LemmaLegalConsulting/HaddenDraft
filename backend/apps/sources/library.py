"""Reading the managed content library as a shelf rather than as a search index.

Retrieval answers a question; browsing answers "what is in here?".  Both read the
same generated manifests, so a section a reader finds by walking the table of
contents is the same chunk a citation points at, with the same identifiers.

Manifests stay the index boundary: nothing here reaches past
``content_paths()`` into provider-specific storage.
"""

from __future__ import annotations

import re

import yaml

from apps.core.content_library import content_paths

# A code manifest is megabytes of generated YAML.  The pure-Python parser spends
# seconds on one, which every reader then waits through; libyaml does the same
# work about fifteen times faster and is what ships with PyYAML wheels.
_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

# Parsed manifests, keyed by the file's identity on disk.  Ingestion rewrites
# manifests in place, so the cache has to notice a regenerated file rather than
# hold the shape of the corpus from process start.
_MANIFEST_CACHE = {}


def manifest_paths():
    """Generated manifests, private overrides first, one entry per file."""
    paths = []
    for root in content_paths():
        paths.extend(sorted(root.joinpath("treatises", "markdown").glob("*/*/manifest.yaml")))
        paths.extend(sorted(root.joinpath("statutes").glob("*/manifest.yaml")))
        paths.extend(sorted(root.joinpath("ordinances").glob("*/manifest.yaml")))
    return list(dict.fromkeys(paths))


def load_manifest(path):
    """Parse a generated manifest, reusing the last parse of an unchanged file."""
    try:
        status = path.stat()
    except OSError:
        return None
    fingerprint = (status.st_mtime_ns, status.st_size)
    cached = _MANIFEST_CACHE.get(str(path))
    if cached and cached[0] == fingerprint:
        return cached[1]
    try:
        manifest = yaml.load(path.read_text(encoding="utf-8"), Loader=_LOADER) or {}
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(manifest, dict):
        return None
    _MANIFEST_CACHE[str(path)] = (fingerprint, manifest)
    return manifest


def library_manifests():
    """(path, manifest) per document slug.

    A private copy of a document shadows the public one exactly as it does
    during retrieval, so the shelf and the search results never disagree about
    which edition is in use.
    """
    found = {}
    for path in manifest_paths():
        manifest = load_manifest(path)
        slug = (manifest or {}).get("document_slug")
        if not slug or slug in found:
            continue
        found[slug] = (path, manifest)
    return list(found.values())


# Shelves a document can sit on.  Anything unrecognized reads as a treatise,
# which is where the library started and where a secondary source belongs.
CONTENT_KINDS = {"statute", "ordinance"}


def _content_kind(manifest):
    kind = manifest.get("content_kind")
    return kind if kind in CONTENT_KINDS else "treatise"


def document_summary(path, manifest):
    chunks = [chunk for chunk in manifest.get("chunks", []) if isinstance(chunk, dict)]
    return {
        "slug": str(manifest.get("document_slug", "")),
        "title": str(manifest.get("document_title", "Untitled document")),
        # Manifests are generated, so a version may arrive as a bare year.
        "version": str(manifest.get("document_version", "") or ""),
        "jurisdiction": str(manifest.get("jurisdiction", "") or ""),
        "contentKind": _content_kind(manifest),
        "publisher": str(manifest.get("publisher", "") or ""),
        "sourceName": str(manifest.get("source_name", "") or ""),
        "sourceBaseUrl": str(manifest.get("source_base_url", "") or ""),
        "sourcePath": str(manifest.get("source_path", "") or ""),
        "generatedAt": str(manifest.get("generated_at", "") or ""),
        "pdfPages": manifest.get("pdf_pages", 0),
        "sectionCount": manifest.get("section_count", 0) or len(chunks),
        "chunkCount": manifest.get("chunk_count", 0) or len(chunks),
        "manifestName": path.parent.name,
        # Local law is shelved by municipality, and a municipality whose
        # authorities are all declared-but-unacquired is a real row with zero
        # readable sections.  Saying so is the point of carrying the count.
        "municipality": str(manifest.get("municipality", "") or ""),
        "county": str(manifest.get("county", "") or ""),
        "pendingCount": manifest.get("pending_count", 0) or 0,
    }


def library_documents():
    documents = [document_summary(path, manifest) for path, manifest in library_manifests()]
    return sorted(documents, key=lambda item: (item["contentKind"], item["title"]))


def find_document(document_slug):
    for path, manifest in library_manifests():
        if manifest.get("document_slug") == document_slug:
            return path, manifest
    return None, None


def document_chunks(manifest_path, manifest):
    """Chunk descriptors that have a readable generated file behind them.

    A manifest entry whose file is missing would otherwise become a table-of-
    contents row that opens nothing.
    """
    chunks = []
    for item in manifest.get("chunks", []):
        if not isinstance(item, dict) or not item.get("file"):
            continue
        if not (manifest_path.parent / item["file"]).is_file():
            continue
        heading = item.get("heading") or "Untitled section"
        chunks.append({
            "id": str(item.get("id") or ""),
            "heading": heading,
            "path": [str(part) for part in (item.get("path") or []) if str(part).strip()],
            "pages": item.get("pages", []),
            "citation": item.get("citation", ""),
            "effectiveDate": item.get("effective_date", ""),
            "contentKind": item.get("content_kind", ""),
            "section": str(item.get("section") or ""),
            "chapter": str(item.get("chapter") or ""),
        })
    return chunks


def _terms(value):
    return [term for term in re.findall(r"[a-z0-9§.]+", (value or "").casefold()) if term]


def filter_chunks(chunks, query):
    """Narrow the table of contents by heading, path, citation, and section.

    Deliberately not a full-text search: browsing is for finding a section you
    can name, and a heading match keeps the surrounding structure meaningful.
    Full-text lookup remains the job of the research search.
    """
    terms = _terms(query)
    if not terms:
        return list(chunks)
    matched = []
    for chunk in chunks:
        haystack = " ".join([
            chunk["heading"],
            " ".join(chunk["path"]),
            chunk["citation"],
            chunk["section"],
            chunk["chapter"],
        ]).casefold()
        if all(term in haystack for term in terms):
            matched.append(chunk)
    return matched


def _node_id(path_key, suffix=""):
    joined = "/".join(path_key)
    return f"{joined}#{suffix}" if suffix else joined


def _leaf(chunk, node_id):
    return {
        "id": node_id,
        "label": chunk["heading"],
        "chunkId": chunk["id"],
        "citation": chunk["citation"],
        "effectiveDate": chunk["effectiveDate"],
        "pages": chunk["pages"],
        "children": [],
        "count": 1,
    }


def _count(node):
    node["count"] = (1 if node["chunkId"] else 0) + sum(_count(child) for child in node["children"])
    return node["count"]


def section_tree(chunks, *, document_title=""):
    """Nest chunks under their generated section path.

    Sections that produced a single chunk become the node itself; a section
    split across several chunks keeps one child per part, so the tree mirrors
    the document instead of the chunker.
    """
    roots = []
    nodes = {}

    def ensure(path_key):
        children = roots
        node = None
        for depth, label in enumerate(path_key):
            key = tuple(path_key[: depth + 1])
            node = nodes.get(key)
            if node is None:
                node = {
                    "id": _node_id(key),
                    "label": label,
                    "chunkId": "",
                    "citation": "",
                    "effectiveDate": "",
                    "pages": [],
                    "children": [],
                    "count": 0,
                }
                nodes[key] = node
                children.append(node)
            children = node["children"]
        return node

    grouped = {}
    for chunk in chunks:
        path_key = tuple(chunk["path"]) or (chunk["heading"],)
        grouped.setdefault(path_key, []).append(chunk)

    for path_key, items in grouped.items():
        node = ensure(path_key)
        if len(items) == 1 and not node["chunkId"]:
            chunk = items[0]
            node.update({
                "chunkId": chunk["id"],
                "citation": chunk["citation"],
                "effectiveDate": chunk["effectiveDate"],
                "pages": chunk["pages"],
            })
            continue
        for index, chunk in enumerate(items, start=1):
            node["children"].append(_leaf(chunk, _node_id(path_key, f"{index}")))

    # A code whose every section hangs off one root named after the code itself
    # ("Ohio Revised Code") would otherwise open onto a single row the reader
    # has to expand before seeing any chapter.  Only that repeated title is
    # dropped: a lone chapter left by a filter is still the real structure.
    title = (document_title or "").strip().casefold()
    if len(roots) == 1 and roots[0]["children"] and not roots[0]["chunkId"] and roots[0]["label"].strip().casefold() == title:
        roots = roots[0]["children"]

    for node in roots:
        _count(node)
    return roots
