"""Choosing, and lazily reading, the case materials a run tests the brief against.

Existing case files are referenced, never copied. A run resolves a matter
document through the same case-file path the rest of the app uses, so a document
the viewer may not see is a document the gym cannot read either. What the gym
stores about it is a pointer and, when the advocate excludes it, that decision.
"""

from apps.ai.case_chat import rank_document_groups_by_salience
from apps.argument_gym.models import GymDocument
from apps.matters.document_context import get_case_documents, get_document_text, summarize_text


MATTER_MATERIAL_PREFIX = "matter:"


def matter_material_id(document_id):
    return f"{MATTER_MATERIAL_PREFIX}{document_id}"


def _reference_for(matter, document):
    return {
        "system": matter.source_system,
        "matterExternalId": matter.external_id,
        "documentId": document["id"],
        "kind": document.get("kind", ""),
        "title": document.get("title", ""),
        "url": (document.get("raw") or {}).get("url", "") or document.get("url", ""),
    }


def excluded_reference_ids(workspace):
    """Case-file documents the advocate took out of scope for this workspace."""
    return {
        (document.external_reference or {}).get("documentId")
        for document in workspace.documents.filter(
            role=GymDocument.CASE_RECORD,
            source_type=GymDocument.MATTER_DOCUMENT,
            excluded=True,
        )
    }


def available_materials(workspace, *, client=None):
    """Every case-record source this workspace could read, excluded ones marked.

    Uploaded materials carry their own extracted text. Case-file documents carry
    only a reference; their text is fetched at read time.
    """
    materials = []
    for document in workspace.documents.filter(role=GymDocument.CASE_RECORD, source_type=GymDocument.UPLOAD):
        materials.append(
            {
                "id": f"upload:{document.id}",
                "documentId": document.id,
                "title": document.title,
                "origin": "upload",
                "kind": "uploaded_material",
                "snippet": summarize_text(document.extracted_text, max_sentences=1),
                "reference": {},
                "excluded": document.excluded,
            }
        )

    matter = workspace.matter
    if not matter:
        return materials

    excluded = excluded_reference_ids(workspace)
    for document in get_case_documents(matter, client=client):
        materials.append(
            {
                "id": matter_material_id(document["id"]),
                "documentId": None,
                "title": document.get("title", "Case document"),
                "origin": "matter_document",
                "kind": document.get("kind", ""),
                "date": document.get("date", ""),
                "snippet": document.get("snippet", ""),
                "reference": _reference_for(matter, document),
                "excluded": document["id"] in excluded,
                "_document": document,
            }
        )
    return materials


def included_materials(workspace, *, client=None):
    return [material for material in available_materials(workspace, client=client) if not material["excluded"]]


def rank_materials(materials, case_context, request_text, *, limit=6, llm_client=None):
    """Narrow the case file to the documents worth reading for this brief.

    Reuses the case-chat salience ranking rather than inventing a second one:
    the question -- which of these documents actually decide anything -- is the
    same question, and the ranking already falls back to a deterministic order
    when the model is unavailable.
    """
    if not materials:
        return [], {"method": "none", "selected": [], "trace": []}
    if len(materials) <= limit:
        return list(materials), {
            "method": "all",
            "selected": [{"id": material["id"], "title": material["title"], "reason": "Every available material was read."} for material in materials],
            "trace": [],
        }
    groups = [
        {
            "id": material["id"],
            "key": material["id"],
            "representative": {
                "title": material["title"],
                "date": material.get("date", ""),
                "type": material.get("kind", ""),
                "snippet": material.get("snippet", ""),
            },
            "copies": [{"title": material["title"]}],
        }
        for material in materials
    ]
    selected_groups, trace = rank_document_groups_by_salience(
        groups, case_context, request_text, llm_client=llm_client
    )
    by_id = {material["id"]: material for material in materials}
    selected = [by_id[group["id"]] for group in selected_groups if group["id"] in by_id]
    # A ranking that returns fewer than asked for is not a reason to read
    # nothing; top up in the order the case file already gave us.
    for material in materials:
        if len(selected) >= limit:
            break
        if material not in selected:
            selected.append(material)
    return selected[:limit], trace


def material_text(material, *, workspace=None, client=None, max_chars=6000):
    """Read a material's text at the moment it is needed, not before."""
    if material["origin"] == "upload":
        document = GymDocument.objects.filter(id=material["documentId"]).first()
        text = document.extracted_text if document else ""
    else:
        document = material.get("_document")
        if document is None and workspace and workspace.matter:
            document = next(
                (
                    candidate
                    for candidate in get_case_documents(workspace.matter, client=client)
                    if matter_material_id(candidate["id"]) == material["id"]
                ),
                None,
            )
        text = get_document_text(document, client=client) if document else ""
    return (text or "")[:max_chars]


def public_material(material):
    """The shape the UI reads: a reference and a reason, never the document body."""
    return {
        "id": material["id"],
        "title": material["title"],
        "origin": material["origin"],
        "kind": material.get("kind", ""),
        "date": material.get("date", ""),
        "snippet": material.get("snippet", ""),
        "excluded": material.get("excluded", False),
        "reference": material.get("reference", {}),
        "reason": material.get("reason", ""),
    }
