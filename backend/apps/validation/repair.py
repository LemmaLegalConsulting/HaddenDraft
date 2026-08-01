"""Bounded automatic repair for error-level, safely-regenerable validation findings."""

from apps.validation.services import validate_document

REPAIRABLE_ACTION_TYPES = {"regenerate_block", "regenerate_document", "refresh_plain_text"}


def is_repairable(finding):
    action = finding.get("action") or {}
    return finding.get("severity") == "error" and action.get("type") in REPAIRABLE_ACTION_TYPES


def _regenerate_document(draft):
    from apps.drafting.services import create_draft

    session = draft.session
    # Regenerate from this draft's own template and sections. A session can hold
    # several documents, and session.template only names the first one.
    template = draft.template or session.template
    if not template:
        return draft
    block_keys = [section.get("key") for section in draft.sections or [] if section.get("key")]
    replacement = create_draft(session, template=template, block_keys=block_keys or None, title=draft.title)
    draft.sections = replacement.sections
    draft.plain_text = replacement.plain_text
    draft.editor_state = replacement.editor_state
    draft.save(update_fields=["sections", "plain_text", "editor_state", "updated_at"])
    replacement.delete()
    return draft


def _regenerate_blocks(draft, block_messages):
    from apps.drafting.services import regenerate_draft_block

    for block_key, messages in block_messages.items():
        instruction = (
            "Regenerate this block to fix validation errors:\n"
            + "\n".join(f"- {message}" for message in messages)
            + "\nDo not invent missing facts. Preserve accurate template data."
        )
        draft = regenerate_draft_block(draft, block_key, instruction)
    return draft


def _refresh_plain_text(draft):
    from apps.drafting.services import plain_text_from_sections

    draft.plain_text = plain_text_from_sections(draft.sections or [])
    draft.save(update_fields=["plain_text", "updated_at"])
    return draft


def apply_repairs(draft, repairable_findings):
    if any((finding.get("action") or {}).get("type") == "regenerate_document" for finding in repairable_findings):
        return _regenerate_document(draft)

    block_messages = {}
    has_plain_text_only = False
    for finding in repairable_findings:
        action = finding.get("action") or {}
        action_type = action.get("type")
        if action_type == "regenerate_block":
            block_key = (action.get("payload") or {}).get("blockKey") or (finding.get("location") or {}).get("blockKey")
            if block_key:
                block_messages.setdefault(block_key, []).append(finding["message"])
        elif action_type == "refresh_plain_text":
            has_plain_text_only = True

    if block_messages:
        return _regenerate_blocks(draft, block_messages)
    if has_plain_text_only:
        return _refresh_plain_text(draft)
    return draft


def validate_with_auto_repair(draft, *, max_attempts=2):
    attempts = []
    current = draft

    for attempt_index in range(max_attempts + 1):
        findings = validate_document(current)
        errors = [finding for finding in findings if finding["severity"] == "error"]
        repairable = [finding for finding in errors if is_repairable(finding)]

        attempts.append(
            {
                "attempt": attempt_index,
                "errorCount": len(errors),
                "repairableCount": len(repairable),
                "findings": findings,
            }
        )

        if not repairable or attempt_index >= max_attempts:
            current.validation_flags = findings
            current.save(update_fields=["validation_flags", "updated_at"])
            break

        current = apply_repairs(current, repairable)

    final = attempts[-1]
    summary = {
        "attempts": attempts,
        "autoRepaired": len(attempts) > 1,
        "remainingErrorCount": final["errorCount"],
        "warningCount": len([f for f in final["findings"] if f["severity"] == "warning"]),
        "infoCount": len([f for f in final["findings"] if f["severity"] == "info"]),
    }
    return current, summary
