#!/bin/bash
# One-shot deployment work: schema migrations and content ingestion.
#
# This must run exactly once per deployment, not once per replica, so it runs as
# a Container Apps job that completes before the new revision takes traffic --
# never as part of starting a replica. Every command here is idempotent, so a
# retried job or a re-run against an already-current database is safe.
set -Eeuo pipefail

cd /app/backend

echo "==> Applying database migrations"
python manage.py migrate --noinput

# Private organization content is side-loaded, so it has to be published out of
# the raw storage area before anything reads the content library. A no-op when
# the raw area is empty.
echo "==> Publishing private organization content"
python manage.py publish_private_content

echo "==> Ingesting document templates"
python manage.py ingest_document_templates

echo "==> Syncing content library"
python manage.py sync_content_library --update-triage-rubrics

# Prepare and index the modular advice-letter catalog, including the Lexical
# formatting converted from the maintained source DOCX files.
echo "==> Ingesting advice letters"
python manage.py ingest_advice_letters

# Case law arrives two ways. Sidecar bundles uploaded to raw/caselaw/ are
# ingested and their derived artifacts written to published/caselaw/. A corpus
# that is already published is re-indexed from a local directory instead.
#
# Both are idempotent: ingest_group skips any decision whose source_sha256 is
# already recorded, so re-running costs a scan and changes nothing.
if [ "${CASELAW_INGEST_FROM_RAW_STORAGE:-true}" = "true" ]; then
  echo "==> Ingesting caselaw from raw storage area"
  python manage.py ingest_caselaw --from-raw-storage
fi

CASELAW_DIR="${CASELAW_INGEST_DIR:-}"
if [ -n "$CASELAW_DIR" ] && [ -d "$CASELAW_DIR" ]; then
  echo "==> Ingesting caselaw artifacts from $CASELAW_DIR"
  python manage.py ingest_caselaw "$CASELAW_DIR"
fi

# CASELAW_INGEST_DIR points at the original corpus bundle, which still holds
# every citation-only stub CAP has since supplied a full opinion for. That
# directory reappears on every deploy, so a stub removed once would just be
# re-imported by the step above next time -- this has to run after caselaw
# ingestion on every bootstrap, not once as a migration.
echo "==> Retiring citation stubs that now have a full opinion"
python manage.py retire_stub_decisions

# Dates were dropped on import for as long as as_date() was a stub, and
# re-ingestion does not fix them: ingest_group skips a decision whose
# source_sha256 is already recorded, so an existing corpus keeps its empty date
# columns. This reads the metadata sidecar each decision already points at and
# fills only what is missing, recording where every date came from. It leaves a
# date that is already set alone, so it is a no-op once the corpus is dated.
echo "==> Backfilling decision dates and their provenance"
python manage.py backfill_decision_dates

echo "==> Bootstrap complete"
