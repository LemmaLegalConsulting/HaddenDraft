from django.db import migrations


SIGNATURE_BODY = (
    "{{ advocate_signoff }}\n\n"
    "{{ advocate_signature_image }}\n"
    "{{ advocate_name }}\n"
    "{{ advocate_organization }}\n"
    "{{ advocate_address }}\n"
    "{{ advocate_phone }}\n"
    "{{ advocate_email }}"
)


def upsert_block(TemplateBlock, template, key, **defaults):
    TemplateBlock.objects.update_or_create(template=template, key=key, defaults={"key": key, **defaults})


def update_author_blocks(apps, _schema_editor):
    DocumentTemplate = apps.get_model("templates_app", "DocumentTemplate")
    TemplateBlock = apps.get_model("templates_app", "TemplateBlock")

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
    upsert_block(
        TemplateBlock,
        answer,
        "signature",
        label="Signature block",
        block_type="signature",
        order=100,
        body=SIGNATURE_BODY,
        ai_fill_mode="deterministic",
    )

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
    upsert_block(
        TemplateBlock,
        motion,
        "motion-signature",
        label="Signature block",
        block_type="signature",
        order=90,
        body=SIGNATURE_BODY,
        ai_fill_mode="deterministic",
    )

    shell, _created = DocumentTemplate.objects.get_or_create(
        slug="novel-motion-shell",
        defaults={
            "title": "Novel Motion Shell",
            "kind": "shell",
            "description": "Court-specific pleading shell for drafting from scratch with section-level generation.",
            "metadata": {"fit": "Draft from scratch"},
        },
    )
    upsert_block(
        TemplateBlock,
        shell,
        "caption",
        label="Caption",
        block_type="caption",
        order=10,
        body="{{ court }}\n{{ plaintiff }} v. {{ defendant }}\nCase No. {{ case_number }}",
        ai_fill_mode="deterministic",
    )
    upsert_block(
        TemplateBlock,
        shell,
        "signature",
        label="Signature",
        block_type="signature",
        order=50,
        body=SIGNATURE_BODY,
        ai_fill_mode="deterministic",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("templates_app", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(update_author_blocks, migrations.RunPython.noop),
    ]
