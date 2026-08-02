"""Package-consistency rules: does this document agree with the ones filed with it?

Rule code range E/W/I800-899.

Every other rule looks at one document in isolation. These compare a draft with
its siblings in the same drafting session, which is where a filing package
breaks in practice: a caption that disagrees with the motion it accompanies, an
exhibit nothing authenticates, or a companion document the text promises and the
package does not contain.
"""

import re

from apps.drafting.packages import package_documents
from apps.validation.findings import warning_finding


CASE_NUMBER_RE = re.compile(
    r"\bcase\s*(?:no\.?|number)\s*[:#]?\s*([A-Z0-9][A-Z0-9\-/. ]{2,24}?)(?=\s*(?:$|\n|[,;)]))",
    re.IGNORECASE,
)
EXHIBIT_RE = re.compile(r"\bexhibit\s+([A-Z0-9]{1,3})\b", re.IGNORECASE)
COMPANION_RE = re.compile(
    r"\b(?:accompanying|attached|supporting|enclosed|proposed)\s+"
    r"(memorandum|declaration|affidavit|order|exhibit)\b",
    re.IGNORECASE,
)
COMPANION_ROLES = {
    "memorandum": "memorandum",
    "declaration": "declaration",
    "affidavit": "declaration",
    "order": "proposed_order",
    "exhibit": "exhibit",
}
AUTHENTICATING_ROLES = {"declaration", "exhibit"}
PLACEHOLDER_CASE_NUMBERS = {"", "number", "no", "tbd", "pending"}


def _case_numbers(text):
    numbers = set()
    for match in CASE_NUMBER_RE.finditer(text or ""):
        value = re.sub(r"\s+", " ", match.group(1)).strip(" .,-").casefold()
        if value.strip("[]") in PLACEHOLDER_CASE_NUMBERS or value.startswith("["):
            continue
        numbers.add(value)
    return numbers


def _exhibits(text):
    return {match.group(1).upper() for match in EXHIBIT_RE.finditer(text or "")}


def validate_package_consistency(draft, snapshot):
    session = getattr(draft, "session", None)
    if session is None:
        return []
    documents = package_documents(session)
    if len(documents) < 2:
        return []

    findings = []
    text = snapshot["plainText"]
    roles = {item["role"] for item in documents}
    siblings = [item for item in documents if item["document"].id != draft.id]

    own_numbers = _case_numbers(text)
    sibling_numbers = set()
    for item in siblings:
        sibling_numbers |= _case_numbers(item["document"].plain_text)
    if own_numbers and sibling_numbers and not (own_numbers & sibling_numbers):
        findings.append(
            warning_finding(
                draft_id=draft.id,
                rule_code="W800",
                category="package_consistency",
                target="package:case-number",
                message=(
                    f"This document's case number ({', '.join(sorted(own_numbers))}) does not match the "
                    f"other documents in this package ({', '.join(sorted(sibling_numbers))})."
                ),
                location={"view": "json"},
                action={
                    "type": "review_package",
                    "label": "Make the caption case number the same across every document in the filing.",
                    "payload": {"caseNumbers": sorted(own_numbers | sibling_numbers)},
                },
            )
        )

    authenticated = set()
    for item in documents:
        if item["role"] in AUTHENTICATING_ROLES:
            authenticated |= _exhibits(item["document"].plain_text)
    for exhibit in sorted(_exhibits(text) - authenticated):
        findings.append(
            warning_finding(
                draft_id=draft.id,
                rule_code="W810",
                category="package_consistency",
                target=f"package:exhibit:{exhibit}",
                message=(
                    f"This document refers to Exhibit {exhibit}, but no declaration or exhibit in this "
                    "package identifies it."
                ),
                location={"view": "json"},
                action={
                    "type": "review_package",
                    "label": "Add a declaration that authenticates this exhibit, or remove the reference.",
                    "payload": {"exhibit": exhibit},
                },
            )
        )

    for match in COMPANION_RE.finditer(text or ""):
        needed = COMPANION_ROLES[match.group(1).casefold()]
        if needed in roles:
            continue
        findings.append(
            warning_finding(
                draft_id=draft.id,
                rule_code="W820",
                category="package_consistency",
                target=f"package:missing:{needed}",
                message=(
                    f"This document refers to a{'n' if needed[0] in 'aeiou' else ''} "
                    f"{needed.replace('_', ' ')}, but the package does not contain one."
                ),
                location={"view": "json", "excerpt": match.group(0)},
                action={
                    "type": "review_package",
                    "label": "Generate the missing document, or remove the reference to it.",
                    "payload": {"packageRole": needed},
                },
            )
        )

    return findings
