"""Build and apply an editable, block-scoped AI revision plan from validation findings.

This is the "future LLM agent" the warning-level findings are meant for: unlike
`apps.validation.repair`, which auto-repairs a narrow set of safe error-level
findings, this groups *all* actionable (error + warning) findings by the block
they target into a plan a reviewer can edit before anything is regenerated.
"""

REVISABLE_SEVERITIES = {"error", "warning"}


def _finding_block_key(finding):
    action_payload = (finding.get("action") or {}).get("payload") or {}
    return action_payload.get("blockKey") or (finding.get("location") or {}).get("blockKey")


def build_revision_plan(draft, findings):
    actionable = [finding for finding in findings if finding.get("severity") in REVISABLE_SEVERITIES]
    section_labels = {section.get("key"): section.get("label") for section in draft.sections or []}

    by_block = {}
    unscoped = []
    for finding in actionable:
        block_key = _finding_block_key(finding)
        if block_key and block_key in section_labels:
            by_block.setdefault(block_key, []).append(finding)
        else:
            unscoped.append(finding)

    plan = []
    for block_key, block_findings in by_block.items():
        messages = [finding["message"] for finding in block_findings]
        instruction = (
            "Revise this section to address the following validation findings:\n"
            + "\n".join(f"- {message}" for message in messages)
            + "\nDo not invent missing facts. Preserve accurate template data. Keep the section's original intent."
        )
        plan.append(
            {
                "blockKey": block_key,
                "sectionLabel": section_labels.get(block_key, block_key),
                "findingIds": [finding["findingId"] for finding in block_findings],
                "instruction": instruction,
                "include": True,
            }
        )

    return {
        "plan": plan,
        "unscoped": [
            {"findingId": finding["findingId"], "message": finding["message"], "severity": finding["severity"]}
            for finding in unscoped
        ],
    }


def apply_revision_plan(draft, plan_items):
    from apps.drafting.services import regenerate_draft_block

    for item in plan_items or []:
        if not item.get("include", True):
            continue
        block_key = item.get("blockKey")
        instruction = (item.get("instruction") or "").strip()
        if not block_key or not instruction:
            continue
        draft = regenerate_draft_block(draft, block_key, instruction)
    return draft
