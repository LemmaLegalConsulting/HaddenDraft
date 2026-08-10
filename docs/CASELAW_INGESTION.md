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

## What is actually in the corpus

The artifact bundle holds two different kinds of document, and counting them
together gives a badly wrong picture of the corpus.

| | bundles | median PDF | median OCR text | in the database |
|---|---|---|---|---|
| Scanned decisions | 532 | ~900 KB, DigiPath | 4,908 bytes | yes |
| Citation stubs | 683 | 6–8 KB, WeasyPrint | 95 bytes | no |

The stubs are single-page PDFs *generated* from HTML, not scans. Each contains a
case caption and a citation line and nothing else — the opinion was never
obtained. OCR read them correctly; there was one line to read. Their metadata
sidecars say so plainly ("Holdings cannot be determined from the provided OCR
excerpt; full opinion text is required"), so nothing was invented from them.

The scanned decisions are image-only (`pdftotext` returns nothing but form
feeds) and were OCR'd completely: median 1,437 characters per page, and not one
of the 532 falls below 413 characters per page. There is no truncation anywhere
in the corpus, which is what a rate-limited or partially failed OCR run would
have left behind.

So a document with no text is not an OCR failure to retry. It is a document that
was never fetched, and re-running OCR over it — with any engine — returns the
same caption and citation. Filling that gap means acquiring the opinions.

## Filling citation-only records from the Caselaw Access Project

CAP publishes its scanned reporters as static files — no API key, no request
signing — laid out by reporter and volume:

```
/<reporter>/<volume>/CasesMetadata.json    every case in the volume
/<reporter>/<volume>/cases/<file>.json     one case, with opinion text
/<reporter>/<volume>/case-pdfs/<file>.pdf  the reporter pages themselves
```

A reporter citation is a volume and a first page, which is enough to find a case
without searching. So a citation stub can be turned back into a readable
opinion:

```bash
python manage.py fetch_cap_opinions --dry-run    # resolve, write nothing
python manage.py fetch_cap_opinions              # stage bundles into raw/caselaw/
python manage.py ingest_caselaw --from-raw-storage
```

Staging and ingestion stay separate so an operator can look at what arrived
before it reaches the database. Bundles are written in the naming ingestion
already reads (`<stem>.pdf`, `<stem>.pdf.txt`, `<stem>.pdf.json`), the stem
identifying the CAP case (`cap-ohio-st-104-0372-01`), so a re-run skips what is
already staged.

Each fetched sidecar records where it came from — `external_source_id`
(`cap:<id>`), the source URL, and CAP's own provenance block — and carries
`treatment_status: unchecked` with a note saying currentness has not been
checked. Where the record answers an existing stub, `replaces_source_sha256`
names it, so the stub can be retired deliberately instead of being left as a
silent duplicate.

Two limits worth knowing before running it:

- **CAP's coverage ends where its scanning did**, around 2018-2020. A citation
  newer than its reporter's run is not a failure to retry; it stays a
  citation-only record. That is still worth having: it confirms the cited case
  exists, which is what most of a citation check needs.
- **Fetched cases import with `approved_for_search` off**, because no one has
  reviewed them — they are what CAP published, not what a person checked. They
  stay out of research until approved at **Case law › Case law decisions** in
  admin, or ingested with `CASELAW_IMPORT_APPROVE_UNVERIFIED_FOR_SEARCH=true`.

### Summarizing what was fetched

A fetched opinion arrives as text. The analytical fields research depends on —
issues, holdings, statutes cited, key facts, outcome — come from the same two
passes that built the rest of this corpus:

```bash
python manage.py enrich_caselaw_metadata --dry-run
python manage.py enrich_caselaw_metadata   # gpt-5-mini drafts, deepseek-v4 checks
python manage.py ingest_caselaw --from-raw-storage
```

One model drafts metadata from the text; a second reads the text and the draft,
corrects it, and a `.verified.json` marker records that the second pass ran.
That marker is what ingestion reads to approve a bundle for search, so a
summarized bundle imports searchable while an unsummarized one does not.

**What `.verified.json` means.** A second model reviewed the first model's work.
Not that a lawyer approved it. Ingestion treats it as fit for *search*, not as
fit to rely on; `approved_for_drafting` remains a separate, human decision.

Fetched bundles differ from the original scans in one way that matters. The
reporter already states the title, citation, deciding court, and decision date.
Those are given to both models as facts to repeat rather than fields to infer,
and are written back afterwards, so a summarizer cannot talk the corpus out of a
date the reporter printed. Only the analytical fields are taken from the models,
and each sidecar records which model drafted, which verified, and where the
authoritative fields came from.

Prompts are file-backed at `prompts/caselaw.metadata_extract.yaml` and
`prompts/caselaw.metadata_verify.yaml`, so the wording and the model defaults are
reviewable and versioned rather than buried in a script.
