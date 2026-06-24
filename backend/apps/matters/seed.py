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
        "raw_payload": {
            "case_notes": [
                "Client reports that the landlord has not credited a $450 money order from March and a $300 payment made in April.",
                "Client says the bedroom ceiling has leaked during heavy rain since February. She notified the property manager by text on February 14, March 3, and April 9.",
            ],
            "documents": [
                {
                    "id": "demo-ledger",
                    "title": "Landlord ledger excerpt.txt",
                    "source": "Uploaded document",
                    "text": "Ledger shows rent charges for January through May. It lists no credit for the tenant's March money order and shows late fees added after the tenant reported repair issues.",
                },
                {
                    "id": "demo-repair-texts",
                    "title": "Repair text messages.txt",
                    "source": "Uploaded screenshots",
                    "text": "February 14: Tenant texted property manager that water was coming through the bedroom ceiling. March 3: Tenant sent another message with a photo of mold around the leak. April 9: Tenant asked for an update and said her child was coughing at night.",
                },
            ],
        },
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
        matter, created = Matter.objects.get_or_create(external_id=item["external_id"], defaults=item)
        if not created and item.get("raw_payload") and not matter.raw_payload:
            matter.raw_payload = item["raw_payload"]
            matter.save(update_fields=["raw_payload"])
        if matter.external_id == "LS-24018":
            for fact in SAMPLE_FACTS:
                MatterFact.objects.get_or_create(matter=matter, slug=fact["slug"], defaults=fact)
