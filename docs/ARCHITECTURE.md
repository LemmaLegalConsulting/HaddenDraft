# Legal Drafting Tool Architecture

This implementation is organized around reviewable workflow boundaries rather than a single free-form agent.

## Backend

- `apps.matters`: LegalServer-style matter records and extracted candidate facts.
- `apps.sources`: pluggable retrieval connectors. New source types implement `SourceConnector.search()` and are registered in `registry.py`.
- `apps.templates_app`: reusable document templates, deterministic blocks, optional clauses, and template creation from example text.
- `apps.drafting`: drafting sessions, selected facts/source results/block keys, draft documents, and workflow advancement.
- `apps.ai`: constrained AI service boundary. The current implementation is deterministic and marks the points where LLM calls can later be added.
- `apps.validation`: output checks for missing facts, tentative language, citation-like strings, and length.
- `apps.exporting`: export adapters. The first adapter exports editable plain text; this is the boundary for future DOCX generation.

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
