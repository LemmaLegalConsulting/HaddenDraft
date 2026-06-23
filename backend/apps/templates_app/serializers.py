def block_to_dict(block):
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
        "createdFromExample": template.created_from_example,
    }
    if include_blocks:
        data["blocks"] = [block_to_dict(block) for block in template.blocks.all()]
    return data
