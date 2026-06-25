from pathlib import Path


DEFAULT_WORD_TEMPLATE_DIR = Path(__file__).resolve().parent / "default_word_templates"


def default_style_template_path(template):
    path = DEFAULT_WORD_TEMPLATE_DIR / template.slug / "style.docx"
    if path.exists():
        return path
    return None


def default_block_template_path(template, block):
    candidates = [
        DEFAULT_WORD_TEMPLATE_DIR / template.slug / "blocks" / f"{block.key}.docx",
        DEFAULT_WORD_TEMPLATE_DIR / template.slug / "blocks" / f"{block.block_type}.docx",
        DEFAULT_WORD_TEMPLATE_DIR / "_generic" / "blocks" / f"{block.block_type}.docx",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def block_template_path(template, block):
    if block.docx_template:
        return block.docx_template.path
    return default_block_template_path(template, block)


def block_template_source(template, block):
    if block.docx_template:
        return "admin"
    if default_block_template_path(template, block):
        return "repository"
    return "body"


def style_template_path(template):
    if template.style_template:
        return template.style_template.path
    return default_style_template_path(template)


def has_word_template_assets(template):
    if not template:
        return False
    if template.style_template or default_style_template_path(template):
        return True
    return template.blocks.filter(docx_template__gt="").exists() or any(
        default_block_template_path(template, block)
        for block in template.blocks.all()
    )
