from apps.templates_app.models import DocumentTemplate, TemplateBlock


def seed_templates():
    answer, _created = DocumentTemplate.objects.get_or_create(
        slug="answer-counterclaims-cleveland",
        defaults={
            "title": "Answer and Counterclaims",
            "kind": "answer_counterclaims",
            "description": "Respond to eviction complaint and preserve defenses or counterclaims.",
            "jurisdiction": "Cleveland Municipal Court - Housing Division",
            "metadata": {"fit": "Best match", "page_limit": None},
        },
    )
    blocks = [
        {
            "key": "caption",
            "label": "Court caption",
            "block_type": "caption",
            "order": 10,
            "body": "{{ court }}\n{{ plaintiff }} v. {{ defendant }}\nCase No. {{ case_number }}",
            "ai_fill_mode": "deterministic",
        },
        {
            "key": "facts",
            "label": "Facts",
            "block_type": "facts",
            "order": 20,
            "body": "Defendant states the following facts based on the selected record.",
            "ai_fill_mode": "constrained_generation",
        },
        {
            "key": "disputed-rent-ledger",
            "label": "Disputed rent ledger",
            "block_type": "optional_clause",
            "order": 30,
            "body": "Defendant disputes the amount claimed and preserves all defenses related to payments, credits, and ledger accuracy.",
            "required": False,
            "selection_rule": {"fact_slugs": ["rent-dispute"]},
            "supporting_sources": ["LegalServer intake notes"],
        },
        {
            "key": "habitability",
            "label": "Habitability and repairs",
            "block_type": "optional_clause",
            "order": 40,
            "body": "Defendant states that serious repair issues existed before filing, including water intrusion, mold concerns, and repeated repair requests.",
            "required": False,
            "selection_rule": {"fact_slugs": ["repair-issues", "habitability-defense"]},
            "supporting_sources": ["LegalServer notes", "Housing Litigation Guide"],
        },
        {
            "key": "rental-assistance",
            "label": "Pending rental assistance",
            "block_type": "optional_clause",
            "order": 50,
            "body": "Defendant asks that any pending rental assistance be considered before any displacement order is entered.",
            "required": False,
            "selection_rule": {"fact_slugs": ["rental-assistance"]},
            "supporting_sources": ["Uploaded assistance confirmation"],
        },
        {
            "key": "relief",
            "label": "Prayer for relief",
            "block_type": "relief",
            "order": 90,
            "body": "Defendant requests dismissal, reduction or offset of any claimed balance as appropriate, time for rental assistance, and any further relief that is just and proper.",
        },
        {
            "key": "signature",
            "label": "Signature block",
            "block_type": "signature",
            "order": 100,
            "body": "Respectfully submitted,\n\n{{ advocate_name }}",
            "ai_fill_mode": "deterministic",
        },
    ]
    for block in blocks:
        TemplateBlock.objects.get_or_create(template=answer, key=block["key"], defaults=block)

    motion, _created = DocumentTemplate.objects.get_or_create(
        slug="motion-continuance-cleveland",
        defaults={
            "title": "Motion for Continuance",
            "kind": "motion",
            "description": "Request more time for rental assistance, evidence gathering, or counsel review.",
            "jurisdiction": "Cleveland Municipal Court - Housing Division",
            "metadata": {"fit": "Recommended"},
        },
    )
    TemplateBlock.objects.get_or_create(
        template=motion,
        key="motion-body",
        defaults={
            "label": "Motion body",
            "block_type": "argument",
            "order": 10,
            "body": "Defendant respectfully requests a continuance because additional time is needed to review documents, resolve disputed rent issues, and permit rental assistance processing.",
            "ai_fill_mode": "constrained_generation",
        },
    )

    shell, _created = DocumentTemplate.objects.get_or_create(
        slug="novel-motion-shell",
        defaults={
            "title": "Novel Motion Shell",
            "kind": "shell",
            "description": "Court-specific pleading shell for drafting from scratch with section-level generation.",
            "jurisdiction": "",
            "metadata": {"fit": "Draft from scratch"},
        },
    )
    for index, block in enumerate(["Caption", "Facts", "Argument", "Prayer for Relief", "Signature"], start=1):
        block_type = "relief" if block == "Prayer for Relief" else "argument" if block == "Argument" else block.lower().split()[0]
        TemplateBlock.objects.get_or_create(
            template=shell,
            key=block.lower().replace(" ", "-"),
            defaults={
                "label": block,
                "block_type": block_type,
                "order": index * 10,
                "body": f"{block} section to be completed.",
                "ai_fill_mode": "constrained_generation" if block in {"Facts", "Argument", "Prayer for Relief"} else "deterministic",
            },
        )
