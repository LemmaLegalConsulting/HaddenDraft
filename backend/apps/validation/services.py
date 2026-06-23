import re


CITATION_RE = re.compile(r"\b\d+\s+[A-Z][A-Za-z.]+\s+\d+\b")


def validate_document(draft):
    text = draft.plain_text
    flags = []
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
