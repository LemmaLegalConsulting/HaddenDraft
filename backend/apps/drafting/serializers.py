from apps.matters.serializers import matter_to_dict
from apps.templates_app.serializers import template_to_dict


def session_to_dict(session):
    return {
        "id": session.id,
        "mode": session.mode,
        "status": session.status,
        "matter": matter_to_dict(session.matter, include_facts=True),
        "template": template_to_dict(session.template, include_blocks=True) if session.template else None,
        "selectedFactIds": session.selected_fact_ids,
        "selectedSourceResults": session.selected_source_results,
        "selectedBlockKeys": session.selected_block_keys,
        "instructions": session.instructions,
        "updatedAt": session.updated_at.isoformat(),
    }


def draft_to_dict(draft):
    return {
        "id": draft.id,
        "sessionId": draft.session_id,
        "title": draft.title,
        "sections": draft.sections,
        "plainText": draft.plain_text,
        "editorState": draft.editor_state,
        "validationFlags": draft.validation_flags,
        "updatedAt": draft.updated_at.isoformat(),
    }
