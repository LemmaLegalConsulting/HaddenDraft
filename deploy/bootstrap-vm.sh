#!/usr/bin/env bash
set -euo pipefail

APP_NAME=${APP_NAME:-haddendraft}
APP_USER=${APP_USER:-haddendraft}
APP_DIR=${APP_DIR:-/opt/haddendraft}
REPO_URL=${REPO_URL:-https://github.com/LemmaLegalConsulting/HaddenDraft.git}
REPO_REF=${REPO_REF:-main}
KEY_VAULT_NAME=${KEY_VAULT_NAME:-}
ENV_TEMPLATE=${ENV_TEMPLATE:-deploy/env.production.template}
COMPOSE_FILE=${COMPOSE_FILE:-deploy/docker-compose.production.yml}
RUN_MIGRATIONS=${RUN_MIGRATIONS:-true}
COLLECT_STATIC=${COLLECT_STATIC:-true}
INSTALL_PACKAGES=${INSTALL_PACKAGES:-true}

log() { printf '\n[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { echo "ERROR: $*" >&2; exit 1; }
require_command() { command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"; }

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<EOF
Bootstrap or redeploy HaddenDraft on an Ubuntu VM.

Required environment:
  KEY_VAULT_NAME              Azure Key Vault name containing production secrets.

Optional environment:
  APP_DIR=/opt/haddendraft
  APP_USER=haddendraft
  REPO_URL=https://github.com/LemmaLegalConsulting/HaddenDraft.git
  REPO_REF=main
  ENV_TEMPLATE=deploy/env.production.template
  COMPOSE_FILE=deploy/docker-compose.production.yml
  RUN_MIGRATIONS=true
  COLLECT_STATIC=true
  INSTALL_PACKAGES=true
EOF
  exit 0
fi

[[ -n "$KEY_VAULT_NAME" ]] || die "Set KEY_VAULT_NAME before running this script."
[[ "$EUID" -eq 0 ]] || die "Run as root or with sudo."

install_base_packages() {
  if [[ "$INSTALL_PACKAGES" != "true" ]]; then
    return
  fi

  log "Installing Ubuntu packages"
  apt-get update
  apt-get install -y --no-install-recommends ca-certificates curl git python3 unzip docker.io
  systemctl enable --now docker

  if ! docker compose version >/dev/null 2>&1; then
    die "Docker is installed, but the Docker Compose plugin is missing. Install docker-compose-plugin, then rerun this script."
  fi

  if ! command -v az >/dev/null 2>&1; then
    die "Azure CLI is required so the VM can read Key Vault. Install az, login with the VM managed identity, then rerun this script."
  fi
}

ensure_app_user() {
  if ! id "$APP_USER" >/dev/null 2>&1; then
    log "Creating $APP_USER user"
    useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"
  fi
  usermod -aG docker "$APP_USER" || true
}

sync_repo() {
  log "Syncing repository into $APP_DIR"
  mkdir -p "$APP_DIR"
  if [[ -d "$APP_DIR/.git" ]]; then
    git -C "$APP_DIR" fetch --prune origin
    git -C "$APP_DIR" checkout "$REPO_REF"
    git -C "$APP_DIR" pull --ff-only origin "$REPO_REF" || true
  else
    git clone "$REPO_URL" "$APP_DIR"
    git -C "$APP_DIR" checkout "$REPO_REF"
  fi
  chown -R "$APP_USER:$APP_USER" "$APP_DIR"
}

render_env_from_key_vault() {
  require_command az
  local template_path="$APP_DIR/$ENV_TEMPLATE"
  local env_file="$APP_DIR/.env"

  [[ -f "$template_path" ]] || die "Missing env template: $template_path"

  log "Rendering $env_file from $template_path and Key Vault $KEY_VAULT_NAME"
  umask 077
  python3 - "$template_path" "$env_file" "$KEY_VAULT_NAME" <<'PY'
import os
import re
import subprocess
import sys
from pathlib import Path

template_path = Path(sys.argv[1])
env_file = Path(sys.argv[2])
vault_name = sys.argv[3]
pattern = re.compile(r"\{\{([A-Za-z0-9_.-]+)\}\}")
cache = {}

def get_secret(name: str) -> str:
    if name not in cache:
        cache[name] = subprocess.check_output([
            "az", "keyvault", "secret", "show",
            "--vault-name", vault_name,
            "--name", name,
            "--query", "value",
            "-o", "tsv",
        ], text=True).rstrip("\n")
    return cache[name]

rendered = pattern.sub(lambda match: get_secret(match.group(1)), template_path.read_text())
env_file.write_text(rendered)
os.chmod(env_file, 0o600)
PY
  chown "$APP_USER:$APP_USER" "$env_file"
}

compose() {
  docker compose --project-name "$APP_NAME" --file "$APP_DIR/$COMPOSE_FILE" "$@"
}

deploy_app() {
  log "Building containers"
  compose build

  if [[ "$RUN_MIGRATIONS" == "true" ]]; then
    log "Running Django migrations"
    compose run --rm web python backend/manage.py migrate --noinput
  fi

  if [[ "$COLLECT_STATIC" == "true" ]]; then
    log "Collecting Django static files"
    compose run --rm web python backend/manage.py collectstatic --noinput
  fi

  log "Starting services"
  compose up -d --remove-orphans
  compose ps
}

write_maintenance_notes() {
  mkdir -p /etc/motd.d
  cat > /etc/motd.d/haddendraft <<EOF || true
HaddenDraft VM
--------------
Application: $APP_DIR
Deploy: sudo KEY_VAULT_NAME=$KEY_VAULT_NAME $APP_DIR/deploy/bootstrap-vm.sh
Logs: docker compose --project-name $APP_NAME --file $APP_DIR/$COMPOSE_FILE logs -f
Status: docker compose --project-name $APP_NAME --file $APP_DIR/$COMPOSE_FILE ps
EOF
}

install_base_packages
ensure_app_user
sync_repo
render_env_from_key_vault
deploy_app
write_maintenance_notes
log "Deployment complete"
