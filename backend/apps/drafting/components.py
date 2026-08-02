"""Projection between a draft's section JSON and its durable components.

`DraftDocument.sections` remains the contract the editor, validation, and export
paths read. Every write of that JSON also lands here, which records each changed
section as a new `ComponentVersion` so a regeneration or reviewer edit adds to
the document's history instead of overwriting the only copy of the text.
"""

from django.utils import timezone

from apps.drafting.models import ComponentVersion, DocumentComponent


SECTION_IDENTITY_KEYS = ("key", "label", "body")
KNOWN_ORIGINS = {choice for choice, _label in ComponentVersion.ORIGIN_CHOICES}
DEFAULT_ORIGIN = "template"


def plain_text_from_sections(sections):
    return "\n\n".join(f"{section.get('label', '').upper()}\n{section.get('body', '')}" for section in sections)


def structured_content_from_section(section):
    return {key: value for key, value in section.items() if key not in SECTION_IDENTITY_KEYS}


def section_from_version(component, version):
    """Rebuild the legacy section shape from a stored component version."""
    return {
        "key": component.stable_key,
        "label": component.label,
        "body": version.body,
        **(version.structured_content or {}),
    }


def sections_from_components(draft):
    """Project the current component versions back into the section JSON shape."""
    components = (
        DocumentComponent.objects.filter(document=draft, removed_at__isnull=True)
        .prefetch_related("versions")
        .order_by("position", "id")
    )
    sections = []
    for component in components:
        version = component.current_version
        if version:
            sections.append(section_from_version(component, version))
    return sections


def _section_origin(section, fallback):
    if fallback:
        return fallback
    origin = str(section.get("origin") or "").strip()
    return origin if origin in KNOWN_ORIGINS else DEFAULT_ORIGIN


def _component_keys(sections):
    """Give every section a key that is unique within the document.

    Sections are addressed by key, and a document can carry a section the
    template did not name, so a collision would otherwise merge two sections
    into one component and lose one of them.
    """
    keys = []
    used = set()
    for position, section in enumerate(sections):
        key = str(section.get("key") or "").strip() or f"section-{position + 1}"
        candidate = key
        suffix = 2
        while candidate in used:
            candidate = f"{key}-{suffix}"[:160]
            suffix += 1
        used.add(candidate)
        keys.append(candidate)
    return keys


def sync_components(draft, *, origin=None, instruction=""):
    """Record the draft's current sections as component versions.

    Only sections whose body or structured content actually changed create a
    version, so repeated saves of an unedited draft do not inflate its history.
    `origin` overrides the per-section origin, which is how a reviewer edit of
    AI-generated text is recorded as a human version.
    """
    sections = list(draft.sections or [])
    keys = _component_keys(sections)
    live_ids = []
    for position, (section, key) in enumerate(zip(sections, keys)):
        component, _created = DocumentComponent.objects.update_or_create(
            document=draft,
            stable_key=key,
            defaults={
                "label": str(section.get("label") or ""),
                "component_type": str(section.get("blockType") or section.get("componentType") or ""),
                "position": position,
                "removed_at": None,
            },
        )
        live_ids.append(component.id)
        body = section.get("body") or ""
        structured = structured_content_from_section(section)
        latest = component.current_version
        if latest and latest.body == body and latest.structured_content == structured:
            continue
        ComponentVersion.objects.create(
            component=component,
            sequence=(latest.sequence + 1) if latest else 1,
            body=body,
            structured_content=structured,
            origin=_section_origin(section, origin),
            instruction=instruction,
        )

    DocumentComponent.objects.filter(document=draft, removed_at__isnull=True).exclude(id__in=live_ids).update(
        removed_at=timezone.now()
    )
    return draft


def record_sections(draft, sections, *, origin=None, instruction="", editor_state=None):
    """Write sections, plain text, and component history in one place."""
    draft.sections = list(sections or [])
    draft.plain_text = plain_text_from_sections(draft.sections)
    update_fields = ["sections", "plain_text", "updated_at"]
    if editor_state is not None:
        draft.editor_state = editor_state
        update_fields.append("editor_state")
    if draft.pk:
        draft.save(update_fields=update_fields)
    else:
        draft.save()
    return sync_components(draft, origin=origin, instruction=instruction)


def ensure_components(draft):
    """Backfill components for a document written before this layer existed."""
    if not DocumentComponent.objects.filter(document=draft).exists():
        sync_components(draft)
    return draft


def component_history(draft):
    """Serializable component history for review and rollback surfaces."""
    from apps.drafting.source_bindings import binding_to_dict

    ensure_components(draft)
    components = (
        DocumentComponent.objects.filter(document=draft)
        .prefetch_related("versions", "versions__source_bindings")
        .order_by("removed_at", "position", "id")
    )
    payload = []
    for component in components:
        versions = sorted(component.versions.all(), key=lambda version: version.sequence)
        current = versions[-1] if versions else None
        payload.append(
            {
                "id": component.id,
                "stableKey": component.stable_key,
                "componentType": component.component_type,
                "label": component.label,
                "position": component.position,
                "removed": bool(component.removed_at),
                "currentVersionSequence": current.sequence if current else None,
                "versions": [
                    {
                        "sequence": version.sequence,
                        "origin": version.origin,
                        "instruction": version.instruction,
                        "body": version.body,
                        "createdAt": version.created_at.isoformat(),
                        "sourceBindings": [
                            binding_to_dict(binding) for binding in version.source_bindings.all()
                        ],
                    }
                    for version in versions
                ],
            }
        )
    return payload
