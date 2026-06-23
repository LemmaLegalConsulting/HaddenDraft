from apps.matters.models import Matter, MatterFact


SAMPLE_MATTERS = [
    {
        "external_id": "LS-24018",
        "client_name": "Elena M.",
        "matter_type": "Eviction defense",
        "jurisdiction": "Cleveland Municipal Court - Housing Division",
        "posture": "Answer due in 5 days",
        "risk": "High urgency",
        "summary": "Nonpayment eviction with disputed balance, repair issues, and pending rental assistance.",
    },
    {
        "external_id": "LS-24027",
        "client_name": "Marcus T.",
        "matter_type": "Conditions / rent deposit",
        "jurisdiction": "Cleveland Municipal Court - Housing Division",
        "posture": "Pre-filing review",
        "risk": "Medium urgency",
        "summary": "Unresolved leaks, mold concerns, and repeated written repair requests.",
    },
    {
        "external_id": "LS-24041",
        "client_name": "Nadia S.",
        "matter_type": "Subsidized housing termination",
        "jurisdiction": "Cuyahoga County Court of Common Pleas",
        "posture": "Hearing scheduled",
        "risk": "High urgency",
        "summary": "Termination notice tied to alleged lease violations; hearing packet needed.",
    },
]

SAMPLE_FACTS = [
    {
        "slug": "rent-dispute",
        "title": "Disputed rent balance",
        "text": "Client disputes the amount claimed and reports payments not credited by the landlord.",
        "source_label": "LegalServer intake notes",
        "confidence": "strong",
    },
    {
        "slug": "repair-issues",
        "title": "Unresolved repair issues",
        "text": "Client reports water intrusion, mold concerns, and repeated requests for repairs.",
        "source_label": "LegalServer notes + uploaded photos",
        "confidence": "strong",
    },
    {
        "slug": "rental-assistance",
        "title": "Rental assistance pending",
        "text": "Client applied for rental assistance before the hearing date and is waiting for processing.",
        "source_label": "Uploaded assistance confirmation",
        "confidence": "medium",
    },
    {
        "slug": "notice-question",
        "title": "Notice issue flagged",
        "text": "Possible defect in the notice timeline; staff review needed before inclusion.",
        "source_label": "AI issue spotting from complaint packet",
        "confidence": "needs_review",
        "ai_suggested": True,
        "selected_by_default": False,
    },
    {
        "slug": "habitability-defense",
        "title": "Potential habitability defense",
        "text": "Repair facts may support counterclaims or defenses related to habitability and rent abatement.",
        "source_label": "SharePoint housing practice guide",
        "confidence": "strong",
        "ai_suggested": True,
    },
]


def seed_matters():
    for item in SAMPLE_MATTERS:
        matter, _created = Matter.objects.get_or_create(external_id=item["external_id"], defaults=item)
        if matter.external_id == "LS-24018":
            for fact in SAMPLE_FACTS:
                MatterFact.objects.get_or_create(matter=matter, slug=fact["slug"], defaults=fact)
