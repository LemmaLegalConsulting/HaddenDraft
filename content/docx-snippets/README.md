# DOCX snippet maintenance

Add reusable DOCX blocks under `_shared/blocks/`. Add a pathway-specific
override under `<template-slug>/blocks/` using the same block key or block type
file name (for example, `caption.docx` or `signature.docx`). See the parent
[`content/README.md`](../README.md) for precedence and supported variables.

Pathway block files produced by `ingest_document_templates` are generated from
the corresponding original DOCX while retaining its OOXML formatting. Correct
the source document or converter and regenerate them; do not hand-edit generated
blocks. The ingestion job promotes only text-identical repeated captions,
signatures, or certificates to `_shared/blocks/`; variants remain scoped to
their template so legally meaningful differences are not collapsed.
