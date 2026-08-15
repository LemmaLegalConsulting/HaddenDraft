#!/usr/bin/env bash
# Build the single-page app and publish it to Azure Static Web Apps.
#
# Why the app is hosted separately from the API at all: the API scales to zero,
# and waking it takes on the order of twenty seconds. When nginx inside that
# same container is what serves index.html, nobody sees anything at all for
# those twenty seconds. Served from a static host that is always warm, the page
# paints immediately and the wait becomes a visible, explained one while the
# first API call wakes the container -- see frontend/src/api/wakeNotice.js.
#
# The API URL is baked in at build time, so this must be re-run when it changes.
set -Eeuo pipefail

SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:-4f62b1f4-b38c-44f3-9c3f-aedaf2d12d2a}"
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-agentic-housing-rg}"
STATIC_APP="${AZURE_STATIC_APP:-agentic-housing-web}"

# The API's own hostname. This must be a sibling subdomain of the hostname the
# app itself is served from: a cookie is same-site across subdomains of one
# registrable domain, so the session survives on an ordinary SameSite=Lax
# cookie. On an unrelated hostname the session becomes a third-party cookie and
# Safari and Firefox drop it, which looks exactly like login silently failing.
API_BASE="${VITE_API_BASE:-https://api.cle-draft.lemmalegal.com/api}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

for command in az npm npx; do
  command -v "$command" >/dev/null || { echo "Missing required command: $command" >&2; exit 1; }
done

az account set --subscription "$SUBSCRIPTION_ID"
ACTIVE="$(az account show --query id -o tsv)"
[[ "$ACTIVE" == "$SUBSCRIPTION_ID" ]] || {
  echo "Refusing deployment: active subscription is $ACTIVE, expected $SUBSCRIPTION_ID" >&2
  exit 1
}

echo "==> Building the frontend against $API_BASE"
(cd frontend && npm ci --silent && VITE_API_BASE="$API_BASE" npm run build)

# staticwebapp.config.json has to sit in the uploaded directory, not beside the
# sources, or Static Web Apps never reads it and every deep link 404s instead of
# falling back to index.html.
cp frontend/staticwebapp.config.json frontend/dist/

echo "==> Publishing to $STATIC_APP"
TOKEN="$(az staticwebapp secrets list -g "$RESOURCE_GROUP" -n "$STATIC_APP" \
  --query properties.apiKey -o tsv)"
npx --yes @azure/static-web-apps-cli@latest deploy frontend/dist \
  --deployment-token "$TOKEN" --env production

HOST="$(az staticwebapp show -g "$RESOURCE_GROUP" -n "$STATIC_APP" \
  --query defaultHostname -o tsv)"
echo
echo "Published: https://$HOST"
echo "Calling API at: $API_BASE"
