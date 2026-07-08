import re

from jinja2 import TemplateSyntaxError

from apps.templates_app.template_variables import (
    LEGACY_LITERAL_FIELDS,
    extract_template_variables_from_text,
    template_field_label,
)


CITATION_RE = re.compile(r"\b\d+\s+[A-Z][A-Za-z.]+\s+\d+\b")


def validate_document(draft):
    text = draft.plain_text
    flags = []
    session = getattr(draft, "session", None)
    template = getattr(session, "template", None) if session else None
    template_data = getattr(session, "template_data", {}) or {}
    declared_fields = list((getattr(template, "metadata", {}) or {}).get("fields", [])) if template else []
    if template:
        for block in template.blocks.all():
            try:
                paths = extract_template_variables_from_text(block.body or "")
            except TemplateSyntaxError:
                paths = []
            for path in paths:
                if str(path).startswith(("fields.", 'fields["')) and path not in declared_fields:
                    declared_fields.append(path)
    missing_template_fields = []
    for path in declared_fields:
        value = str(path)
        bracketed = re.fullmatch(r'fields\["([^"]+)"\]', value)
        key = bracketed.group(1) if bracketed else value.removeprefix("fields.")
        if key not in LEGACY_LITERAL_FIELDS and not str(template_data.get(key, "")).strip():
            missing_template_fields.append(template_field_label(key))
    if missing_template_fields:
        preview = ", ".join(missing_template_fields[:5])
        remainder = len(missing_template_fields) - 5
        flags.append(
            {
                "severity": "warning",
                "code": "missing_template_data",
                "message": f"Complete template details before filing: {preview}{f' (+{remainder} more)' if remainder else ''}.",
                "location": "Template details",
            }
        )
    applicability = (getattr(template, "metadata", {}) or {}).get("applicability", {}) if template else {}
    required_template_data = applicability.get("requiredTemplateData", {})
    unmet_applicability = [
        key
        for key, expected in required_template_data.items()
        if template_data.get(key) != expected
    ]
    if unmet_applicability:
        flags.append(
            {
                "severity": "warning",
                "code": "template_applicability",
                "message": "Confirm this template's threshold applicability requirements before drafting or filing.",
                "location": "Template selection",
            }
        )
    if "{{" in text or "{%" in text:
        flags.append(
            {
                "severity": "warning",
                "code": "unrendered_template_syntax",
                "message": "The draft contains unresolved template syntax.",
                "location": "Template details",
            }
        )
    attorney_review_markers = re.findall(r"\[Attorney review required:[^\]]+\]", text, flags=re.IGNORECASE)
    if attorney_review_markers:
        flags.append(
            {
                "severity": "warning",
                "code": "attorney_review_required",
                "message": f"Resolve {len(attorney_review_markers)} attorney-review marker(s) before filing.",
                "location": "Draft",
            }
        )
    unresolved_labels = re.findall(
        r"\[(?:Filing|Hearing|Service|Premises|Plaintiff|Defendant|Attorney|Case|Copy|Describe|Insert|Number|Time)[^\]\n]{0,70}\]",
        text,
        flags=re.IGNORECASE,
    )
    if unresolved_labels:
        flags.append(
            {
                "severity": "warning",
                "code": "unresolved_template_values",
                "message": f"Complete {len(unresolved_labels)} visible template value(s) before filing.",
                "location": "Template details",
            }
        )
    if session and not session.matter.jurisdiction and not getattr(template, "jurisdiction", ""):
        flags.append(
            {
                "severity": "warning",
                "code": "missing_jurisdiction",
                "message": "Confirm the court and jurisdiction before filing.",
                "location": "Caption",
            }
        )
    elif session and template:
        effective_jurisdiction = session.matter.jurisdiction or template.jurisdiction
        has_caption_marker = template.blocks.filter(label__istartswith="Case caption").exists()
        if has_caption_marker and "court" not in effective_jurisdiction.casefold():
            flags.append(
                {
                    "severity": "warning",
                    "code": "missing_court",
                    "message": "Select the specific court before filing this captioned document.",
                    "location": "Caption",
                }
            )
    if "No facts selected" in text:
        flags.append(
            {
                "severity": "warning",
                "code": "missing_facts",
                "message": "The draft contains a facts section without selected facts.",
                "location": "Facts",
            }
        )
    if "may support" in text.lower():
        flags.append(
            {
                "severity": "info",
                "code": "needs_attorney_review",
                "message": "Tentative legal language should be reviewed before filing.",
                "location": "Argument",
            }
        )
    for citation in CITATION_RE.findall(text):
        flags.append(
            {
                "severity": "needs_check",
                "code": "citation_validation",
                "message": f"Validate citation and treatment: {citation}",
                "location": "Citations",
            }
        )
    if len(text.split()) > 3000:
        flags.append(
            {
                "severity": "warning",
                "code": "length",
                "message": "Draft may exceed a short motion page budget.",
                "location": "Document",
            }
        )
    return flags
