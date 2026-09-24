#!/usr/bin/env bash
# A local deployment shaped like production, for the browser suite to run against.
#
#   scripts/e2e_production_rig.sh up      # build, bootstrap and serve
#   scripts/e2e_production_rig.sh env     # print the exports the e2e suite needs
#   scripts/e2e_production_rig.sh spa     # rebuild only the static app from the working tree
#   scripts/e2e_production_rig.sh down    # stop and remove everything
#
# E2E_RIG_REF=WORKTREE builds from uncommitted changes instead of HEAD.
#
# What makes it production-shaped, and why each part is here:
#   - The image is built from `git archive HEAD`, as CI builds it, never from the
#     working tree: a local build context also carries git-ignored research
#     directories (F2 in docs/e2e-findings-2026-09-23.md).
#   - docker/bootstrap.sh runs against Postgres exactly as the deploy job does,
#     over a storage root staged as raw/ (caselaw, private content, ordinances).
#   - The API runs docker/web.sh -- nginx in front of gunicorn --preload -- with
#     DJANGO_DEBUG=false, secure cookies, a parent-domain CSRF cookie and CORS.
#   - The app and API are separate HTTPS origins, app.cle.test and api.cle.test,
#     behind Caddy standing in for Static Web Apps and Container Apps ingress.
#     Several production faults exist only across that split.
#
# Secrets (LegalServer, the model provider) are read from .env and never
# printed. LegalServer writes stay off unless E2E_ALLOW_LEGALSERVER_WRITES=1.
set -Eeuo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RIG="${E2E_RIG_DIR:-${TMPDIR:-/tmp}/ahd-e2e-rig}"
PORT="${E2E_RIG_PORT:-8443}"
NET=ahd-e2e
IMAGE=ahd-e2e:local
APP="https://app.cle.test:${PORT}"
API="https://api.cle.test:${PORT}"

stage_storage() {
  mkdir -p "$RIG/storage/raw" "$RIG/storage/published" "$RIG/media"
  if [[ -d "$REPO/private-content/storage/raw/caselaw" ]]; then
    rsync -a "$REPO/private-content/storage/raw/caselaw" "$RIG/storage/raw/"
  fi
  if [[ -d "$REPO/private-content" ]]; then
    # As scripts/deploy_azure_containerapps.sh stages it, less the storage area.
    rsync -a --exclude 'caselaw-artifacts/' --exclude '.git' --exclude 'storage/' \
      "$REPO/private-content/" "$RIG/storage/raw/private-content/"
  fi
  if [[ -d "$REPO/content/ordinances" ]]; then
    mkdir -p "$RIG/storage/raw/content"
    rsync -a "$REPO/content/ordinances" "$RIG/storage/raw/content/"
  fi
}

write_env() {
  umask 077
  {
    grep -E "^(OPENAI_BASE_URL|OPENAI_API_KEY|OPENAI_MODEL|LEGALSERVER_BASE_URL|LEGALSERVER_API_TOKEN|LEGALSERVER_MATTERS_PATH|LEGALSERVER_MATTER_DOCUMENTS_PATH|DEFAULT_JURISDICTION|COURTLISTENER_API_KEY)=" "$REPO/.env" || true
    cat <<EOF
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=$(openssl rand -hex 32)
DJANGO_ALLOWED_HOSTS=api.cle.test
DJANGO_CSRF_TRUSTED_ORIGINS=${APP},${API}
DJANGO_CORS_ALLOWED_ORIGINS=${APP}
DJANGO_CSRF_COOKIE_DOMAIN=.cle.test
DJANGO_CSRF_COOKIE_SECURE=true
DJANGO_SESSION_COOKIE_SECURE=true
DJANGO_TRUST_PROXY_SSL_HEADER=true
DJANGO_SECURE_HSTS_SECONDS=0
FRONTEND_SITE_URL=${APP}
CONTENT_LIBRARY_DIR=/app/content
DOCUMENT_STORAGE_BACKEND=filesystem
DOCUMENT_STORAGE_ROOT=/app/storage
ORGANIZATION_CONTENT_LIBRARY_DIR=/app/storage/published/private-content
PUBLISHED_CONTENT_LIBRARY_DIR=/app/storage/published/content
CASELAW_INGEST_DIR=/app/storage/published/caselaw
POSTGRES_HOST=ahd-pg
POSTGRES_DB=agentic_housing
POSTGRES_USER=agentic_housing
POSTGRES_PASSWORD=e2e-local-only
POSTGRES_SSLMODE=disable
LEGALSERVER_ALLOW_WRITES=$([[ "${E2E_ALLOW_LEGALSERVER_WRITES:-}" == "1" ]] && echo true || echo false)
EOF
  } > "$RIG/api.env"
}

