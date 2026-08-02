"""Typed, reviewable operations on a draft document.

A change to a filing is described before it happens: which component moves,
what replaces it, and why. Deterministic code validates the description and
applies it, which keeps "regenerate this section" a patch against a known
component rather than a wholesale replacement of the editor's contents.

Proposing and applying are separate steps so a proposal can be reviewed,
rejected, or produced by something that is not allowed to write documents
directly.
"""

from django.db import transaction
from django.utils import timezone

from apps.drafting.components import ensure_components, record_sections
from apps.drafting.models import DocumentComponent, DraftOperation


class OperationError(ValueError):
    """A proposed operation does not describe a change this document can make."""


TARGETED_OPERATIONS = {"replace_component", "delete_component", "move_component", "revert_component"}
OPERATION_TYPES = {choice for choice, _label in DraftOperation.OPERATION_TYPES}


def _sections(draft):
    return [dict(section) for section in (draft.sections or [])]


def _index_of(sections, stable_key):
    for index, section in enumerate(sections):
        if section.get("key") == stable_key:
            return index
    return None


def _required_text(payload, key, *, allow_blank=False):
    value = payload.get(key)
    if not isinstance(value, str) or (not allow_blank and not value.strip()):
        raise OperationError(f"'{key}' is required for this operation.")
    return value


def _resolve_component(draft, target_component, payload):
    if target_component is not None:
        if target_component.document_id != draft.id:
            raise OperationError("The target component belongs to another document.")
        return target_component
    stable_key = str(payload.get("stableKey") or payload.get("key") or "").strip()
    if not stable_key:
        raise OperationError("This operation needs a target component.")
    component = DocumentComponent.objects.filter(
        document=draft, stable_key=stable_key, removed_at__isnull=True
    ).first()
    if not component:
        raise OperationError(f"No live component '{stable_key}' in this document.")
    return component


def propose(draft, operation_type, *, payload=None, target_component=None, rationale="", origin="human", requested_by=None):
    """Validate a described change and record it as a proposal."""
    if operation_type not in OPERATION_TYPES:
        raise OperationError(f"Unsupported operation type '{operation_type}'.")
    ensure_components(draft)
    payload = dict(payload or {})
    component = None
    if operation_type in TARGETED_OPERATIONS:
        component = _resolve_component(draft, target_component, payload)

    if operation_type == "replace_component":
        # An empty body is a legitimate result: a deterministic block can render
        # to nothing, and validation is what reports that, not this layer.
        _required_text(payload, "body", allow_blank=True)
    elif operation_type == "insert_component":
        _required_text(payload, "key")
        _required_text(payload, "body", allow_blank=True)
        if _index_of(_sections(draft), payload["key"]) is not None:
            raise OperationError(f"Component '{payload['key']}' is already in this document.")
    elif operation_type == "move_component":
        if not isinstance(payload.get("position"), int):
            raise OperationError("'position' must be an integer for a move.")
    elif operation_type == "revert_component":
        sequence = payload.get("sequence")
        if not isinstance(sequence, int):
            raise OperationError("'sequence' must be an integer for a revert.")
        if not component.versions.filter(sequence=sequence).exists():
            raise OperationError(f"Version {sequence} does not exist for this component.")

    return DraftOperation.objects.create(
        document=draft,
        operation_type=operation_type,
        target_component=component,
        payload=payload,
        rationale=rationale,
        origin=origin,
        requested_by=requested_by,
    )


def _apply_replace(draft, sections, operation):
    index = _index_of(sections, operation.target_component.stable_key)
    if index is None:
        raise OperationError("The component this operation targets is no longer in the document.")
    payload = operation.payload or {}
    structured = {
        key: value
        for key, value in (payload.get("structuredContent") or {}).items()
        if key not in {"key", "label", "body"}
    }
    sections[index] = {**sections[index], **structured, "body": payload["body"]}
    if payload.get("label"):
        sections[index]["label"] = payload["label"]
    return sections


