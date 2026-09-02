"""Local law as a first-class source: coverage, structured datasets, and links.

Three things separate a local-law corpus from the statute corpus it otherwise
resembles.

The first is that *absence is information*.  A municipality can have an
ordinance that matters enormously and no permitted way to retrieve its text, so
the corpus records the authority as declared-but-unacquired.  ``coverage()``
reports those alongside what was ingested, because a reader who is told nothing
about Lakewood will assume Lakewood has nothing.

The second is that the interesting content is often not prose.  Whether tender
must be accepted, what it must cover, and whether a rental-assistance guarantee
counts are facts a lawyer compares across cities, so they live in reviewable
YAML datasets with a stated basis per field rather than only inside embeddings.

The third is that a local ordinance is only half an argument.  It operates
against R.C. 5321.19, which may preempt it; against R.C. 1923, which it
defends; and against a treatise section and cases that show how courts read it.
``cross_references()`` resolves those links in both directions, so reading the
preemption statute shows every local provision exposed to it.
"""

from __future__ import annotations

import re

import yaml

from apps.core.content_library import content_path, content_paths
from apps.sources.library import library_manifests

DATASET_DIR = ("ordinances", "datasets")
SCOPE_PATH = ("ordinances", "scope.yaml")


def _manifests_of_kind(kind):
    return [(path, manifest) for path, manifest in library_manifests() if manifest.get("content_kind") == kind]


def ordinance_manifests():
    return _manifests_of_kind("ordinance")


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------

def authority_overrides():
    """Active admin corrections, keyed by the authority they patch."""
    from apps.sources.models import OrdinanceOverride

    return {
        (override.municipality_slug, override.target_key): override
        for override in OrdinanceOverride.objects.filter(is_active=True)
    }


def authority_documents():
    """Admin-managed documents, keyed by authority, active ones first."""
    from apps.sources.models import OrdinanceDocument

    grouped = {}
    for document in OrdinanceDocument.objects.all():
        grouped.setdefault(document.authority_key, []).append(document)
    for documents in grouped.values():
        documents.sort(key=lambda item: (item.status != "active", item.created_at))
    return grouped


def _document_summary(document):
    return {
        "id": document.id,
        "title": document.title,
        "sourceType": document.source_type,
        "status": document.status,
        "url": document.url,
        "hasFile": bool(document.storage_key),
        "sha256": document.sha256,
        "verified": document.verified,
        "verifiedBy": document.verified_by,
        "supersededById": document.superseded_by_id,
        "notes": document.notes,
    }


def _section_summary(manifest, section, *, override=None, documents=()):
    """One authority, said plainly enough to be judged.

    ``textBasis`` is the load-bearing field.  An enacted act is what the
    council passed, which is not the same as the chapter as it stands today,
    and a reader who is not told the difference will assume the stronger one.
    """
    summary = {
        "key": str(section.get("key", "")),
        "topic": str(section.get("topic", "")),
        "topicLabel": str(section.get("topic_label", "")),
        "priority": section.get("priority"),
        "citation": str(section.get("citation", "")),
        "title": str(section.get("title", "")),
        "status": str(section.get("status", "")),
        "pendingReason": str(section.get("pending_reason", "")),
        "notInForceReason": str(section.get("not_in_force_reason", "")),
        "repealedBy": str(section.get("repealed_by", "")),
        "textBasis": str(section.get("text_basis", "")),
        "acquisitionMethod": str(section.get("acquisition_method", "")),
        "actFileNumber": str(section.get("act_file_number", "")),
        "actTitle": str(section.get("act_title", "")),
        "enactedDate": str(section.get("enacted_date", "")),
        "effectiveDate": str(section.get("effective_date", "")),
        "amendedDate": str(section.get("amended_date", "")),
        "repealDate": str(section.get("repeal_date", "")),
        "amendmentHistory": section.get("amendment_history", []) or [],
        "preemption": section.get("preemption", {}) or {},
        "notes": str(section.get("notes", "")),
        "codifierUrl": str(section.get("codifier_url", "")),
        "sourceUrl": str(section.get("source_url", "")),
        "verificationUrls": section.get("verification_urls", []) or [],
        "retrievedAt": str(section.get("retrieved_at", "")),
        "documentSlug": str(manifest.get("document_slug", "")),
        "chunkIds": [str(chunk.get("id", "")) for chunk in section.get("chunks", []) or []],
        "sourceType": str(section.get("source_type", "")),
        "enactedAs": str(section.get("enacted_as", "")),
        "extraction": section.get("extraction", {}) or {},
        "legalStatus": "in_force",
        "documents": [_document_summary(document) for document in documents],
        "overriddenFields": [],
    }
    if override is not None:
        # An override patches; a blank admin field leaves the generated value
        # alone rather than erasing it, so a later ingestion can still improve
        # a field nobody has corrected.
        applied = override.applied_fields()
        preemption = applied.pop("preemption", None)
        if preemption:
            summary["preemption"] = {**summary["preemption"], **preemption}
        summary.update(applied)
        summary["overriddenFields"] = sorted([*applied, *(["preemption"] if preemption else [])])
        summary["reviewedBy"] = override.reviewed_by
        summary["overrideNotes"] = override.notes
    return summary


