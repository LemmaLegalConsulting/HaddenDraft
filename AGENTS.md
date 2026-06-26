# Repository maintenance pattern

Reusable legal-content defaults belong in the top-level [`content/`](content/README.md)
library, not inside a Django app or embedded in Python constants.

- Put shared DOCX snippets in `content/docx-snippets/_shared/blocks/` and
  pathway overrides in `content/docx-snippets/<template-slug>/blocks/`.
- Put authoritative treatise PDFs under `content/treatises/source/`; keep
  generated Markdown under `content/treatises/markdown/` and do not hand-edit
  it.
- Put default triage rubrics in `content/triage-rubrics/*.yaml`. Seed new files
  into the database; do not silently overwrite existing admin-managed records.
- Treat `CONTENT_LIBRARY_DIR` as a content-provider boundary. Future SharePoint
  support must preserve the same logical paths and record remote provenance
  before writing derived data.

See [`content/README.md`](content/README.md) for the complete maintenance,
precedence, and future SharePoint-provider guidance.