def _apply_insert(draft, sections, operation):
    payload = operation.payload or {}
    section = {
        "key": payload["key"],
        "label": payload.get("label") or payload["key"],
        "body": payload["body"],
        **{
            key: value
            for key, value in (payload.get("structuredContent") or {}).items()
            if key not in {"key", "label", "body"}
        },
    }
    if payload.get("componentType"):
        section["blockType"] = payload["componentType"]
    position = payload.get("position")
    if isinstance(position, int):
        sections.insert(max(0, min(position, len(sections))), section)
    else:
        sections.append(section)
    return sections


def _apply_delete(draft, sections, operation):
    stable_key = operation.target_component.stable_key
    remaining = [section for section in sections if section.get("key") != stable_key]
    if len(remaining) == len(sections):
        raise OperationError("The component this operation targets is no longer in the document.")
    return remaining


def _apply_move(draft, sections, operation):
    index = _index_of(sections, operation.target_component.stable_key)
    if index is None:
        raise OperationError("The component this operation targets is no longer in the document.")
    section = sections.pop(index)
    position = max(0, min(operation.payload["position"], len(sections)))
    sections.insert(position, section)
    return sections


def _apply_revert(draft, sections, operation):
    index = _index_of(sections, operation.target_component.stable_key)
    if index is None:
        raise OperationError("The component this operation targets is no longer in the document.")
    version = operation.target_component.versions.filter(sequence=operation.payload["sequence"]).first()
    if not version:
        raise OperationError("The version this operation targets no longer exists.")
    sections[index] = {
        "key": operation.target_component.stable_key,
        "label": operation.target_component.label,
        "body": version.body,
        **(version.structured_content or {}),
    }
    return sections


APPLIERS = {
    "replace_component": _apply_replace,
    "insert_component": _apply_insert,
    "delete_component": _apply_delete,
    "move_component": _apply_move,
    "revert_component": _apply_revert,
}


def apply(operation):
    """Apply a proposed operation and record the resulting component versions."""
    if operation.status != "proposed":
        raise OperationError(f"This operation was already {operation.status}.")
    draft = operation.document
    with transaction.atomic():
        sections = APPLIERS[operation.operation_type](draft, _sections(draft), operation)
        origin = "rollback" if operation.operation_type == "revert_component" else operation.origin
        record_sections(draft, sections, origin=origin, instruction=operation.rationale)
        component = operation.target_component
        if component is not None:
            component.refresh_from_db()
        current = component.current_version if component else None
        operation.status = "applied"
        operation.resolved_at = timezone.now()
        operation.result = {"componentVersionSequence": current.sequence if current else None}
        operation.save(update_fields=["status", "resolved_at", "result"])
    return draft


def reject(operation, note=""):
    if operation.status != "proposed":
        raise OperationError(f"This operation was already {operation.status}.")
    operation.status = "rejected"
    operation.decision_note = note
    operation.resolved_at = timezone.now()
    operation.save(update_fields=["status", "decision_note", "resolved_at"])
    return operation


def propose_and_apply(draft, operation_type, **kwargs):
    """Record and immediately apply a change made by an already-approved action."""
    operation = propose(draft, operation_type, **kwargs)
    apply(operation)
    return operation


def operation_to_dict(operation):
    return {
        "id": operation.id,
        "documentId": operation.document_id,
        "operationType": operation.operation_type,
        "targetComponentKey": operation.target_component.stable_key if operation.target_component else None,
        "payload": operation.payload,
        "rationale": operation.rationale,
        "status": operation.status,
        "origin": operation.origin,
        "decisionNote": operation.decision_note,
        "result": operation.result,
        "requestedBy": operation.requested_by.get_username() if operation.requested_by else None,
        "createdAt": operation.created_at.isoformat(),
        "resolvedAt": operation.resolved_at.isoformat() if operation.resolved_at else None,
    }
