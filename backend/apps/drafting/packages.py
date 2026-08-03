"""Treat the documents a plan produces as one filing package.

A motion, its memorandum, a supporting declaration, and a proposed order are
filed together and have to agree with each other. This module gives each
document a package role and records the relationships between them, which is
what makes cross-document validation possible.

Roles come from the template's own `metadata.packageRole` when it declares one,
so new document families arrive as content rather than as Python.
"""

from apps.drafting.models import PackageRelationship


PACKAGE_ROLES = [
    "motion",
    "memorandum",
    "declaration",
    "proposed_order",
    "answer",
    "hearing_statement",
    "exhibit",
    "other",
]

# Checked in order: the first phrase found in the title wins, so "memorandum in
# support of motion" is a memorandum rather than a motion.
TITLE_ROLE_HINTS = [
    ("proposed order", "proposed_order"),
    ("memorandum", "memorandum"),
    ("declaration", "declaration"),
    ("affidavit", "declaration"),
    ("exhibit", "exhibit"),
    ("hearing statement", "hearing_statement"),
    ("answer", "answer"),
    ("motion", "motion"),
]
KIND_ROLES = {
    "motion": "motion",
    "brief": "memorandum",
    "answer_counterclaims": "answer",
    "hearing_statement": "hearing_statement",
}

# source role -> (target role, relationship type)
DERIVED_RELATIONSHIPS = [
    ("proposed_order", "motion", "implements_relief"),
    ("memorandum", "motion", "incorporates"),
    ("declaration", "motion", "depends_on"),
    ("declaration", "memorandum", "depends_on"),
    ("exhibit", "declaration", "depends_on"),
]


def package_role(draft):
    """Name what this document is within its package."""
    template = draft.template
    declared = str(((template.metadata or {}) if template else {}).get("packageRole") or "").strip()
    if declared in PACKAGE_ROLES:
        return declared
    title = (draft.title or "").casefold()
    for hint, role in TITLE_ROLE_HINTS:
        if hint in title:
            return role
    if template and template.kind in KIND_ROLES:
        return KIND_ROLES[template.kind]
    return "other"


def package_documents(session):
    """Documents in this session's package, each with its role."""
    return [
        {"document": draft, "role": package_role(draft)}
        for draft in session.drafts.select_related("template").order_by("created_at", "id")
    ]


def derive_relationships(session):
    """Record the relationships implied by the package's roles.

    Deriving these deterministically keeps the package graph in step with what
    the plan actually generated. Relationships added by hand are left alone.
    """
    documents = package_documents(session)
    by_role = {}
    for item in documents:
        by_role.setdefault(item["role"], []).append(item["document"])

    created = []
    for source_role, target_role, relationship_type in DERIVED_RELATIONSHIPS:
        for source in by_role.get(source_role, []):
            for target in by_role.get(target_role, []):
                if source.id == target.id:
                    continue
                relationship, was_created = PackageRelationship.objects.get_or_create(
                    source_document=source,
                    target_document=target,
                    relationship_type=relationship_type,
                    defaults={"metadata": {"derived": True}},
                )
                if was_created:
                    created.append(relationship)
    return created


def package_payload(session):
    """Serializable package composition and relationship graph."""
    documents = package_documents(session)
    document_ids = [item["document"].id for item in documents]
    relationships = PackageRelationship.objects.filter(
        source_document_id__in=document_ids, target_document_id__in=document_ids
    )
    return {
        "documents": [
            {
                "id": item["document"].id,
                "title": item["document"].title,
                "role": item["role"],
                "templateId": item["document"].template_id,
            }
            for item in documents
        ],
        "relationships": [
            {
                "sourceDocumentId": relationship.source_document_id,
                "targetDocumentId": relationship.target_document_id,
                "relationshipType": relationship.relationship_type,
                "metadata": relationship.metadata,
            }
            for relationship in relationships
        ],
    }
