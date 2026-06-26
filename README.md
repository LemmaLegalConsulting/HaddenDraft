# Legal Drafting Tool

This repository contains a working Django + React prototype for a housing court document drafting workspace. The app supports three modes:

- Research across configured source connectors.
- Draft from a structured template with human review points.
- Draft from scratch using a pleading shell and constrained section generation.

The implementation is intentionally modular so real integrations can replace the current stubs without rewriting the workflow.

## Requirements

- Python 3.12+
- Node.js 22+
- npm 11+

## First-Time Setup

From the repository root:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env

cd frontend
npm install
cd ..

.venv/bin/python backend/manage.py migrate
.venv/bin/python backend/manage.py createsuperuser
```

The app seeds templates through the API bootstrap path. Sample matters are opt-in with `ENABLE_DEMO_MATTERS=true`; by default, missing LegalServer access shows an unconnected/empty state instead of fake case data.

## Integration Configuration

Runtime settings are loaded from `.env` in the repository root. `.env` is intentionally ignored by git; `.env.example` documents the required keys.

- OpenAI-compatible drafting calls use `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL`. Set `AI_DRAFTING_ENABLED=false` to keep deterministic drafting fallbacks during local development.
- Case action recommendations default to `CASE_ACTION_MODEL` or `OPENAI_MODEL` when unset, so that workflow suggestions can use a different model from document drafting.
- AI prompts are file-backed YAML entries in [`prompts/`](prompts/README.md). Set `PROMPT_CATALOG_DIR` to a directory containing a benchmark variant catalog; enabled **Prompt overrides** in Django admin take precedence for operational edits.
- Research is constrained to a jurisdiction. Set the organization fallback with `DEFAULT_JURISDICTION`; Django admin's **Organization settings** can override it, and each user can set a **Default research jurisdiction** in Profile. A selected matter's jurisdiction takes precedence over both.
- Reusable legal-content defaults are maintained in [`content/`](content/README.md). Set `CONTENT_LIBRARY_DIR` only to point at an equivalent staged content library. DOCX snippets are resolved from the content library before legacy package defaults; triage YAML seeds new database records without replacing admin edits.
- Case chat document text extraction uses `DOCUMENT_TEXT_EXTRACTOR=stdlib` by default. Optional values are `markitdown` or `docling` when those packages are installed; the extractor interface is intentionally pluggable for custom backends.
- LegalServer uses `LEGALSERVER_BASE_URL`, `LEGALSERVER_API_TOKEN`, `LEGALSERVER_MATTERS_PATH`, `LEGALSERVER_MATTERS_RESULTS`, and `LEGALSERVER_MATTER_DOCUMENTS_PATH`. Matter search uses the v2 `/api/v2/matters` endpoint with `results=full`, `page_size`, and the documented text search keys. User access filtering is applied inside the app after LegalServer returns authorized records.
- SharePoint Online uses Microsoft Graph with `SHAREPOINT_SITE_ID`, `SHAREPOINT_DRIVE_ID`, and either a delegated `ms_graph_access_token` in the Django session or a service token in `SHAREPOINT_ACCESS_TOKEN`. Case document lookup uses `SHAREPOINT_CASE_FOLDER_TEMPLATE`.

Authentication uses Django's standard auth framework. Manual accounts authenticate through `/api/auth/login/`; Office 365 SSO can be fronted by an upstream OIDC/proxy layer and passed into Django with `ENABLE_REMOTE_USER_AUTH=true`.

Configure live connections in Django admin at `/admin/` under **Source configurations**. Admin rows use typed fields for each connection type and override `.env`; if a field is missing or no enabled row exists for a connection, the app falls back to `.env`.

Office 365 / SharePoint supports two access paths:

- **User delegated access:** save an enabled Office 365 entry under **User OAuth connections** for a Django user. SharePoint searches use that user's Graph token first, so the user sees documents their account can access.
- **Server fallback access:** configure SharePoint server credentials under **Source configurations**. The connector uses those only when there is no delegated user token, which supports volunteers or external users who should only see documents exposed through the server/legal-system integration.

For Office 365 sign-in across any work/school tenant, use `OFFICE365_TENANT_ID=organizations`. Use a concrete tenant ID only when sign-in should be restricted to that tenant.

## Start The Application

Run the backend and frontend in separate terminals.

Terminal 1, from the repository root:

```bash
.venv/bin/python backend/manage.py runserver 0.0.0.0:8000
```

Terminal 2, from the repository root:

```bash
cd frontend
npm run dev -- --port 5173
```

Then open:

- Frontend: http://localhost:5173/
- Django admin, proxied through Vite: http://localhost:5173/admin/
- Backend direct URL, when needed: http://localhost:8000/

The dev frontend proxies `/api`, `/admin`, `/static`, and `/favicon.ico` to Django, so normal local use happens through `http://localhost:5173/`. Django is still available directly at `http://localhost:8000/` when needed.

