from apps.templates_app.template_variables import LEGACY_LITERAL_FIELDS, block_variable_metadata, template_variable_metadata


def _public_template_metadata(template):
    metadata = dict(template.metadata or {})
    fields = metadata.get("fields")
    if isinstance(fields, list):
        metadata["fields"] = [
            path
            for path in fields
            if str(path).removeprefix("fields.") not in LEGACY_LITERAL_FIELDS
        ]
    return metadata


def block_to_dict(block):
    template = getattr(block, "template", None)
    return {
        "id": block.id,
        "key": block.key,
        "label": block.label,
        "blockType": block.block_type,
        "order": block.order,
        "body": block.body,
        "required": block.required,
        "aiFillMode": block.ai_fill_mode,
        "aiLatitude": block.ai_latitude,
        "aiInstructions": block.ai_instructions,
        "selectionRule": block.selection_rule,
        "supportingSources": block.supporting_sources,
        "inputSchema": block.input_schema,
        "lexicalConfig": block.lexical_config,
        "editable": block.editable,
        "contentPath": block.content_path,
        "wordTemplateVariables": block_variable_metadata(template, block) if template else None,
    }


def template_to_dict(template, include_blocks=False):
    data = {
        "id": template.id,
        "slug": template.slug,
        "title": template.title,
        "kind": template.kind,
        "description": template.description,
        "goal": template.goal,
        "negativeGoal": template.negative_goal,
        "aliases": template.aliases or [],
        "jurisdiction": template.jurisdiction,
        "sourceLabel": template.source_label,
        "metadata": _public_template_metadata(template),
        "sourceKind": template.source_kind,
        "contentPath": template.content_path,
        "isActive": template.is_active,
        "createdFromExample": template.created_from_example,
    }
    if include_blocks:
        data["blocks"] = [block_to_dict(block) for block in template.blocks.all()]
        data["wordTemplateVariables"] = template_variable_metadata(template)
    return data
