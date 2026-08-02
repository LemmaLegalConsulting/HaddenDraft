# Legal Drafting Tool Architecture

This implementation is organized around reviewable workflow boundaries rather than a single free-form agent.

## Backend

- `apps.matters`: LegalServer-style matter records and extracted candidate facts.
- `apps.sources`: pluggable retrieval connectors. New source types implement `SourceConnector.search()` and are registered in `registry.py`.
- `apps.templates_app`: reusable document templates, deterministic blocks, optional clauses, and template creation from example text.
- `apps.templates_app` also owns the loss-minimizing DOCX ingestion and manifest
  index. `content/document-templates/` is authoritative for file-managed
  templates; database rows are a query/index cache and never replace the files.
- `content/`: provider-neutral, file-backed defaults for reusable DOCX snippets, authoritative treatise PDFs and Markdown derivatives, and triage rubric seeds. Django packages consume logical content paths rather than owning these legal assets.
- `apps.drafting`: drafting sessions, selected facts/source results/block keys, draft documents, and workflow advancement.
- `apps.drafting.components`: the durable artifact layer under `DraftDocument`. See [Document components and versions](#document-components-and-versions).
- `apps.ai`: constrained AI service boundary, including the YAML prompt catalog and optional database overrides. Default prompts are repository files in `prompts/`, which keeps benchmark variants reviewable and independent from application code.
- `apps.validation`: output checks for missing facts, tentative language, citation-like strings, and length.
- `apps.exporting`: export adapters. The first adapter exports editable plain text; this is the boundary for future DOCX generation.

## Document components and versions

`DraftDocument.sections` is the JSON shape the editor, validation, and export
paths read, and it stays that way. Underneath it, every section is also stored as
a durable domain object:

- `DocumentComponent`: one addressable part of a document, identified by a
  `stable_key` (normally the template block key) that survives rewrites of the
  section JSON. A component dropped from the document is retired with
  `removed_at` rather than deleted, so its history stays auditable.
- `ComponentVersion`: an append-only body/`structured_content` snapshot with the
  `origin` that produced it (`template`, `ai`, `human`, `validation_repair`,
  `rollback`) and the instruction that was given.

`apps.drafting.components.record_sections()` is the single write path: it saves
the section JSON, refreshes plain text, and records a version for each component
whose content actually changed. Generation, block regeneration, reviewer edits
through `PATCH /api/drafts/<id>/`, and validation auto-repair all go through it,
so each one is attributable. `GET /api/drafts/<id>/components/` returns the
per-component version history.

This is what makes narrower operations possible: regenerating one section no
longer discards the text it replaced, and the document's prior states remain
recoverable.

## Draft operations

`apps.drafting.operations` describes a change to a document before it is made.
A `DraftOperation` names its type (`replace_component`, `insert_component`,
`delete_component`, `move_component`, `revert_component`), its target component,
a payload, a rationale, and its status (`proposed`, `applied`, `rejected`).

Proposal and application are separate. `propose()` validates the described
change against the current document and stores it without touching the draft;
`apply()` runs the deterministic applier in a transaction and records the
resulting component versions. A resolved operation cannot be applied twice.

Block regeneration and reviewer-initiated edits go through this path, so the
draft's change log is the operation list rather than a series of anonymous
overwrites. `revert_component` restores an earlier component version as a new
version, which is how a bad regeneration is undone without losing the record
that it happened.

The API is `GET|POST /api/drafts/<id>/operations/` and
`POST /api/drafts/<id>/operations/<operation_id>/decision/` with
`{"decision": "apply" | "reject"}`. Proposing with `{"apply": true}` records and
applies in one request, which is what an already-approved reviewer edit does.

This is also the seam for any future model-driven drafting stage: something that
may propose operations but not write documents needs no new permission model,
because proposals are inert until a reviewer applies them.

## Frontend

The React app mirrors the backend boundaries:

- `CaseSelector`: matter selection and case summary.
- `ResearchPanel`: source-aware retrieval across LegalServer, SharePoint, RAG content, local cases, and user resources.
- `FactReview`: human review of candidate facts before generation.
- `TemplatePicker`: deterministic template and clause selection.
- `TemplateBuilder`: create a structured template outline from example text.
- `DraftEditor`: Lexical editor boundary for draft review and manual edits.

## Workflow Modes

- `research`: retrieval only, no draft required.
- `draft_from_template`: linear case -> facts -> template -> law/source support -> draft -> validation/export.
- `draft_from_scratch`: uses a pleading shell and instructions for section-level constrained generation.

The stub connectors are intentionally replaceable. They make the application runnable now while preserving clean integration points for real LegalServer, Microsoft Graph/SharePoint, vector search, archived case indexes, and user-upload pipelines.

## Maintained legal-content library

The repository's top-level [`content/`](../content/README.md) directory is the
default local content provider. It has three independently auditable areas:

- `docx-snippets/` provides shared blocks and per-template-pathway overrides.
  Admin uploads remain the highest-precedence operational override.
- `document-templates/` provides full-document DOCX/Jinja packages. Its manifest
  maps input fields and list expectations to Lexical blocks. Full-document export
  preserves the source package's headers, tables, numbering, media, and sections;
  pathway snippets remain available for block composition and overrides.
- `treatises/source/` retains authoritative incoming PDFs; `treatises/markdown/`
  holds deterministic heading-preserving derivatives for a future chunking and
  retrieval ingestion workflow.
- `triage-rubrics/` holds YAML seed records. Synchronization creates missing
  database records and does not overwrite an existing admin-managed rubric
  unless the explicit management-command update flag is used.

`CONTENT_LIBRARY_DIR` permits a staged local copy of this layout. A SharePoint
implementation belongs behind this provider boundary, selected explicitly by an
administrator at the organization/package level. It should preserve remote item
identity, ETag, modified time, source path, checksum, and import time alongside
every processed record; it should not silently replace repository defaults.