def coverage():
    """Every municipality in the corpus, ingested and pending alike."""
    municipalities = []
    overrides = authority_overrides()
    documents = authority_documents()
    for _path, manifest in ordinance_manifests():
        slug = str(manifest.get("municipality_slug", ""))
        sections = [
            _section_summary(
                manifest, section,
                override=overrides.get((slug, str(section.get("key", "")))),
                documents=documents.get((slug, str(section.get("key", ""))), ()),
            )
            for section in manifest.get("sections", [])
        ]
        municipalities.append({
            "slug": str(manifest.get("document_slug", "")),
            "municipality": str(manifest.get("municipality", "")),
            "county": str(manifest.get("county", "")),
            "documentTitle": str(manifest.get("document_title", "")),
            "codeShortName": str(manifest.get("code_short_name", "")),
            "codifier": str(manifest.get("codifier", "")),
            "codifierUrl": str(manifest.get("source_base_url", "")),
            "courts": manifest.get("courts", []) or [],
            "generatedAt": str(manifest.get("generated_at", "")),
            "updateNote": str(manifest.get("update_note", "")),
            "preemptionStatute": str(manifest.get("preemption_statute", "")),
            "sections": sections,
            "ingestedCount": len([item for item in sections if item["status"] == "ingested"]),
            "pendingCount": len([item for item in sections if item["status"] == "pending"]),
            "notInForceCount": len([item for item in sections if item["status"] == "no_current_provision"]),
        })
    municipalities.sort(key=lambda item: item["municipality"] or item["slug"])

    declared = []
    scope = _load_scope()
    covered = {item["municipality"] for item in municipalities}
    for entry in scope.get("declared_municipalities", []) or []:
        if not isinstance(entry, dict) or entry.get("name") in covered:
            continue
        declared.append({
            "slug": str(entry.get("slug", "")),
            "municipality": str(entry.get("name", "")),
            "county": str(entry.get("county", "")),
            "topics": [str(topic) for topic in entry.get("topics", []) or []],
        })
    return {
        "municipalities": municipalities,
        "declared": declared,
        "topics": scope.get("topics", {}) or {},
        "ingestedCount": sum(item["ingestedCount"] for item in municipalities),
        "pendingCount": sum(item["pendingCount"] for item in municipalities),
        "notInForceCount": sum(item["notInForceCount"] for item in municipalities),
    }


