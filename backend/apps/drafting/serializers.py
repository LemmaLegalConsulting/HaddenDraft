from apps.drafting import opposing_filing
from apps.drafting.revisions import validation_state
from apps.drafting.services import normalize_status, workflow_step_payload
from apps.matters.serializers import matter_to_dict
from apps.templates_app.serializers import template_to_dict


def session_to_dict(session):
    return {
        "id": session.id,
        "mode": session.mode,
        "status": normalize_status(session.status),
        "workflowSteps": workflow_step_payload(),
        "matter": matter_to_dict(session.matter, include_facts=True),
        "template": template_to_dict(session.template, include_blocks=True) if session.template else None,
        "selectedFactIds": session.selected_fact_ids,
        "selectedCuratedFacts": session.selected_curated_facts,
        "selectedSourceResults": session.selected_source_results,
        "selectedBlockKeys": session.selected_block_keys,
        "authorProfile": session.author_profile,
        "templateData": session.template_data,
        "goal": session.goal,
        "draftPlan": session.draft_plan,
        "missingInformation": session.missing_information,
        "selectedTemplateIds": session.selected_template_ids,
        "instructions": session.instructions,
        "workflowOptions": session.workflow_options or {},
        "opposingFiling": opposing_filing.to_dict(opposing_filing.filing_for(session)),
        "revision": session.revision,
        "updatedAt": session.updated_at.isoformat(),
    }


def draft_to_dict(draft):
    template = draft.template or draft.session.template
    render = ((template.metadata or {}).get("render") or {}) if template else {}
    return {
        "id": draft.id,
        "sessionId": draft.session_id,
        "templateId": draft.template_id,
        "title": draft.title,
        "exportFormat": "xlsx" if render.get("strategy") == "workbook" else "docx",
        "sections": draft.sections,
        "plainText": draft.plain_text,
        "editorState": draft.editor_state,
        "validationFlags": draft.validation_flags,
        "revision": draft.revision,
        # Which revision the findings above describe: "current", "stale", or
        # "never" checked. Empty findings mean clean only when current.
        "validation": validation_state(draft),
        "updatedAt": draft.updated_at.isoformat(),
    }
