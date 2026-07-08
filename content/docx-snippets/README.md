# DOCX snippet maintenance

Only generic, non-confidential reusable DOCX blocks belong under
`_shared/blocks/` in this public repository. Organization-specific and
pathway-specific blocks belong under
`ORGANIZATION_CONTENT_LIBRARY_DIR/docx-snippets/<template-slug>/blocks/`
(the default local root is the git-ignored `private-content/` directory).
See the parent [`content/README.md`](../README.md) for provider precedence and
supported variables.

Pathway block files produced by `ingest_document_templates` are generated in
the private organization provider from the corresponding source DOCX while
retaining its OOXML formatting. Correct the source document or converter and
regenerate them; do not hand-edit or commit generated blocks. Variants remain
scoped to their template so legally meaningful differences are not collapsed.
