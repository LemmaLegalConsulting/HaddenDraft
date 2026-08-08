#!/usr/bin/env bash
# Copy the legacy VM's PostgreSQL database into the managed Flexible Server.
#
# Run this once to seed the new database, and again immediately before the DNS
# cutover: the VM keeps serving until DNS moves, so anything written after the
# first copy would otherwise be lost.
#
# The dump and restore both run on the VM. That is deliberate — the managed
# server has no public endpoint, and the VM is the one machine already inside
# the VNet that can reach it.
#
# This DESTROYS the current contents of the target database (the dump is taken
# with --clean --if-exists). It refuses to run without --confirm.
set -Eeuo pipefail

# COMPLETE. The VM this copied from was deleted on 2026-08-07, after the final
# copy verified matching row counts on both sides. Kept as the record of how the
# data moved; it cannot run, because there is no longer a source host.
if [[ "${ALLOW_LEGACY_VM_MIGRATION:-false}" != "true" ]]; then
  cat >&2 <<'COMPLETE'
scripts/migrate_vm_database.sh has already completed and will not run.

The source VM was deleted on 2026-08-07. This script is retained only to document
how the database was copied into the managed server.

Note what it would do if a source existed: it DROPs schema public on the target
before restoring. Against the live database that is destructive.
COMPLETE
  exit 1
fi

RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-agentic-housing-rg}"
SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:-4f62b1f4-b38c-44f3-9c3f-aedaf2d12d2a}"
POSTGRES_SERVER="${AZURE_POSTGRES_SERVER:-agentic-housing-db}"
TARGET_DB="${TARGET_DB:-agentic_housing}"
TARGET_USER="${TARGET_USER:-ahadmin}"
VM_HOST="${VM_HOST:-20.118.35.106}"
VM_USER="${VM_USER:-azureuser}"
SSH_KEY="${AZURE_SSH_KEY:-$HOME/.ssh/agentic_housing_aidraftingtool}"
SOURCE_DB="${SOURCE_DB:-agentic_housing}"
SOURCE_USER="${SOURCE_USER:-agentic_housing}"

if [[ "${1:-}" != "--confirm" ]]; then
  cat >&2 <<USAGE
Usage: TARGET_PASSWORD=... $0 --confirm

Replaces the contents of "$TARGET_DB" on $POSTGRES_SERVER with a fresh dump of
the VM database at $VM_HOST. Existing rows in the target are dropped.
USAGE
  exit 2
fi

: "${TARGET_PASSWORD:?Set TARGET_PASSWORD to the Flexible Server admin password}"
[[ -f "$SSH_KEY" ]] || { echo "Missing SSH private key: $SSH_KEY" >&2; exit 1; }

SSH_OPTIONS=(-i "$SSH_KEY" -o IdentitiesOnly=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)

PGHOST="$(az postgres flexible-server show --subscription "$SUBSCRIPTION_ID" \
  -g "$RESOURCE_GROUP" -n "$POSTGRES_SERVER" --query fullyQualifiedDomainName -o tsv)"
echo "Target: $PGHOST/$TARGET_DB"

# The credential travels over the ssh channel into a root-owned 0600 file rather
# than a command line, so it never shows up in the VM's process list.
printf '%s:5432:%s:%s:%s\n' "$PGHOST" "$TARGET_DB" "$TARGET_USER" "$TARGET_PASSWORD" | \
  ssh "${SSH_OPTIONS[@]}" "$VM_USER@$VM_HOST" \
    'sudo tee /root/ah_pgpass >/dev/null && sudo chmod 600 /root/ah_pgpass && sudo chown root:root /root/ah_pgpass'

echo "Dumping VM database..."
# Deliberately not --clean. Its generated DROP statements fail on this schema:
# dropping templates_app_documenttemplate's primary key is refused while
# drafting_draftdocument's foreign key still depends on the index. Recreating the
# schema wholesale below is both simpler and more thorough.
ssh "${SSH_OPTIONS[@]}" "$VM_USER@$VM_HOST" "bash -s -- '$SOURCE_USER' '$SOURCE_DB'" <<'REMOTE'
set -Eeuo pipefail
SOURCE_USER="$1"
SOURCE_DB="$2"
cd "$HOME/app"
sudo docker compose --env-file .env.azure exec -T db \
  pg_dump -U "$SOURCE_USER" -d "$SOURCE_DB" --no-owner --no-privileges \
  > /tmp/ah_dump.sql
ls -lh /tmp/ah_dump.sql
REMOTE

echo "Restoring into the managed server (replacing schema public)..."
ssh "${SSH_OPTIONS[@]}" "$VM_USER@$VM_HOST" "bash -s -- '$PGHOST' '$TARGET_DB' '$TARGET_USER'" <<'REMOTE'
set -Eeuo pipefail
PGHOST="$1"
TARGET_DB="$2"
TARGET_USER="$3"
CONN="host=$PGHOST port=5432 dbname=$TARGET_DB user=$TARGET_USER sslmode=require"

sudo docker run --rm --network host \
  -e PGPASSFILE=/pgpass -v /root/ah_pgpass:/pgpass:ro \
  postgres:16-alpine \
  psql "$CONN" -v ON_ERROR_STOP=1 -q -c "
    DROP SCHEMA IF EXISTS public CASCADE;
    CREATE SCHEMA public;
    GRANT ALL ON SCHEMA public TO \"$TARGET_USER\";
    GRANT ALL ON SCHEMA public TO public;"

sudo docker run --rm --network host \
  -e PGPASSFILE=/pgpass \
  -v /root/ah_pgpass:/pgpass:ro \
  -v /tmp/ah_dump.sql:/dump.sql:ro \
  postgres:16-alpine \
  psql "$CONN" -v ON_ERROR_STOP=1 -q -f /dump.sql
REMOTE

echo "Comparing row counts..."
COUNT_SQL="select (select count(*) from information_schema.tables where table_schema='public') as tables, (select count(*) from django_migrations) as migrations, (select count(*) from auth_user) as users;"

SOURCE_COUNTS="$(ssh "${SSH_OPTIONS[@]}" "$VM_USER@$VM_HOST" \
  "cd ~/app && sudo docker compose --env-file .env.azure exec -T db psql -U '$SOURCE_USER' -d '$SOURCE_DB' -t -A -c \"$COUNT_SQL\"")"
TARGET_COUNTS="$(ssh "${SSH_OPTIONS[@]}" "$VM_USER@$VM_HOST" \
  "sudo docker run --rm --network host -e PGPASSFILE=/pgpass -v /root/ah_pgpass:/pgpass:ro postgres:16-alpine \
   psql \"host=$PGHOST port=5432 dbname=$TARGET_DB user=$TARGET_USER sslmode=require\" -t -A -c \"$COUNT_SQL\"")"

echo "  source: $SOURCE_COUNTS"
echo "  target: $TARGET_COUNTS"

# Leave nothing sensitive behind on a VM that is about to be decommissioned.
ssh "${SSH_OPTIONS[@]}" "$VM_USER@$VM_HOST" 'sudo shred -u /root/ah_pgpass 2>/dev/null || sudo rm -f /root/ah_pgpass; rm -f /tmp/ah_dump.sql'

[[ "$SOURCE_COUNTS" == "$TARGET_COUNTS" ]] || { echo "Row counts differ." >&2; exit 1; }
echo "Database migration complete."
