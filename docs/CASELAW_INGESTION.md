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

## Local Storage

`.env` defaults are suitable for development:

```bash
CASELAW_STORAGE_BACKEND=filesystem
CASELAW_STORAGE_ROOT=private-content/caselaw-artifacts
CASELAW_IMPORT_APPROVE_VERIFIED_FOR_SEARCH=true
CASELAW_IMPORT_APPROVE_UNVERIFIED_FOR_SEARCH=false
```

Import a processed PDF corpus:

```bash
.venv/bin/python backend/manage.py ingest_caselaw ~/cases --dry-run
.venv/bin/python backend/manage.py ingest_caselaw ~/cases
```

Use `--allow-missing-pdf` or `--allow-missing-text` only for intentionally incomplete imports. Use `--require-verified` when only reviewed metadata should be accepted.

## Sidecar Naming

Files are grouped by canonical case stem:

```text
Some Case.pdf
Some Case.pdf.txt
Some Case.pdf.json
Some Case.verified.json
```

`Some Case.verified.json` wins over `Some Case.pdf.json`. OCR text is read from `Some Case.pdf.txt`.

## Production Storage

Set `CASELAW_STORAGE_BACKEND=object` and configure the S3-compatible object settings:

```bash
CASELAW_STORAGE_BUCKET=
CASELAW_STORAGE_ENDPOINT_URL=
CASELAW_STORAGE_ACCESS_KEY_ID=
CASELAW_STORAGE_SECRET_ACCESS_KEY=
CASELAW_STORAGE_REGION=
```

The ingestion code talks only to `CaseLawStorage`, so provider-specific APIs stay out of models, commands, and search connectors.

## Research

Imported decisions are exposed through the existing `local_cases` source connector. The research UI has a cases-only mode for exploring imported cases without secondary materials, and manual source selection can search cases alongside treatises and statutes for cross-reference work.
