# Repository maintenance pattern

Reusable legal-content defaults belong in the top-level [`content/`](content/README.md)
library, not inside a Django app or embedded in Python constants.

- Put shared DOCX snippets in `content/docx-snippets/_shared/blocks/` and
  pathway overrides in `private-content/docx-snippets/<template-slug>/blocks/`.
- Put organization letterheads in `<provider>/letterheads/<slug>/` with a
  `manifest.yaml` and `letterhead.docx`. Real stationery is private; keep a
  neutral placeholder in `content/letterheads/` so a fresh checkout can draft.
- Put authoritative treatise PDFs under `content/treatises/source/`; keep
  generated Markdown under `content/treatises/markdown/` and do not hand-edit
  it.
- Put default triage rubrics in `content/triage-rubrics/*.yaml`. Seed new files
  into the database; do not silently overwrite existing admin-managed records.
- Read generated manifests through `apps.sources.library.load_manifest()`, never
  with a bare `yaml.safe_load`. It caches each parse against the file's mtime and
  size and uses libyaml when available; a code manifest is megabytes of YAML that
  the pure-Python parser needs seconds to read, and browsing, retrieval, and every
  citation preview all parse the same files.
- Treat `CONTENT_LIBRARY_DIR` as a content-provider boundary. Future SharePoint
  support must preserve the same logical paths and record remote provenance
  before writing derived data.
- Side-loaded documents go through `apps.core.storage`, never through direct
  filesystem or SDK calls. Every store has a `raw/` area an operator uploads into
  and a `published/` area the application reads; nothing serves out of `raw/`,
  and only an ingest or publish step writes to `published/`. Keep provider APIs
  behind `DocumentStorage` so moving between a mounted share and S3 stays a
  configuration change.
- Keep the published layout re-ingestable. Ingestion once recognized only the
  download naming (`*.pdf.txt`) while storage wrote the published naming
  (`<sha>.txt`), so a complete corpus reported `missing_text` on every group and
  imported nothing, silently. A round trip through storage must be a no-op, not a
  loss — and a corpus that reports itself incomplete deserves suspicion of the
  reader before the data.

See [`content/README.md`](content/README.md) for the complete maintenance,
precedence, and future SharePoint-provider guidance.

## Development workflow

This is a Django + React prototype. Work from the repository root unless a
command says otherwise.

- Backend setup and checks use the local virtualenv:
  - `.venv/bin/pip install -r requirements.txt`
  - `.venv/bin/python backend/manage.py migrate`
  - `.venv/bin/python backend/manage.py check`
  - `.venv/bin/python backend/manage.py test apps.ai apps.sources apps.core apps.matters`
- Frontend work happens under `frontend/`:
  - `npm install`
  - `npm run test`
  - `npm run build`
- When changing both backend and frontend behavior, verify the API contract and
  the UI path that consumes it.

## Application boundaries

Keep changes aligned with the existing workflow boundaries:

- Retrieval/source integrations belong under `backend/apps/sources/`; new
  connectors should implement `SourceConnector.search()` and be registered in
  `backend/apps/sources/registry.py`.
- Drafting orchestration belongs under `backend/apps/drafting/`. Write draft
  section JSON only through `apps.drafting.components.record_sections()`, and
  express changes to an existing document as `apps.drafting.operations`
  proposals, so component history and provenance stay complete.
- AI prompt execution and model-facing logic belong under `backend/apps/ai/`.
- Template and reusable block behavior belongs under
  `backend/apps/templates_app/`.
- A prepared template keeps the maintained original's wording. Convert only
  language the author marked as variable (`[...]`, `____`, highlighting) through
  `apps.templates_app.placeholders`; never rebind ordinary prose to a model-written
  slot. Rewrite paragraphs run by run so inline formatting survives.
- Express either/or clauses as a named choice with Docassemble/AssemblyLine
  conventions: a snake_case variable, snake_case option values, and
  paragraph-level `{%p if %}`/`{%p elif %}` tags. Make the first alternative the
  default so an unanswered choice never deletes the passage.
- Express how much the model may write as a block's `ai_latitude`
  (`locked`/`guided`/`generate`). Latitude constrains the model only: a human
  edit must always reach the export through `blocks[<key>]["revision"]`.
