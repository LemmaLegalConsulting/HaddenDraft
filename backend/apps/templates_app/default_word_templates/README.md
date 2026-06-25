# Default Word templates

These .docx files are repository defaults for composed Word exports. Admin-uploaded files on `DocumentTemplate.style_template` and `TemplateBlock.docx_template` take precedence.

Template lookup order is: admin-uploaded block file, template-specific repository block file, generic repository block file, text fallback.

Common Jinja variables: `{{ section.body }}`, `{{ section.label }}`, `{{ document.title }}`, `{{ court }}`, `{{ plaintiff }}`, `{{ defendant }}`, `{{ case_number }}`, `{{ advocate_name }}`, `{{ advocate_organization }}`, `{{ advocate_address }}`, `{{ advocate_phone }}`, `{{ advocate_email }}`.