def _load_scope():
    try:
        payload = yaml.safe_load(content_path(*SCOPE_PATH).read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return payload if isinstance(payload, dict) else {}


# ---------------------------------------------------------------------------
# Structured datasets
# ---------------------------------------------------------------------------

def dataset_names():
    names = []
    for directory in content_paths(*DATASET_DIR):
        names.extend(sorted(path.stem for path in directory.glob("*.yaml")))
    return list(dict.fromkeys(names))


def dataset(name):
    """One comparison dataset with its per-field sources resolved to citations.

    A field's ``basis`` is kept verbatim.  Resolution only turns the source key
    into something openable; it never upgrades how well-established a value is.
    """
    if not re.fullmatch(r"[a-z0-9-]+", str(name or "")):
        return None
    for directory in content_paths(*DATASET_DIR):
        path = directory / f"{name}.yaml"
        if not path.is_file():
            continue
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            return None
        if not isinstance(payload, dict):
            return None
        sources = payload.get("sources", {}) or {}
        records = []
        for record in payload.get("records", []) or []:
            if not isinstance(record, dict):
                continue
            fields = {}
            for field_name, field in (record.get("fields") or {}).items():
                if not isinstance(field, dict):
                    continue
                fields[field_name] = {
                    "value": field.get("value"),
                    "basis": str(field.get("basis", "unknown")),
                    "note": " ".join(str(field.get("note", "")).split()),
                    "source": _resolve_source(sources.get(field.get("source"), {}), field.get("source")),
                }
            records.append({
                "municipality": str(record.get("municipality", "")),
                "citation": str(record.get("citation", "")),
                "enactingAct": str(record.get("enacting_act", "")),
                # A repealed chapter's fields are history.  Carrying the status
                # out with them is what stops the comparison table from
                # presenting a dead ordinance as one a tenant can invoke.
                "status": str(record.get("status", "in_force")),
                "repealDate": str(record.get("repeal_date", "")),
                "repealedBy": str(record.get("repealed_by", "")),
                "shapeNote": " ".join(str(record.get("shape_note", "")).split()),
                "caveat": " ".join(str(record.get("caveat", "")).split()),
                "basisNote": " ".join(str(record.get("basis_note", "")).split()),
                "fields": fields,
            })
        return {
            "name": name,
            "title": str(payload.get("title", name)),
            "jurisdiction": str(payload.get("jurisdiction", "")),
            "vocabularies": payload.get("vocabularies", {}) or {},
            "records": records,
        }
    return None


def _resolve_source(source, key):
    if not source:
        return None
    resolved = {
        "key": str(key or ""),
        "citation": str(source.get("citation", "")),
        "caveat": " ".join(str(source.get("caveat", "")).split()),
        "documentSlug": str(source.get("document", "")),
        "chunkId": str(source.get("chunk", "")),
    }
    if resolved["documentSlug"] and resolved["chunkId"]:
        resolved["sourceId"] = f"content:{resolved['documentSlug']}:{resolved['chunkId']}"
    return resolved


# ---------------------------------------------------------------------------
# Coverage notices
# ---------------------------------------------------------------------------

# A notice is capped hard.  It exists to stop a wrong answer, not to become one.
MAX_NOTICES = 2


def _names_municipality(query, name):
    """Whether the question actually asks about this municipality.

    The city name is the gate.  Without it a general question about pay-to-stay
    would collect a notice from every city the corpus cannot reach, which
    buries the four ordinances it can.
    """
    if not name:
        return False
    return re.search(rf"\b{re.escape(name)}\b", query or "", re.IGNORECASE) is not None


def _named_municipalities(query, names):
    """The municipalities a question actually asks about.

    Ohio's city names nest: "Cleveland Heights" contains "Cleveland", and
    "South Euclid" contains "Euclid".  A plain name match therefore answers a
    question about Cleveland Heights with a notice about Cleveland, which is
    the same substitution this whole mechanism exists to prevent.  The longest
    matched name wins, and a name contained in it is dropped.
    """
    matched = [name for name in dict.fromkeys(names) if _names_municipality(query, name)]
    return {
        name for name in matched
        if not any(other != name and name.casefold() in other.casefold() for other in matched)
    }


def _topic_matches(query, *labels):
    words = {word for label in labels for word in re.findall(r"[a-z]{4,}", str(label).casefold())}
    asked = set(re.findall(r"[a-z]{4,}", (query or "").casefold()))
    return bool(words & asked)


def pending_notices(query):
    """Authorities this corpus knows of but holds no text for, for one query.

    Search is where the question actually gets asked, so this is where the gap
    has to be visible.  Ask about Lakewood's pay-to-stay ordinance against a
    corpus that cannot reach Lakewood's code and the ranked results are
    Toledo's chapter and Cleveland's section -- other cities' law, on their own
    terms, with nothing saying Lakewood has its own.  That is a worse answer
    than silence, because it looks like an answer.

    A notice carries no ordinance text.  It names the authority, says the text
    is not held and why, and links the codifier so the reader can go read it.
    """
    scope = _load_scope()
    candidates = [str(manifest.get("municipality", "")) for _path, manifest in ordinance_manifests()]
    candidates += [
        str(entry.get("name", "")) for entry in scope.get("declared_municipalities", []) or []
        if isinstance(entry, dict)
    ]
    named = _named_municipalities(query, candidates)

    notices = []
    overrides = authority_overrides()
    for _path, manifest in ordinance_manifests():
        name = str(manifest.get("municipality", ""))
        if name not in named:
            continue
        slug = str(manifest.get("municipality_slug", ""))
        for section in manifest.get("sections", []) or []:
            if section.get("status") not in {"pending", "no_current_provision"}:
                continue
            override = overrides.get((slug, str(section.get("key", ""))))
            overridden = override.applied_fields() if override else {}
            notices.append({
                "id": f"ordinance-coverage:{manifest.get('municipality_slug', '')}:{section.get('key', '')}",
                "municipality": name,
                "citation": overridden.get("citation") or str(section.get("citation", "")),
                "title": overridden.get("title") or str(section.get("title", "")),
                "topic": str(section.get("topic", "")),
                "topicLabel": str(section.get("topic_label", "")),
                "reason": str(section.get("pending_reason", "")),
                "inForce": section.get("status") != "no_current_provision",
                "notInForceReason": str(section.get("not_in_force_reason", "")),
                "repealDate": str(section.get("repeal_date", "")),
                "legalStatus": overridden.get("legalStatus", ""),
                "overrideRepealDate": overridden.get("repealDate", ""),
                "url": str(section.get("codifier_url", "") or manifest.get("source_base_url", "")),
                "notes": str(section.get("notes", "")),
                "summary": None if section.get("status") == "no_current_provision" else _dataset_summary(
                    str(manifest.get("municipality_slug", "")), str(section.get("topic", "")),
                ),
                "onTopic": _topic_matches(query, section.get("topic", ""), section.get("topic_label", "")),
            })

    for entry in scope.get("declared_municipalities", []) or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", ""))
        if name not in named:
            continue
        topics = [str(topic) for topic in entry.get("topics", []) or []]
        labels = [str((scope.get("topics", {}) or {}).get(topic, {}).get("label", topic)) for topic in topics]
        notices.append({
            "id": f"ordinance-coverage:{entry.get('slug', '')}:declared",
            "municipality": name,
            "citation": f"{name}, Ohio — municipal code not indexed",
            "title": "; ".join(labels) or "Local ordinances",
            "topic": topics[0] if topics else "",
            "topicLabel": "; ".join(labels),
            "reason": (
                "This municipality is listed as having local law in this area, but no "
                "chapter citation or permitted retrieval route has been established yet."
            ),
            "url": "",
            "notes": "",
            "summary": next(
                (summary for summary in (
                    _dataset_summary(str(entry.get("slug", "")), topic) for topic in topics
                ) if summary),
                None,
            ),
            "onTopic": _topic_matches(query, *topics, *labels),
        })

    # A notice that matches the topic asked about comes first; the rest still
    # rank ahead of another city's ordinance, which is the failure being fixed.
    notices.sort(key=lambda item: (not item["onTopic"], item["municipality"], item["citation"]))
    return notices[:MAX_NOTICES]


def _readable(value):
    if isinstance(value, (list, tuple)):
        return ", ".join(_readable(item) for item in value)
    return str(value).replace("_", " ")


def _dataset_summary(municipality_slug, topic):
    """A secondary-source summary of an ordinance whose text is not held.

    This is the only honest way to say something substantive about a chapter
    this corpus cannot retrieve: repeat what an attributable source says about
    it, name that source, and never let it pass as the ordinance.  Fields whose
    basis is ``unknown`` are omitted -- there is nothing to repeat -- and a
    municipality no source describes gets no summary rather than a written-up
    guess.
    """
    scope = _load_scope()
    dataset_name = str((scope.get("topics", {}) or {}).get(topic, {}).get("dataset", ""))
    if not dataset_name:
        return None
    payload = dataset(dataset_name)
    if not payload:
        return None
    record = next(
        (item for item in payload["records"] if item["municipality"] == municipality_slug), None,
    )
    if not record:
        return None

    stated, citations, bases = [], [], set()
    for field_name, field in record["fields"].items():
        if field["basis"] == "unknown" or field["value"] in (None, "", "unknown"):
            continue
        stated.append(f"{_readable(field_name)}: {_readable(field['value'])}")
        bases.add(field["basis"])
        citation = (field.get("source") or {}).get("citation", "")
        if citation and citation not in citations:
            citations.append(citation)
    if not stated:
        return None
    status = record.get("status", "in_force")
    return {
        "status": status,
        "repealDate": record.get("repealDate", ""),
        "text": "; ".join(stated),
        "bases": sorted(bases),
        "citations": citations,
        "caveat": " ".join(str(record.get("caveat", "")).split()),
        "shapeNote": record.get("shapeNote", ""),
    }


def not_in_force_snippet(notice):
    """The answer when the answer is "there is no such rule here".

    Worth stating as plainly as a rule, because it decides a case the same way:
    an advocate who reads "we do not hold this" keeps looking, and an advocate
    who reads "none is in force" can move on.
    """
    when = f" (repealed or expired {notice['repealDate']})" if notice.get("repealDate") else ""
    parts = [
        f"No {notice['topicLabel'] or notice['topic']} provision is in force in "
        f"{notice['municipality']}{when}.",
        notice.get("notInForceReason", ""),
        notice.get("notes", ""),
        "Confirm no successor has been adopted since this was recorded"
        + (f": {notice['url']}" if notice.get("url") else "."),
    ]
    return " ".join(part for part in parts if part)


def notice_snippet(notice):
    """What the reader is told, in place of text this corpus does not have.

    Order matters.  The gap is stated first, then the summary, then where to go
    read the real thing.  A summary that led would be mistaken for the
    ordinance, which is the one outcome this must not produce.
    """
    if not notice.get("inForce", True):
        return not_in_force_snippet(notice)
    summary = dict(notice.get("summary") or {})
    if notice.get("legalStatus") in {"repealed", "expired"}:
        summary["status"] = notice["legalStatus"]
        summary["repealDate"] = notice.get("overrideRepealDate", "") or summary.get("repealDate", "")
    described = ""
    if summary.get("text"):
        attribution = "; ".join(summary["citations"]) or "an indexed secondary source"
        # A repealed or expired chapter is described in the past tense, ahead of
        # its terms.  Its fields read exactly like a live ordinance's otherwise,
        # which is how a tenant gets advised to invoke a defense that no longer
        # exists.
        if summary.get("status") in {"repealed", "expired"}:
            when = f" on {summary['repealDate']}" if summary.get("repealDate") else ""
            described = (
                f"NOT CURRENT LAW: this provision was {summary['status']}{when}. "
                f"Its former terms, per {attribution}, were: {summary['text']}."
            )
        else:
            described = (
                f"Described by {attribution} (secondary source, not the ordinance text; "
                f"check the date): {summary['text']}."
            )
    parts = [
        f"{notice['municipality']} has local law on this point that this corpus does not hold.",
        f"Authority: {notice['citation']}." if notice["citation"] else "",
        notice["reason"],
        described,
        summary.get("shapeNote", ""),
        summary.get("caveat", ""),
        f"Read the current text at the publisher: {notice['url']}" if notice["url"]
        else "No publisher link has been established for this municipality yet.",
        notice["notes"],
    ]
    return " ".join(part for part in parts if part)


# ---------------------------------------------------------------------------
# Cross references
# ---------------------------------------------------------------------------

def _chunk_index():
    """chunk id -> a citation a reader can open, across every library document."""
    index = {}
    for _path, manifest in library_manifests():
        slug = manifest.get("document_slug", "")
        for item in manifest.get("chunks", []) or []:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            index[str(item["id"])] = {
                "documentSlug": slug,
                "documentTitle": str(manifest.get("document_title", "")),
                "contentKind": str(manifest.get("content_kind", "treatise")),
                "chunkId": str(item["id"]),
                "heading": str(item.get("heading", "")),
                "citation": str(item.get("citation", "")),
                "sourceId": f"content:{slug}:{item['id']}",
            }
    return index


def _statute_chunk(section_number):
    """The first chunk of one Revised Code section, by section number."""
    for _path, manifest in _manifests_of_kind("statute"):
        for item in manifest.get("chunks", []) or []:
            if not isinstance(item, dict) or str(item.get("section", "")) != str(section_number):
                continue
            slug = manifest.get("document_slug", "")
            return {
                "section": str(section_number),
                "documentSlug": slug,
                "chunkId": str(item.get("id", "")),
                "heading": str(item.get("heading", "")),
                "citation": str(item.get("citation", "")),
                "sourceId": f"content:{slug}:{item.get('id', '')}",
            }
    return None


def _ordinance_sections():
    """Every ingested ordinance section paired with the manifest it came from."""
    for _path, manifest in ordinance_manifests():
        for section in manifest.get("sections", []) or []:
            if section.get("status") == "ingested":
                yield manifest, section


def _ordinance_reference(manifest, section):
    chunks = section.get("chunks", []) or []
    slug = manifest.get("document_slug", "")
    chunk_id = str(chunks[0].get("id", "")) if chunks else ""
    return {
        "municipality": str(manifest.get("municipality", "")),
        "citation": str(section.get("citation", "")),
        "title": str(section.get("title", "")),
        "topic": str(section.get("topic", "")),
        "textBasis": str(section.get("text_basis", "")),
        "enactedDate": str(section.get("enacted_date", "")),
        "documentSlug": slug,
        "chunkId": chunk_id,
        "sourceId": f"content:{slug}:{chunk_id}" if chunk_id else "",
    }


def _matching_decisions(citations, limit=6):
    """Decisions this corpus holds for a citation an ordinance record names.

    Matching is by citation string and then by case name, because the corpus
    records both and a local ordinance is usually cited by name in practice.
    A miss is normal and is reported as an unresolved citation rather than
    dropped, so a reader knows the case exists and this corpus lacks it.
    """
    from apps.caselaw.models import CaseLawDecision

    resolved, unresolved = [], []
    for citation in citations:
        text = str(citation or "").strip()
        if not text:
            continue
        name = text.split(",")[0].strip()
        queryset = CaseLawDecision.objects.filter(approved_for_search=True)
        matches = list(queryset.filter(citation_string__icontains=text)[:limit])
        if not matches and name:
            matches = list(queryset.filter(title__icontains=name)[:limit])
        if not matches:
            unresolved.append(text)
            continue
        for decision in matches:
            resolved.append({
                "id": decision.id,
                "title": decision.title,
                "citation": decision.citation_string,
                "court": decision.court,
                "decisionDate": decision.decision_date.isoformat() if decision.decision_date else "",
                "citedAs": text,
            })
    return resolved, unresolved


def cross_references(document_slug, chunk_id):
    """What else in the corpus bears on this chunk, in both directions.

    Outward, from an ordinance: the statutes it operates against, the treatise
    section that discusses it, the cases named for it.  Inward, to a statute or
    treatise section: every ordinance that names it -- which is what makes
    R.C. 5321.19 open onto the local provisions it may preempt.
    """
    index = _chunk_index()
    chunk = index.get(str(chunk_id))
    outward = {"statutes": [], "treatise": [], "cases": [], "unresolvedCases": []}
    inbound = []

    section_record = None
    if chunk and chunk["documentSlug"] == document_slug and chunk["contentKind"] == "ordinance":
        for manifest, section in _ordinance_sections():
            if manifest.get("document_slug") != document_slug:
                continue
            if any(str(item.get("id")) == str(chunk_id) for item in section.get("chunks", []) or []):
                section_record = section
                break

    if section_record:
        for number in section_record.get("related_statutes", []) or []:
            resolved = _statute_chunk(number)
            outward["statutes"].append(resolved or {"section": str(number), "sourceId": ""})
        for treatise_chunk in section_record.get("treatise_chunks", []) or []:
            entry = index.get(str(treatise_chunk))
            if entry:
                outward["treatise"].append(entry)
        cases, unresolved = _matching_decisions(section_record.get("related_cases", []) or [])
        outward["cases"], outward["unresolvedCases"] = cases, unresolved

    # Inbound links do not require the chunk to be resolvable: a reader may
    # arrive at a statute section by number alone.
    statute_section = ""
    if chunk and chunk["contentKind"] == "statute":
        for _path, manifest in _manifests_of_kind("statute"):
            for item in manifest.get("chunks", []) or []:
                if str(item.get("id")) == str(chunk_id):
                    statute_section = str(item.get("section", ""))
                    break
    for manifest, section in _ordinance_sections():
        names_statute = statute_section and statute_section in [
            str(value) for value in section.get("related_statutes", []) or []
        ]
        names_treatise = str(chunk_id) in [
            str(value) for value in section.get("treatise_chunks", []) or []
        ]
        if names_statute or names_treatise:
            inbound.append(_ordinance_reference(manifest, section))

    return {
        "chunkId": str(chunk_id),
        "documentSlug": str(document_slug),
        "outward": outward,
        "ordinancesCiting": inbound,
    }
