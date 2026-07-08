#!/usr/bin/env bash
set -Eeuo pipefail

SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:-4f62b1f4-b38c-44f3-9c3f-aedaf2d12d2a}"
EXPECTED_USER="${AZURE_EXPECTED_USER:-quinten@nonprofittechy.com}"
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-agentic-housing-rg}"
LOCATION="${AZURE_LOCATION:-centralus}"
VM_NAME="${AZURE_VM_NAME:-AIDraftingTool}"
VM_SIZE="${AZURE_VM_SIZE:-Standard_D2als_v7}"
ADMIN_USER="${AZURE_ADMIN_USER:-azureuser}"
STORAGE_ACCOUNT="${AZURE_STORAGE_ACCOUNT:-agentichousing1782661910}"
STORAGE_ACCOUNT="${STORAGE_ACCOUNT:0:24}"
CONTAINER_NAME="${AZURE_STORAGE_CONTAINER:-content}"
SSH_KEY="${AZURE_SSH_KEY:-$HOME/.ssh/agentic_housing_aidraftingtool}"
ARTIFACT_TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ARTIFACT_NAME="content-${ARTIFACT_TIMESTAMP}.zip"
ARTIFACT_FILE="$(mktemp --suffix=.zip)"
SSH_OPTIONS=(-i "$SSH_KEY" -o IdentitiesOnly=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)

cleanup() {
  rm -f "$ARTIFACT_FILE"
}
trap cleanup EXIT

for command in az ssh rsync zip openssl curl; do
  command -v "$command" >/dev/null || { echo "Missing required command: $command" >&2; exit 1; }
done
[[ -f "$SSH_KEY" ]] || { echo "Missing SSH private key: $SSH_KEY" >&2; exit 1; }

az account set --subscription "$SUBSCRIPTION_ID"
ACTIVE_USER="$(az account show --query user.name -o tsv)"
ACTIVE_SUBSCRIPTION="$(az account show --query id -o tsv)"
if [[ "${ACTIVE_USER,,}" != "${EXPECTED_USER,,}" || "$ACTIVE_SUBSCRIPTION" != "$SUBSCRIPTION_ID" ]]; then
  echo "Refusing deployment: active Azure context is $ACTIVE_USER / $ACTIVE_SUBSCRIPTION" >&2
  echo "Expected $EXPECTED_USER / $SUBSCRIPTION_ID" >&2
  exit 1
fi
echo "Azure context verified: $ACTIVE_USER / $ACTIVE_SUBSCRIPTION"

echo "Creating or updating resource group $RESOURCE_GROUP in $LOCATION..."
az group create --subscription "$SUBSCRIPTION_ID" --name "$RESOURCE_GROUP" --location "$LOCATION" -o none

if ! az storage account show --subscription "$SUBSCRIPTION_ID" --resource-group "$RESOURCE_GROUP" --name "$STORAGE_ACCOUNT" -o none 2>/dev/null; then
  echo "Creating Standard_LRS storage account $STORAGE_ACCOUNT..."
  az storage account create --subscription "$SUBSCRIPTION_ID" --resource-group "$RESOURCE_GROUP" \
    --name "$STORAGE_ACCOUNT" --location "$LOCATION" --sku Standard_LRS \
    --allow-blob-public-access false -o none
fi
CONNECTION_STRING="$(az storage account show-connection-string --subscription "$SUBSCRIPTION_ID" \
  --resource-group "$RESOURCE_GROUP" --name "$STORAGE_ACCOUNT" --query connectionString -o tsv)"
az storage container create --name "$CONTAINER_NAME" --connection-string "$CONNECTION_STRING" -o none

echo "Packaging content library..."
rm -f "$ARTIFACT_FILE"
(cd content && zip -qr "$ARTIFACT_FILE" .)
echo "Uploading $ARTIFACT_NAME and content-latest.zip..."
for blob_name in "$ARTIFACT_NAME" content-latest.zip; do
  az storage blob upload --container-name "$CONTAINER_NAME" --name "$blob_name" \
    --file "$ARTIFACT_FILE" --connection-string "$CONNECTION_STRING" --overwrite true -o none
done

if ! az vm show --subscription "$SUBSCRIPTION_ID" --resource-group "$RESOURCE_GROUP" --name "$VM_NAME" -o none 2>/dev/null; then
  echo "Creating $VM_SIZE VM $VM_NAME..."
  az vm create --subscription "$SUBSCRIPTION_ID" --resource-group "$RESOURCE_GROUP" --name "$VM_NAME" \
    --location "$LOCATION" --image Ubuntu2404 --size "$VM_SIZE" --admin-username "$ADMIN_USER" \
    --ssh-key-values "${SSH_KEY}.pub" --public-ip-sku Standard --custom-data cloud-init.yml -o none
