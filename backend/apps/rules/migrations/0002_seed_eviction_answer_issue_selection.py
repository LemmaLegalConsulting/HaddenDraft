from django.db import migrations


TABLE_KEY = "eviction_answer_issue_selection"


NOTICE_OUTPUT = {
    "candidate_issue": "notice_defect",
    "title": "Possible notice defect",
    "issue_type": "defense",
    "review_required": True,
    "activate_blocks_after_approval": ["defense_notice_defect"],
    "missing_facts": [
        "Confirm the notice service date.",
        "Confirm the complaint filing date.",
        "Confirm whether the notice contains required statutory language.",
    ],
}

ASSISTANCE_OUTPUT = {
    "candidate_issue": "pending_rental_assistance",
    "title": "Pending rental assistance",
    "issue_type": "defense",
    "review_required": True,
    "activate_blocks_after_approval": ["defense_pending_rental_assistance"],
    "missing_facts": [
        "Was the application pending before the complaint was filed?",
        "Did the landlord know about the pending application?",
        "Was payment approved, denied, or still pending?",
    ],
}

GOOD_CAUSE_OUTPUT = {
    "candidate_issue": "subsidized_good_cause",
    "title": "Subsidized housing good-cause issue",
    "issue_type": "defense",
    "review_required": True,
    "activate_blocks_after_approval": ["defense_subsidized_good_cause"],
    "missing_facts": [
        "Confirm the housing subsidy program type.",
        "Identify the landlord's stated reason for termination.",
        "Determine whether the stated reason is supported by specific evidence.",
        "Identify contrary tenant evidence.",
    ],
}


def seed_rules(apps, schema_editor):
    DecisionTable = apps.get_model("rules", "DecisionTable")
    DecisionRuleRow = apps.get_model("rules", "DecisionRuleRow")
    DecisionTestCase = apps.get_model("rules", "DecisionTestCase")

    table, _ = DecisionTable.objects.update_or_create(
        key=TABLE_KEY,
        version=1,
        defaults={
            "title": "Eviction answer issue selection",
            "description": "DMN-lite issue selection rules for housing answer drafting.",
            "workflow_type": "eviction_answer",
            "jurisdiction": "",
            "status": "published",
            "hit_policy": "collect",
            "change_reason": "Initial deterministic issue-selection rules.",
            "engine_type": "dmn_lite",
        },
    )

    rows = [
        {
            "row_id": "notice_defect",
            "label": "Missing or premature notice",
            "priority": 10,
            "conditions": {
                "all": [
                    {"field": "eviction.ground", "op": "equals", "value": "nonpayment"},
                    {
                        "any": [
                            {"field": "notice.exists", "op": "equals", "value": False},
                            {"field": "notice.days_between_service_and_filing", "op": "less_than", "value": 3},
                        ]
                    },
                ]
            },
            "outputs": NOTICE_OUTPUT,
            "explanation_template": "The case appears to involve nonpayment and a potentially missing or premature notice.",
        },
        {
            "row_id": "pending_rental_assistance",
            "label": "Pending rental assistance",
            "priority": 20,
            "conditions": {
                "all": [
                    {"field": "eviction.ground", "op": "equals", "value": "nonpayment"},
                    {"field": "assistance.application_status", "op": "equals", "value": "pending"},
                ]
            },
            "outputs": ASSISTANCE_OUTPUT,
            "explanation_template": "The case appears to involve nonpayment with a pending rental assistance application.",
        },
        {
            "row_id": "subsidized_good_cause",
            "label": "Subsidized good-cause review",
            "priority": 30,
            "conditions": {
                "all": [
                    {
                        "field": "housing.program_type",
                        "op": "in",
                        "value": [
                            "public_housing",
                            "project_based_section_8",
                            "voucher",
                            "lihtc",
                            "rural_housing",
                        ],
                    },
                    {
                        "field": "good_cause.heuristic_result",
                        "op": "in",
                        "value": ["not_supported", "plausible_but_contested", "unknown"],
                    },
                ]
            },
            "outputs": GOOD_CAUSE_OUTPUT,
            "explanation_template": "The case appears to involve subsidized housing and a good-cause issue needing review.",
        },
    ]

    for row in rows:
        DecisionRuleRow.objects.update_or_create(
            table=table,
            row_id=row["row_id"],
            defaults={
                "label": row["label"],
                "priority": row["priority"],
                "conditions": row["conditions"],
                "outputs": row["outputs"],
                "explanation_template": row["explanation_template"],
                "enabled": True,
            },
        )

    tests = [
        {
            "name": "notice defect matches missing notice",
            "inputs": {
                "eviction": {"ground": "nonpayment"},
                "notice": {"exists": False},
            },
            "expected_outputs": [NOTICE_OUTPUT],
        },
        {
            "name": "pending assistance matches",
            "inputs": {
                "eviction": {"ground": "nonpayment"},
                "assistance": {"application_status": "pending"},
            },
            "expected_outputs": [ASSISTANCE_OUTPUT],
        },
        {
            "name": "subsidized good cause matches",
            "inputs": {
                "housing": {"program_type": "project_based_section_8"},
                "good_cause": {"heuristic_result": "plausible_but_contested"},
            },
            "expected_outputs": [GOOD_CAUSE_OUTPUT],
        },
    ]
    for test in tests:
        DecisionTestCase.objects.update_or_create(
            table=table,
            name=test["name"],
            defaults={
                "inputs": test["inputs"],
                "expected_outputs": test["expected_outputs"],
                "enabled": True,
            },
        )


def unseed_rules(apps, schema_editor):
    DecisionTable = apps.get_model("rules", "DecisionTable")
    DecisionTable.objects.filter(key=TABLE_KEY, version=1).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("rules", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_rules, unseed_rules),
    ]
