#!/usr/bin/env bash
# Serve the built SPA through the production nginx.conf and check that every
# kind of application URL reaches the app while the server's own paths do not.
#
# A route that 404s at the edge only shows up when someone pastes a link or
# presses reload -- never while clicking around -- so it is checked here, with
# the real config, rather than trusted to the SPA fallback.
#
#   npm --prefix frontend run build
#   scripts/check_spa_routes.sh
#
# Needs Docker. Django is deliberately not running: /api/, /admin/ and /readyz
# must be *proxied* (and so fail with 502 here), never answered with the SPA.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${SPA_CHECK_PORT:-18080}"
IMAGE="${SPA_CHECK_IMAGE:-nginx:1.27-alpine}"
NAME="spa-route-check-$$"

if [[ ! -f "$ROOT/frontend/dist/index.html" ]]; then
  echo "frontend/dist is missing; run: npm --prefix frontend run build" >&2
  exit 2
fi

docker run -d --rm --name "$NAME" -p "127.0.0.1:$PORT:80" \
  -v "$ROOT/nginx.conf:/etc/nginx/conf.d/default.conf:ro" \
  -v "$ROOT/frontend/dist:/app/frontend/dist:ro" \
  "$IMAGE" >/dev/null
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true' EXIT

for _ in $(seq 1 50); do
  curl -fs "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1 && break
  sleep 0.2
done

failures=0
check() {
  local path="$1" want_status="$2" want_spa="$3"
  local body status
  body="$(mktemp)"
  status="$(curl -s -o "$body" -w '%{http_code}' "http://127.0.0.1:$PORT$path")"
  local is_spa=no
  grep -q '<div id="root">' "$body" && is_spa=yes
  if [[ "$status" != "$want_status" || "$is_spa" != "$want_spa" ]]; then
    echo "FAIL $path: status $status (want $want_status), SPA $is_spa (want $want_spa)"
    failures=$((failures + 1))
  else
    if [[ "$want_spa" == yes ]]; then echo "ok   $path -> $status (SPA)"; else echo "ok   $path -> $status"; fi
  fi
  rm -f "$body"
}

# Every route family, including the deepest shapes, reaches the app.
for path in \
  / /cases /cases/26-0222 \
  /drafting/26-0222 /drafting/26-0222/new /drafting/26-0222/sessions/184 \
  /drafting/26-0222/sessions/184/plan /drafting/26-0222/sessions/184/jobs/7 \
  /drafting/26-0222/sessions/184/drafts/391/history \
  /template-fill/26-0222/sessions/73/preview /template-fill/26-0222/sessions/73/jobs/91 \
  /advice-letters/26-0222/drafts/118/history \
  /triage/26-0222/assessments/52 /chat/26-0222/threads/42 \
  /research/search /research/chats/4 /research/decisions/9 \
  /research/library/ohio-landlord-tenant/chunks/c-12.3 \
  /argument-gym/workspaces/5/runs/17 \
  "/drafting/MANUAL-3-abc123def456/sessions/1/plan" "/cases/26%200222"; do
  check "$path" 200 yes
done

# The server's own paths are proxied to Django, never answered by the SPA.
check /api/cases/ 502 no
check /api/cases/by-route-key/?key=26-0222 502 no
check /admin/ 502 no
check /readyz 502 no
check /healthz 200 no

if (( failures )); then
  echo "$failures route check(s) failed" >&2
  exit 1
fi
echo "All route checks passed."