fi
az vm open-port --subscription "$SUBSCRIPTION_ID" --resource-group "$RESOURCE_GROUP" \
  --name "$VM_NAME" --port 80 --priority 1001 -o none

IP_ADDRESS="$(az vm show --subscription "$SUBSCRIPTION_ID" --resource-group "$RESOURCE_GROUP" \
  --name "$VM_NAME" --show-details --query publicIps -o tsv)"
[[ -n "$IP_ADDRESS" ]] || { echo "VM has no public IP address" >&2; exit 1; }

echo "Waiting for SSH and cloud-init at $IP_ADDRESS..."
until ssh "${SSH_OPTIONS[@]}" "$ADMIN_USER@$IP_ADDRESS" true 2>/dev/null; do sleep 5; done
ssh "${SSH_OPTIONS[@]}" "$ADMIN_USER@$IP_ADDRESS" "cloud-init status --wait"

SAS_EXPIRY="$(date -u -d '2 hours' '+%Y-%m-%dT%H:%MZ')"
SAS_TOKEN="$(az storage blob generate-sas --account-name "$STORAGE_ACCOUNT" --container-name "$CONTAINER_NAME" \
  --name "$ARTIFACT_NAME" --permissions r --expiry "$SAS_EXPIRY" --connection-string "$CONNECTION_STRING" -o tsv)"
BLOB_URL="https://${STORAGE_ACCOUNT}.blob.core.windows.net/${CONTAINER_NAME}/${ARTIFACT_NAME}?${SAS_TOKEN}"

echo "Syncing application code..."
ssh "${SSH_OPTIONS[@]}" "$ADMIN_USER@$IP_ADDRESS" "mkdir -p ~/app"
rsync -az --delete \
  --exclude '.git/' --exclude '.venv/' --exclude '.env*' --exclude 'content/' \
  --exclude 'node_modules/' --exclude 'frontend/dist/' --exclude 'backend/db.sqlite3' \
  -e "ssh ${SSH_OPTIONS[*]}" ./ "$ADMIN_USER@$IP_ADDRESS:~/app/"

echo "Configuring production environment and deploying Compose services..."
ssh "${SSH_OPTIONS[@]}" "$ADMIN_USER@$IP_ADDRESS" bash -s -- "$IP_ADDRESS" "$BLOB_URL" <<'REMOTE'
set -Eeuo pipefail
cd "$HOME/app"
IP_ADDRESS="$1"
BLOB_URL="$2"
if [[ ! -f .env.azure ]]; then
  umask 077
  cat > .env.azure <<ENV
POSTGRES_DB=agentic_housing
POSTGRES_USER=agentic_housing
POSTGRES_PASSWORD=$(openssl rand -hex 32)
POSTGRES_HOST=db
POSTGRES_PORT=5432
DJANGO_SECRET_KEY=$(openssl rand -hex 48)
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=$IP_ADDRESS
FRONTEND_SITE_URL=http://$IP_ADDRESS
DJANGO_SESSION_COOKIE_SECURE=false
DJANGO_CSRF_COOKIE_SECURE=false
DJANGO_SECURE_HSTS_SECONDS=0
CONTENT_LIBRARY_DIR=/app/content
AI_DRAFTING_ENABLED=false
ENV
fi
rm -rf content
python3 scripts/sideload_content.py --url "$BLOB_URL" --target content/
sudo docker compose --env-file .env.azure build app
sudo docker compose --env-file .env.azure up -d --remove-orphans
sudo docker image prune -f
REMOTE

echo "Waiting for application response..."
for attempt in {1..30}; do
  if curl --fail --silent --show-error "http://$IP_ADDRESS/" >/dev/null; then
    echo "Deployment complete: http://$IP_ADDRESS"
    echo "Blob artifact: $CONTAINER_NAME/$ARTIFACT_NAME"
    exit 0
  fi
  sleep 4
done
echo "Deployment started, but http://$IP_ADDRESS did not become healthy in time." >&2
ssh "${SSH_OPTIONS[@]}" "$ADMIN_USER@$IP_ADDRESS" "cd ~/app && sudo docker compose --env-file .env.azure ps && sudo docker compose --env-file .env.azure logs --tail=100" >&2
exit 1
