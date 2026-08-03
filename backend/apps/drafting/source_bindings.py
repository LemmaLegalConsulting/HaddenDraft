"""Bind the sources a component version relied on, typed by what they can support.

The session holds one undifferentiated list of selected sources. A filing needs
a sharper distinction: a prior brief may guide style but must not be cited as
authority, a case document may establish a fact but not a legal rule, and a
court rule governs procedure but does not prove the record. Bindings record
which component used which source, in which role, so validation can check the
source type against the assertion instead of trusting a citation string.
"""

from apps.drafting.models import SourceBinding


# Support purposes come off the session's selected sources; roles are the
# stronger typing the drafting layer needs.
PURPOSE_ROLES = {
    "legal_authority": "legal_authority",
    "example_language": "example_language",
    "background_reference": "background_reference",
}
ROLE_SUPPORT_TYPES = {
    "record_evidence": "direct",
    "legal_authority": "direct",
    "procedural_rule": "direct",
    "example_language": "style_only",
    "background_reference": "background",
}
# Roles a draft may cite as authority for a legal proposition.
CITABLE_ROLES = {"legal_authority", "procedural_rule"}
# Roles that may shape wording but must never be offered as support.
STYLE_ONLY_ROLES = {"example_language"}

PROCEDURAL_SOURCE_KINDS = {"rules", "court_rules"}


def classify_source_result(source):
    """Give a selected source result a role and the support it can carry."""
    purpose = str(source.get("purpose") or "").strip()
    role = PURPOSE_ROLES.get(purpose)
    if role is None:
        source_kind = str(source.get("sourceKind") or source.get("source_kind") or "").strip()
        if source_kind in PROCEDURAL_SOURCE_KINDS:
            role = "procedural_rule"
        elif source.get("citation"):
            role = "legal_authority"
        else:
            role = "background_reference"
    return role, ROLE_SUPPORT_TYPES[role]


def _source_result_binding(version, source):
    role, support_type = classify_source_result(source)
    return SourceBinding(
        component_version=version,
        source_key=str(source.get("id") or source.get("citation") or source.get("title") or "")[:255],
        source_kind=str(source.get("sourceKind") or source.get("source_kind") or "")[:80],
        role=role,
        support_type=support_type,
        label=str(source.get("title") or source.get("sourceLabel") or "")[:500],
        citation=str(source.get("citation") or "")[:500],
        locator={
            "url": source.get("url") or "",
            "sourceId": source.get("id") or "",
            "contentPath": (source.get("metadata") or {}).get("contentPath", ""),
            "sourceChecksum": (source.get("metadata") or {}).get("sourceChecksum", ""),
        },
        excerpt=str(source.get("snippet") or ""),
    )


def _fact_binding(version, fact):
    return SourceBinding(
        component_version=version,
        source_key=f"fact:{fact.id}",
        source_kind="matter_fact",
        role="record_evidence",
        support_type="direct",
        label=fact.title[:500],
        locator={"factId": fact.id, "factSlug": fact.slug, "sourceLabel": fact.source_label},
        excerpt=fact.text,
    )


def _template_source_binding(version, label):
    return SourceBinding(
        component_version=version,
        source_key=str(label)[:255],
        source_kind="template",
        role="background_reference",
        support_type="background",
        label=str(label)[:500],
    )


def bindings_for_section(version, section, *, facts, source_results):
    """Derive the bindings implied by how a section was composed."""
    bindings = []
    if section.get("blockType") == "facts":
        bindings.extend(_fact_binding(version, fact) for fact in facts)
    if section.get("aiFillMode") == "constrained_generation":
        bindings.extend(_source_result_binding(version, source) for source in source_results)

    # Advice-letter sections start from maintained wording but can be
    # redrafted through the same AI operation as filing blocks. An AI version
    # needs the case facts and selected support recorded even though the
    # maintained version itself is sourced from the advice-letter catalog.
    if version.origin == "ai" and section.get("adviceSectionSlug"):
        bindings.extend(_fact_binding(version, fact) for fact in facts)
        bindings.extend(_source_result_binding(version, source) for source in source_results)

    # Whatever is left in the section's own source list is template-declared
    # support: strings the block carried, minus the fact labels already bound.
    fact_labels = {fact.source_label for fact in facts}
    for entry in section.get("sources") or []:
        if isinstance(entry, dict):
            if section.get("aiFillMode") != "constrained_generation":
                bindings.append(_source_result_binding(version, entry))
        elif entry and entry not in fact_labels:
            bindings.append(_template_source_binding(version, entry))

    seen = set()
    unique = []
    for binding in bindings:
        identity = (binding.source_key, binding.role)
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(binding)
    return unique


def bind_current_versions(draft, *, facts=None, source_results=None):
    """Record bindings for any current component version that has none yet.

    Versions are immutable, so a version that already has bindings is left
    alone; a regenerated component gets bindings for its new version.
    """
    from apps.matters.models import MatterFact

    session = draft.session
    if facts is None:
        facts = list(MatterFact.objects.filter(id__in=session.selected_fact_ids or []).order_by("id"))
    if source_results is None:
        source_results = [source for source in (session.selected_source_results or []) if isinstance(source, dict)]

    sections_by_key = {section.get("key"): section for section in draft.sections or []}
    created = []
    for component in draft.components.filter(removed_at__isnull=True).prefetch_related("versions"):
        version = component.current_version
        if not version or version.source_bindings.exists():
            continue
        section = sections_by_key.get(component.stable_key)
        if section is None:
            continue
        created.extend(bindings_for_section(version, section, facts=facts, source_results=source_results))
    SourceBinding.objects.bulk_create(created)
    return created


def bindings_for_draft(draft):
    """Current bindings by component key, for validation and review surfaces."""
    by_component = {}
    for component in draft.components.filter(removed_at__isnull=True).prefetch_related("versions"):
        version = component.current_version
        if not version:
            continue
        by_component[component.stable_key] = list(version.source_bindings.all())
    return by_component


def binding_to_dict(binding):
    return {
        "sourceKey": binding.source_key,
        "sourceKind": binding.source_kind,
        "role": binding.role,
        "supportType": binding.support_type,
        "label": binding.label,
        "citation": binding.citation,
        "locator": binding.locator,
        "excerpt": binding.excerpt,
        "verified": binding.verified,
    }
