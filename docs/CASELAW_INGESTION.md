# Case-Law Corpus Ingestion

The caselaw corpus is stored in two places:

- Searchable metadata, OCR text, chunks, and provenance live in the Django database.
- Original PDFs and sidecar files live in the configured caselaw artifact storage backend.

Case files are not source-controlled. For local development, keep them under a
private import directory such as `~/cases` and copy artifacts into
`private-content/caselaw-artifacts`.

The repository-local `downloaded_cases/` directory is ignored because it is a
generated acquisition cache. If a downloaded corpus needs to be retained,
store it outside the repository and pass its path explicitly to the staging
helper:

```bash
.venv/bin/python scripts/ingest_downloaded_cases.py \
  --source-dir ~/case-law-cache/downloaded_cases
```

The helper copies only complete, verified PDF sidecar sets into the private
artifact provider. It does not make the source corpus part of Git history.

## Storage Areas

Case-law artifacts are one tenant of the shared document store in
[`apps.core.storage`](../backend/apps/core/storage.py), which splits every store
into two areas:

```text
raw/caselaw/...        sidecar bundles as downloaded, awaiting ingestion
published/caselaw/...  derived artifacts the application serves
```

Nothing serves out of `raw/`. That is what makes a slow upload safe: bundles can
accumulate for as long as they need to without a running replica seeing a
half-finished corpus, and ingestion is the single moment the change becomes
visible.

`.env` defaults are suitable for development:

```bash
DOCUMENT_STORAGE_BACKEND=filesystem
DOCUMENT_STORAGE_ROOT=private-content/storage
CASELAW_IMPORT_APPROVE_VERIFIED_FOR_SEARCH=true
CASELAW_IMPORT_APPROVE_UNVERIFIED_FOR_SEARCH=false
```

Import from a local directory, or from the raw storage area:

```bash
.venv/bin/python backend/manage.py ingest_caselaw ~/cases --dry-run
.venv/bin/python backend/manage.py ingest_caselaw ~/cases

# Stage every object under raw/caselaw/ to a temporary directory and ingest it.
.venv/bin/python backend/manage.py ingest_caselaw --from-raw-storage
```

Use `--allow-missing-pdf` or `--allow-missing-text` only for intentionally incomplete imports. Use `--require-verified` when only reviewed metadata should be accepted.

Ingestion is idempotent: a decision whose `source_sha256` is already recorded is
skipped unless `--force` is given, so re-running costs a scan and changes
nothing.

## Sidecar Naming

Files are grouped by canonical case stem, and **two namings are recognized**.

Downloaded bundles append to the PDF's full name:

```text
Some Case.pdf
Some Case.pdf.txt
Some Case.pdf.json
Some Case.verified.json
```

Published artifacts are named by content hash with a plain extension, because
the storage layer splits them across directories by artifact type:

```text
originals/<sha>.pdf
ocr-text/<sha>.txt
metadata/<sha>.json
metadata/<sha>.verified.json
```

`.verified.json` wins over `.pdf.json`, and where both namings exist for one
case the more specific suffix wins. Recognizing only the first form is what once
reduced a complete 1,215-case corpus to `missing_text` on every group and
imported zero decisions — so the published layout must stay re-ingestable.

## Production Storage

The current deployment uses `filesystem` with `DOCUMENT_STORAGE_ROOT` pointing at
mounted Azure Files shares, one per area.

To move to object storage, install `boto3` and set:

```bash
DOCUMENT_STORAGE_BACKEND=s3
DOCUMENT_STORAGE_BUCKET=
DOCUMENT_STORAGE_ENDPOINT_URL=   # omit for AWS; set for R2, B2, MinIO
DOCUMENT_STORAGE_ACCESS_KEY_ID=
DOCUMENT_STORAGE_SECRET_ACCESS_KEY=
DOCUMENT_STORAGE_REGION=
```

Ingestion, views, and the publish step talk only to `DocumentStorage`, so
provider-specific APIs stay out of models, commands, and search connectors.
`CaseLawArtifact.storage_key` rows are recorded relative to the area, so they
stay valid across a backend change.

One caveat before switching: `ORGANIZATION_CONTENT_LIBRARY_DIR` is a filesystem
path that the content library walks directly. Under `s3` it would need a local
materialization step rather than pointing into the published area.

## Research

Imported decisions are exposed through the existing `local_cases` source connector. The research UI has a cases-only mode for exploring imported cases without secondary materials, and manual source selection can search cases alongside treatises and statutes for cross-reference work.
