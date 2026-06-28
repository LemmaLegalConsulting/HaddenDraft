from apps.templates_app.template_variables import block_variable_metadata, template_variable_metadata


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
        "jurisdiction": template.jurisdiction,
        "sourceLabel": template.source_label,
        "metadata": template.metadata,
        "sourceKind": template.source_kind,
        "contentPath": template.content_path,
        "isActive": template.is_active,
        "createdFromExample": template.created_from_example,
    }
    if include_blocks:
        data["blocks"] = [block_to_dict(block) for block in template.blocks.all()]
        data["wordTemplateVariables"] = template_variable_metadata(template)
    return data
