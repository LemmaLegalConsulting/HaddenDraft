from pathlib import Path

from apps.core.content_library import content_path
from apps.templates_app.content_library import resolve_content_asset


DEFAULT_WORD_TEMPLATE_DIR = Path(__file__).resolve().parent / "default_word_templates"


def content_block_template_path(template, block):
    """Return a top-level content-library snippet, if one has been maintained."""
    candidates = [
        content_path("docx-snippets", template.slug, "blocks", f"{block.key}.docx"),
        content_path("docx-snippets", template.slug, "blocks", f"{block.block_type}.docx"),
        content_path("docx-snippets", "_shared", "blocks", f"{block.block_type}.docx"),
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def default_style_template_path(template):
    path = DEFAULT_WORD_TEMPLATE_DIR / template.slug / "style.docx"
    if path.exists():
        return path
    return None


def default_block_template_path(template, block):
    content_path_override = content_block_template_path(template, block)
    if content_path_override:
        return content_path_override
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
    if block.content_path:
        path = resolve_content_asset(block.content_path)
        if path.exists():
            return path
    return default_block_template_path(template, block)


def block_template_source(template, block):
    if block.docx_template:
        return "admin"
    if block.content_path and resolve_content_asset(block.content_path).exists():
        return "content_library"
    if content_block_template_path(template, block):
        return "content_library"
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
    if template.source_kind == "content_library" and template.content_path:
        return True
    if template.style_template or default_style_template_path(template):
        return True
    return template.blocks.filter(docx_template__gt="").exists() or any(
        default_block_template_path(template, block)
        for block in template.blocks.all()
    )