Django admin's **View site** link uses `FRONTEND_SITE_URL`, which defaults to `http://localhost:5173`.

## Useful Verification Commands

From the repository root:

```bash
.venv/bin/python backend/manage.py check
```

Run backend tests:

```bash
.venv/bin/python backend/manage.py test apps.ai apps.sources apps.core apps.matters
```

Run a quick backend workflow smoke test:

```bash
ENABLE_DEMO_MATTERS=true .venv/bin/python backend/manage.py shell -c "import json; from django.contrib.auth import get_user_model; from django.test import Client; User=get_user_model(); User.objects.update_or_create(username='smoke', defaults={'is_staff': True, 'is_superuser': True}); u=User.objects.get(username='smoke'); u.set_password('smoke-pass'); u.save(); c=Client(); assert c.login(username='smoke', password='smoke-pass'); assert c.get('/api/bootstrap/').status_code == 200; s=c.post('/api/drafting-sessions/', data=json.dumps({'mode':'draft_from_template','matterId':'LS-24018','templateId':1}), content_type='application/json').json()['session']; d=c.post(f\"/api/drafting-sessions/{s['id']}/draft/\", content_type='application/json').json()['draft']; print(d['title'], len(d['plainText']))"
```

Build the frontend:

```bash
cd frontend
npm run build
```

## Repository Layout

```text
.
├── backend/                  Django project and backend apps
├── brainstorming/            Original planning documents
├── clickable_prototype.js    Original clickable React prototype
├── content/                  Maintained DOCX snippets, treatise source/Markdown, and triage rubrics
├── docs/                     Architecture notes
├── frontend/                 Vite + React + Lexical frontend
└── requirements.txt          Python dependencies
```

## Backend Layout

```text
backend/
├── manage.py
├── config/
│   ├── settings.py           Django settings, dev CORS/CSRF config
│   └── urls.py               API and admin routes
└── apps/
    ├── ai/                   Constrained drafting service boundary
    ├── core/                 Shared JSON helpers, bootstrap, dev CORS middleware
    ├── drafting/             Drafting sessions, draft documents, workflow endpoints
    ├── exporting/            Export adapters
    ├── matters/              Case/matter data and candidate facts
    ├── sources/              Retrieval connector registry and source search
    ├── templates_app/        Document templates, blocks, template-from-example service
    └── validation/           Draft validation checks
```

Key extension points:

- Add a retrieval source by implementing `SourceConnector.search()` under `backend/apps/sources/connectors/` and registering it in `backend/apps/sources/registry.py`.
- Add or change document structure through `DocumentTemplate` and `TemplateBlock` in `backend/apps/templates_app/models.py`.
- Replace deterministic AI placeholders inside `backend/apps/ai/services.py`.
- Maintain LLM system/user messages in `prompts/*.yaml`; see [`prompts/README.md`](prompts/README.md) for the schema, benchmark workflow, and database-override behavior.
- Maintain reusable legal-content files in [`content/`](content/README.md). Run `.venv/bin/python backend/manage.py sync_content_library` to seed new triage-rubric files; use `--update-triage-rubrics` only when intentionally replacing existing database values.
- Add export formats in `backend/apps/exporting/services.py`.

## Frontend Layout

```text
frontend/
├── package.json
├── index.html
└── src/
    ├── App.jsx               Main workspace state and mode orchestration
    ├── api/client.js         Backend API client and CSRF header handling
    ├── components/           Case, fact, research, template, and workflow panels
    ├── editor/DraftEditor.jsx Lexical draft editor wrapper
    ├── main.jsx              React entry point
    └── styles/app.css        Application styling
```

Important frontend components:

- `CaseSelector`: selects and displays LegalServer-style matters.
- `ResearchPanel`: queries source connectors and shows retrieved support.
- `FactReview`: lets a human select candidate facts before drafting.
- `TemplatePicker`: selects templates and optional prewritten clauses.
- `TemplateBuilder`: creates a structured template outline from example text.
- `DraftEditor`: Lexical editing surface for generated draft text.

## Current Prototype Notes

- The source connectors are stubs with realistic contracts, not production LegalServer, SharePoint, or vector search integrations.
- SQLite is used for local development.
- Export currently returns editable plain text. DOCX export belongs behind `backend/apps/exporting/`.
- More detailed architecture notes are in `docs/ARCHITECTURE.md`.