write_caddyfile() {
  cat > "$RIG/Caddyfile" <<'EOF'
{
	local_certs
	skip_install_trust
}
# Static Web Apps: SPA fallback except for assets, headers from staticwebapp.config.json.
app.cle.test {
	tls internal
	root * /srv
	header X-Content-Type-Options nosniff
	header X-Frame-Options DENY
	header Referrer-Policy strict-origin-when-cross-origin
	@static path /assets/* *.png *.jpg *.jpeg *.svg *.ico *.webp *.woff *.woff2 *.txt *.json
	handle @static {
		file_server
	}
	handle {
		try_files {path} /index.html
		file_server
	}
}
# Container Apps ingress: TLS terminated here, X-Forwarded-Proto passed on.
api.cle.test {
	tls internal
	reverse_proxy ahd-api:80
}
EOF
}

build_spa() {
  (cd "$REPO/frontend" && VITE_API_BASE="${API}/api" npx vite build --outDir "$RIG/dist" --emptyOutDir >/dev/null)
  cp "$REPO/frontend/staticwebapp.config.json" "$RIG/dist/"
  docker rm -f ahd-edge >/dev/null 2>&1 || true
  docker run -d --name ahd-edge --network "$NET" -p "127.0.0.1:${PORT}:443" \
    -v "$RIG/Caddyfile:/etc/caddy/Caddyfile:ro" -v "$RIG/dist:/srv:ro" caddy:2 >/dev/null
}

start_api() {
  docker rm -f ahd-api >/dev/null 2>&1 || true
  docker run -d --name ahd-api --network "$NET" --env-file "$RIG/api.env" \
    -v "$RIG/storage:/app/storage" -v "$RIG/media:/app/media" "$IMAGE" >/dev/null
}

create_user() {
  local password
  password="$(openssl rand -hex 16)"
  printf 'E2E_PASSWORD=%s\n' "$password" > "$RIG/e2e.secret"
  chmod 600 "$RIG/e2e.secret"
  docker exec -e PW="$password" ahd-api sh -c 'cd /app/backend && python manage.py shell -c "
import os
from django.contrib.auth import get_user_model
user, _ = get_user_model().objects.get_or_create(username=\"e2e-browser\", defaults={\"email\": \"e2e-browser@example.invalid\"})
user.set_password(os.environ[\"PW\"]); user.is_staff = True; user.is_superuser = True; user.save()
"' >/dev/null
}

up() {
  command -v docker >/dev/null || { echo "docker is required" >&2; exit 1; }
  [[ -f "$REPO/.env" ]] || { echo "Missing .env" >&2; exit 1; }
  mkdir -p "$RIG" && rm -f "$RIG/bootstrap.log"
  # E2E_RIG_REF=WORKTREE builds the working tree as it stands -- uncommitted
  # changes and new files included, git-ignored files excluded, as a commit of
  # it would be -- to check a fix before committing it.
  local ref="${E2E_RIG_REF:-HEAD}"
  echo "==> Building the image from ${ref} (as CI does)"
  rm -rf "$RIG/src" && mkdir -p "$RIG/src"
  if [[ "$ref" == "WORKTREE" ]]; then
    (cd "$REPO" && git ls-files -z --cached --others --exclude-standard | grep -zv "^private-content$" | tar -cf - --null --ignore-failed-read -T -) \
      | tar -x -C "$RIG/src"
  else
    git -C "$REPO" archive "$ref" | tar -x -C "$RIG/src"
  fi
  docker build -q -t "$IMAGE" "$RIG/src" >/dev/null || { echo "Image build failed; rerun: docker build $RIG/src" >&2; exit 1; }
  echo "==> Staging storage and configuration"
  stage_storage
  write_env
  write_caddyfile
  docker network create "$NET" >/dev/null 2>&1 || true
  echo "==> Starting Postgres"
  docker rm -f ahd-edge ahd-api ahd-pg >/dev/null 2>&1 || true
  docker rm -f ahd-pg >/dev/null 2>&1 || true
  docker run -d --name ahd-pg --network "$NET" -e POSTGRES_DB=agentic_housing \
    -e POSTGRES_USER=agentic_housing -e POSTGRES_PASSWORD=e2e-local-only postgres:16 >/dev/null
  until docker exec ahd-pg pg_isready -U agentic_housing -q; do sleep 1; done
  echo "==> Running docker/bootstrap.sh (log: $RIG/bootstrap.log)"
  docker run --rm --network "$NET" --env-file "$RIG/api.env" -v "$RIG/storage:/app/storage" \
    -v "$RIG/media:/app/media" "$IMAGE" /app/docker/bootstrap.sh > "$RIG/bootstrap.log" 2>&1 \
    || { echo "Bootstrap failed; see $RIG/bootstrap.log" >&2; exit 1; }
  echo "==> Starting the API and the edge"
  start_api
  build_spa
  until [[ "$(curl -sk --resolve "api.cle.test:${PORT}:127.0.0.1" -o /dev/null -w '%{http_code}' "${API}/readyz")" == 200 ]]; do sleep 1; done
  create_user
  echo "==> Ready: ${APP}  (API ${API})"
  echo "    eval \"\$(scripts/e2e_production_rig.sh env)\" && npm --prefix frontend run test:e2e"
}

env_exports() {
  cat <<EOF
export \$(cat "$RIG/e2e.secret")
export E2E_BASE_URL=${APP}
export E2E_API_BASE=${API}/api
export E2E_IGNORE_HTTPS_ERRORS=1
export E2E_HOST_RESOLVER_RULES="MAP *.cle.test 127.0.0.1"
export NODE_OPTIONS="--require $REPO/frontend/e2e/support/dns-map.cjs"
export E2E_USERNAME=e2e-browser
export E2E_LEGALSERVER_IDENTIFIER=\${E2E_LEGALSERVER_IDENTIFIER:?set E2E_LEGALSERVER_IDENTIFIER to the test user LegalServer login}
EOF
}

down() {
  docker rm -f ahd-edge ahd-api ahd-pg >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
  echo "Stopped. Work files remain in $RIG"
}

case "${1:-}" in
  up) up ;;
  env) env_exports ;;
  spa) build_spa ;;
  api) start_api ;;
  down) down ;;
  *) sed -n '2,8p' "$0"; exit 1 ;;
esac