- Client advice letters are catalogued as `AdviceLetterSection`, not as
  `DocumentTemplate`. The unit that gets picked and reviewed is the section. Keep
  assembly deterministic: the wording is what the working group revised for
  readability, and regenerating it discards that work.
- Offer every advice-letter section, and say which ones need checking. Text that
  carries accepted tracked changes, a merge-boundary passage, or AI drafting is
  flagged with `needs_attorney_review` and a one-line reason rather than hidden;
  withholding it once hid the best match for a case behind a stale status.
- Do not let `sync_advice_letters` overwrite a section marked `is_locally_edited`.
  An attorney's read and correction must survive the next ingest.
- Score client-facing text with `apps.validation.readability`, whose rules are
  file-backed in `content/drafting-rules/checks/`. Report several formulas rather
  than treating one as authoritative, and never rewrite text purely to move a
  score.
- Letterhead behavior belongs in `apps.templates_app.letterheads`. A letterhead
  prepared for sharing must carry no trace of the advocate whose file seeded it,
  including document properties and `mailto:`/`attachedTemplate` relationships.
- Export formats belong behind `backend/apps/exporting/`.
- Frontend API calls should go through `frontend/src/api/client.js`; avoid
  scattering fetch logic through components.
- Frontend derivation and state logic belongs in plain `.js` modules with
  `node --test` coverage under `frontend/test/`; keep `.jsx` components
  presentational so the rules stay testable without a browser runtime.

Do not replace reviewable workflow steps with a single free-form agent flow.
Preserve human review points for facts, template choices, source support,
validation, and export.

## Prompt catalog rules

Runtime prompts belong in file-backed YAML under `prompts/`, not hardcoded in
Python or React.

- Use one `*.yaml` or `*.yml` file per prompt key.
- Keep prompt placeholders explicit and named with Python `{name}` syntax.
- Do not rely on Django admin prompt overrides for benchmark variants or
  source-controlled behavior.
- If a prompt's required variables, model default, or reasoning default changes,
  update the YAML and any tests or call sites together.

## Legal content and generated assets

Never commit client documents, credentials, private organization templates, or
other confidential material.

- Public reusable defaults belong under `content/`.
- Private organization material belongs under `ORGANIZATION_CONTENT_LIBRARY_DIR`,
  normally `private-content/`, which should remain git-ignored.
- Do not hand-edit generated Markdown, generated statute chunks, generated
  manifests, or ingested template package outputs. Fix the source document,
  converter, or ingestion script and regenerate.
- Record where an extracted date came from, not just its value. Dates on case-law
  decisions are model-read out of scanned paper, so `apps.caselaw.dates` writes a
  `CaseLawDateProvenance` row per field carrying the source sidecar, its checksum,
  and the passage in the document's own OCR text that shows the date. Corroborated
  means the text contains it, never that it has been confirmed to mean what the
  field says. An uncorroborated date is unverifiable, not wrong: the scans carry
  complete OCR, so the date is simply not printed on the page in readable form.
- Preserve provenance for legal authorities and remote/private content,
  including source path, checksum, modified time, fetch/import time, and remote
  IDs where available.
- Treat generated legal-source records as research aids only; do not imply they
  replace checking current law before filing.

## Environment and secrets

Runtime configuration belongs in `.env`; `.env` must stay untracked.

- Keep `.env.example` current when adding or renaming settings.
- Do not add API keys, access tokens, tenant secrets, LegalServer credentials,
  SharePoint tokens, or client-identifying data to tests, fixtures, screenshots,
  docs, or sample content.
- Prefer deterministic fallbacks for local development unless a change
  explicitly needs live AI, LegalServer, SharePoint, or Office 365 access.

## Change style

Prefer small, reviewable changes that keep legal content, prompts, provider
integrations, and UI behavior auditable.

- Document new management commands, environment variables, and content-provider
  paths in the relevant README.
- Add or update tests for behavior changes in backend services, prompt loading,
  content ingestion, retrieval connectors, or frontend data handling.
- Keep naming lowercase kebab-case for content-library files and directories.
