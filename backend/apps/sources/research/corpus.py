"""What research mode indexes, and the metadata a reader judges a result by.

One record per retrievable passage, drawn from the two places this application
keeps law: the generated content library (statutes, local ordinances, treatises
and handbooks) and the imported case-law corpus. Records are deliberately flat
-- the index does not care which store a passage came from, and the facets are
the same shape for all of them -- so that a search can be narrowed by court or
municipality without the caller knowing which corpus answers.

Manifests remain the index boundary for library content: nothing here reaches
past ``content_paths()`` into provider-specific storage.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml
from django.db import models

from apps.core.jurisdictions import appellate_district, canonical_county
from apps.sources.library import load_manifest, manifest_paths


CASES = "cases"
STATUTES = "statutes"
ORDINANCES = "ordinances"
TREATISES = "treatises"
CORPORA = (CASES, STATUTES, ORDINANCES, TREATISES)

CORPUS_LABELS = {
    CASES: "Case law",
    STATUTES: "Statutes",
    ORDINANCES: "Local ordinances and court rules",
    TREATISES: "Treatises and handbooks",
}

# Model-written abstractions of an opinion rank above its raw OCR because they
# are where a researcher's phrasing tends to land. The OCR is indexed too: it is
# the only place an exact quotation actually lives.
CASE_DOCUMENT_WEIGHTS = {
    "keywords": 1.6,
    "issues": 1.5,
    "holdings": 1.45,
    "rules": 1.4,
    "overview": 1.3,
    "facts": 1.2,
    "outcome": 1.15,
    "procedural_posture": 1.1,
    "ocr_chunk": 1.0,
}

CASE_DOCUMENT_LABELS = {
    "keywords": "Search keywords",
    "issues": "Issues",
    "holdings": "Holdings",
    "rules": "Rules applied",
    "overview": "Overview",
    "facts": "Facts",
    "outcome": "Outcome",
    "procedural_posture": "Procedural posture",
    "ocr_chunk": "Opinion text",
}


@dataclass
class IndexRecord:
    """One indexed passage: what it says, where it is, and how to open it.

    ``text`` is stored with its whitespace already collapsed. Exact-phrase
    matching has to run over a form where a phrase cannot be broken by a line
    wrap, and collapsing once at build time costs a second across the whole
    corpus where collapsing per query costs seconds per search.

    ``group_key`` is what a result list counts as one thing. A decision reaches
    the index as eight or ten passages -- its issues, its holdings, each chunk
    of its opinion text -- and a reader looking for a case wants the case once,
    not once per passage that happened to match.

    ``authority_citation`` is the record's own citation when the record *is* an
    authority -- a code section, an ordinance, a decision. A treatise chunk has
    no such citation: what it carries is a location within a book, which names
    every section the heading happens to mention. Telling the two apart is what
    lets a search for ``R.C. 5321.04`` return the section before the chapter of
    commentary that discusses it thirty times.
    """

    key: str
    group_key: str
    corpus: str
    title: str
    text: str
    citation: str = ""
    authority_citation: str = ""
    url: str = ""
    weight: float = 1.0
    facets: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    open_target: dict = field(default_factory=dict)


def _county(value):
    """A county as the shared vocabulary spells it.

    Canonicalizing on the way out as well as on the way in is what lets a
    corpus imported before the vocabulary existed group correctly: the facet
    offers "Cuyahoga" once, with every decision under it, rather than offering
    it twice with the cases split between the spellings.
    """
    return canonical_county(value)


def compact(text):
    """Collapse whitespace so a phrase cannot be split by a line wrap."""
    return " ".join(str(text or "").split())


def _chunk_text(path):
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    marker = "## Source text"
    return text.split(marker, 1)[-1].strip() if marker in text else text.strip()


def _manifest_corpus(manifest):
    kind = str(manifest.get("content_kind") or "")
    if kind == "statute":
        return STATUTES
    if kind == "ordinance":
        return ORDINANCES
    return TREATISES


def _library_citation(manifest, chunk, section_path):
    if chunk.get("citation"):
        effective = chunk.get("effective_date")
        return f"{chunk['citation']} (effective {effective})" if effective else str(chunk["citation"])
    pages = chunk.get("pages") or []
    version = f", {manifest['document_version']}" if manifest.get("document_version") else ""
    location = " > ".join(section_path)
    if pages:
        first, last = pages[0], pages[-1]
        page_text = f"PDF p. {first}" if first == last else f"PDF pp. {first}–{last}"
        return f"{manifest.get('document_title', 'Source')}{version}, {location} ({page_text})"
    return f"{manifest.get('document_title', 'Source')}{version}, {location}"


def library_records():
    """One record per generated content chunk, private overrides shadowing public ones."""
    records = []
    seen_documents = set()
    for manifest_path in manifest_paths():
        manifest = load_manifest(manifest_path)
        if not manifest:
            continue
        slug = str(manifest.get("document_slug") or "")
        if not slug or slug in seen_documents:
            continue
        seen_documents.add(slug)
        corpus = _manifest_corpus(manifest)
        courts = [str(court.get("name") or "") for court in manifest.get("courts") or [] if isinstance(court, dict)]
        county = _county(manifest.get("county") or "")
        for chunk in manifest.get("chunks") or []:
            if not isinstance(chunk, dict) or not chunk.get("file"):
                continue
            chunk_path = manifest_path.parent / chunk["file"]
            if not chunk_path.is_file():
                continue
            text = _chunk_text(chunk_path)
            if not text:
                continue
            section_path = [str(part) for part in chunk.get("path") or []]
            heading = str(chunk.get("heading") or "Untitled section")
            effective_date = str(chunk.get("effective_date") or "")
            records.append(IndexRecord(
                key=f"content:{slug}:{chunk.get('id')}",
                group_key=f"content:{slug}:{chunk.get('id')}",
                corpus=corpus,
                title=f"{manifest.get('document_title', 'Source')} — {heading}",
                text=compact(" \n ".join([heading, *section_path, *(chunk.get("retrieval_hints") or []), text])),
                citation=_library_citation(manifest, chunk, section_path),
                authority_citation=str(chunk.get("citation") or ""),
                url=str(chunk.get("url") or ""),
                facets={
                    "sourceType": corpus,
                    "documentSlug": slug,
                    "municipality": str(manifest.get("municipality") or ""),
                    "county": county,
                    "appellateDistrict": appellate_district(county),
                    "court": courts[0] if courts else "",
                    "year": effective_date[:4],
                    "publicationStatus": "",
                    "judge": "",
                    "title": manifest.get("document_title", ""),
                },
                metadata={
                    "documentTitle": manifest.get("document_title", ""),
                    "documentVersion": manifest.get("document_version", ""),
                    "documentSlug": slug,
                    "chunkId": chunk.get("id"),
                    "heading": heading,
                    "sectionPath": section_path,
                    "contentKind": chunk.get("content_kind", ""),
                    "pdfPages": chunk.get("pages") or [],
                    "sourcePath": chunk.get("source_path") or manifest.get("source_path", ""),
                    "sourceSha256": chunk.get("source_sha256") or manifest.get("source_sha256", ""),
                    "jurisdiction": manifest.get("jurisdiction", ""),
                    "effectiveDate": effective_date,
                    "textBasis": chunk.get("text_basis", ""),
                    "municipality": manifest.get("municipality", ""),
                    "county": county,
                    "corpusLabel": CORPUS_LABELS[corpus],
                },
                open_target={
                    "kind": "content",
                    "documentSlug": slug,
                    "chunkId": str(chunk.get("id") or ""),
                    "sourceUrl": f"/api/sources/content/{slug}/{chunk.get('id')}/",
                    "pdfUrl": f"/api/sources/content/{slug}/{chunk.get('id')}/pdf/" if (chunk.get("source_path") or manifest.get("source_path")) else "",
                    "pages": chunk.get("pages") or [],
                },
            ))
    return records


def _case_title(decision):
    return decision.short_title or decision.title


def _case_citation(decision):
    if decision.citation_string:
        return decision.citation_string
    parts = [_case_title(decision)]
    if decision.docket_number:
        parts.append(f"No. {decision.docket_number}")
    if decision.court:
        parts.append(decision.court)
    if decision.decision_date:
        parts.append(decision.decision_date.isoformat())
    return ", ".join(parts)


def case_records():
    """One record per case-law search document, opinion text included.

    Every document type is indexed, not only the model-written abstractions:
    an exact quotation exists nowhere but the OCR, and a phrase search that
    skipped it would report a decision as not containing words it prints.
    """
    from apps.caselaw.models import CaseLawSearchDocument
    from apps.caselaw.values import text_values

    records = []
    queryset = (
        CaseLawSearchDocument.objects
        .filter(decision__approved_for_search=True)
        .select_related("decision")
        .only(
            "id", "document_type", "title", "search_text", "decision_id",
            "decision__id", "decision__title", "decision__short_title", "decision__court",
            "decision__county", "decision__judge", "decision__decision_date", "decision__entry_date",
            "decision__publication_status", "decision__precedential_status", "decision__authority_level",
            "decision__treatment_status", "decision__negative_treatment_type", "decision__vacated_date",
            "decision__reversed_date", "decision__overruled_by", "decision__metadata_verified",
            "decision__approved_for_drafting", "decision__citation_string", "decision__docket_number",
            "decision__case_number", "decision__jurisdiction", "decision__issues",
            "decision__search_keywords", "decision__statutes_cited", "decision__regulations_cited",
            "decision__cases_cited", "decision__source_sha256", "decision__parallel_citations",
        )
        .iterator(chunk_size=500)
    )
    for document in queryset:
        decision = document.decision
        text = document.search_text or ""
        if not text.strip():
            continue
        county = _county(decision.county or "")
        decision_date = decision.decision_date or decision.entry_date
        superseded = bool(
            decision.negative_treatment_type or decision.vacated_date
            or decision.reversed_date or decision.overruled_by
        )
        records.append(IndexRecord(
            key=f"case:{decision.id}:{document.id}",
            group_key=f"case:{decision.id}",
            corpus=CASES,
            title=_case_title(decision),
            text=compact(" ".join([document.title or "", str(decision.citation_string or ""), text])),
            citation=_case_citation(decision),
            authority_citation=" ".join([
                str(decision.citation_string or ""),
                *(str(value) for value in (decision.parallel_citations or []) if isinstance(value, str)),
            ]).strip(),
            url=f"/api/caselaw/decisions/{decision.id}/",
            weight=CASE_DOCUMENT_WEIGHTS.get(document.document_type, 1.0),
            facets={
                "sourceType": CASES,
                "documentSlug": "",
                "municipality": "",
                "county": county,
                "appellateDistrict": appellate_district(county),
                "court": decision.court or "",
                "year": decision_date.isoformat()[:4] if decision_date else "",
                "publicationStatus": decision.publication_status or "",
                "judge": decision.judge or "",
                "title": _case_title(decision),
            },
            metadata={
                "decisionId": decision.id,
                "documentType": document.document_type,
                "documentTypeLabel": CASE_DOCUMENT_LABELS.get(document.document_type, document.document_type),
                "court": decision.court,
                "county": county,
                "judge": decision.judge,
                "decisionDate": decision_date.isoformat() if decision_date else None,
                "publicationStatus": decision.publication_status,
                "precedentialStatus": decision.precedential_status,
                "authorityLevel": decision.authority_level,
                "treatmentStatus": decision.treatment_status,
                "metadataVerified": decision.metadata_verified,
                "approvedForDrafting": decision.approved_for_drafting,
                "jurisdiction": decision.jurisdiction,
                "docketNumber": decision.docket_number,
                "issues": text_values(decision.issues),
                "searchKeywords": text_values(decision.search_keywords),
                "statutesCited": text_values(decision.statutes_cited),
                "regulationsCited": text_values(decision.regulations_cited),
                "casesCited": text_values(decision.cases_cited),
                "sourceSha256": decision.source_sha256,
                "supersededOrCriticized": superseded,
                "corpusLabel": CORPUS_LABELS[CASES],
                "warning": "Treatment/currentness has not been checked." if decision.treatment_status == "unchecked" else "",
            },
            open_target={
                "kind": "caselaw",
                "decisionId": decision.id,
                "sourceUrl": f"/api/caselaw/decisions/{decision.id}/",
                "pdfUrl": f"/api/caselaw/decisions/{decision.id}/pdf/",
                "pages": [],
            },
        ))
    return records


def managed_records():
    """Published operator-maintained chunks, selected through the atomic DB pointer."""
    from apps.sources.models import ManagedSourceChunk

    kind_to_corpus = {
        "case": CASES, "statute": STATUTES, "ordinance": ORDINANCES,
        "treatise": TREATISES, "other": TREATISES,
    }
    records = []
    queryset = (
        ManagedSourceChunk.objects
        .filter(
            version__source__state="published",
            version__source__current_version_id=models.F("version_id"),
        )
        .select_related("version", "version__source")
        .iterator(chunk_size=500)
    )
    for chunk in queryset:
        source = chunk.version.source
        corpus = kind_to_corpus.get(source.kind, TREATISES)
        date = source.decision_date
        citation = source.citation or (
            f"{source.title}, {source.court}, {date.isoformat()}"
            if source.kind == "case" and date else source.title
        )
        records.append(IndexRecord(
            key=f"managed:{source.id}:{chunk.version_id}:{chunk.ordinal}",
            group_key=f"managed:{source.id}",
            corpus=corpus,
            title=source.title,
            text=compact(" ".join([source.title, source.citation, chunk.heading, chunk.text])),
            citation=citation,
            authority_citation=source.citation,
            facets={
                "sourceType": corpus, "documentSlug": source.slug,
                "municipality": source.municipality, "county": _county(source.county),
                "appellateDistrict": source.appellate_district or appellate_district(source.county),
                "court": source.court, "year": date.isoformat()[:4] if date else "",
                "publicationStatus": source.publication_status, "judge": "", "title": source.title,
            },
            metadata={
                "managedSourceId": source.id, "managedSourceVersionId": chunk.version_id,
                "versionNumber": chunk.version.number, "chunkOrdinal": chunk.ordinal,
                "sourceSha256": chunk.version.sha256, "chunkSha256": chunk.sha256,
                "sourceLocator": source.source_locator, "sourceSystemId": source.source_system_id,
                "storageManifestKey": chunk.version.published_manifest_key,
                "jurisdiction": source.jurisdiction, "court": source.court,
                "county": _county(source.county), "municipality": source.municipality,
                "decisionDate": date.isoformat() if date else None,
                "publicationStatus": source.publication_status, "corpusLabel": CORPUS_LABELS[corpus],
            },
            open_target={
                "kind": "managed", "sourceId": source.id, "versionId": chunk.version_id,
                "sourceUrl": f"/api/sources/managed/{source.id}/{chunk.ordinal}/",
                "pdfUrl": (
                    f"/api/sources/managed/{source.id}/{chunk.ordinal}/pdf/"
                    if chunk.version.content_type == "application/pdf" else ""
                ),
                "pages": [value for value in (chunk.page_start, chunk.page_end) if value],
            },
        ))
    return records
