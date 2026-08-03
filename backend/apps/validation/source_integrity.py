"""Source-integrity rules: is a component's support the right kind of source?

Rule code range E/W/I700-799.

The citation rules in `services.py` lint citation *strings*. These rules use the
source bindings recorded for each component version to check the source *type*
against what the text asserts: authority language needs a citable authority, and
example language from a prior filing may shape wording but never stands as
support. Locator and quotation verification belong here too, once bindings carry
verified locators.
"""

from apps.drafting.source_bindings import CITABLE_ROLES, STYLE_ONLY_ROLES, bindings_for_draft
from apps.validation.findings import warning_finding


LEGAL_ASSERTION_CUES = (
    "requires",
    "provides",
    "holds",
    "held",
    "must",
    "entitled",
    "prohibits",
    "under ohio",
    "under r.c.",
    "pursuant to",
)


def _section_asserts_law(section, citation_pattern):
    text = section.get("body") or ""
    if citation_pattern.search(text):
        return True
    lowered = text.casefold()
    return any(cue in lowered for cue in LEGAL_ASSERTION_CUES)


def validate_source_bindings(draft, snapshot, *, citation_pattern):
    findings = []
    bindings_by_key = bindings_for_draft(draft)
    if not bindings_by_key:
        return findings

    for section in draft.sections or []:
        key = section.get("key")
        bindings = bindings_by_key.get(key)
        if bindings is None:
            continue
        label = section.get("label") or key
        if section.get("blockType") in {"caption", "signature", "certificate"}:
            continue
        if not _section_asserts_law(section, citation_pattern):
            continue

        roles = {binding.role for binding in bindings}
        if roles & CITABLE_ROLES:
            continue

        if roles & STYLE_ONLY_ROLES:
            example = next(binding for binding in bindings if binding.role in STYLE_ONLY_ROLES)
            findings.append(
                warning_finding(
                    draft_id=draft.id,
                    rule_code="W700",
                    category="source_integrity",
                    target=f"section:{key}:example-as-authority",
                    message=(
                        f"'{label}' states a legal proposition, but its only drafting support is example "
                        f"language ('{example.label or example.source_key}'). Example filings guide wording; "
                        "they are not authority."
                    ),
                    location={"view": "json", "blockKey": key, "sectionLabel": label},
                    action={
                        "type": "review_source_support",
                        "label": "Add legal authority for this section, or soften the legal assertion.",
                        "payload": {"blockKey": key},
                    },
                )
            )
            continue

        findings.append(
            warning_finding(
                draft_id=draft.id,
                rule_code="W710",
                category="source_integrity",
                target=f"section:{key}:no-authority-bound",
                message=(
                    f"'{label}' states a legal proposition, but no legal authority or procedural rule is "
                    "bound to it."
                ),
                location={"view": "json", "blockKey": key, "sectionLabel": label},
                action={
                    "type": "review_source_support",
                    "label": "Select supporting authority for this section before filing.",
                    "payload": {"blockKey": key},
                },
            )
        )

    return findings
