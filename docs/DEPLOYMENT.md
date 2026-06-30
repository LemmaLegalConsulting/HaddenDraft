# Production VM deployment

This guide describes the low-friction deployment path for HaddenDraft on a single disposable Ubuntu VM with durable services kept outside the VM.

The intended architecture is:

```text
Azure Key Vault
  production secrets

Azure Database for PostgreSQL Flexible Server
  durable application database and point-in-time restore

Ubuntu VM
  Docker Engine
  Docker Compose
  HaddenDraft backend container
  HaddenDraft frontend/nginx container
```

The VM should be treated as replaceable. The deployment script can bootstrap a fresh VM, fetch secrets from Key Vault, build containers, run migrations, collect static files, and start the app.

## Prerequisites

1. An Ubuntu 22.04 or 24.04 VM.
2. A DNS name pointing at the VM.
3. TCP 80 open to the VM. Put TLS in front with an Azure load balancer, reverse proxy, or future Caddy/nginx TLS configuration as needed.
4. Docker Engine with the Docker Compose plugin.
5. Azure CLI installed on the VM.
6. An Azure Key Vault that stores production secrets.
7. An Azure PostgreSQL Flexible Server database reachable from the VM.
8. A VM system-assigned managed identity or another Azure login that can read the Key Vault secrets.

The bootstrap script installs common Ubuntu packages and `docker.io` when they are missing. It intentionally does not run remote installer scripts for Docker or Azure CLI. If your Ubuntu image does not include the Docker Compose plugin or Azure CLI, install those once through your standard VM build process, then rerun the script.

## Required Key Vault secrets

The default template expects these Key Vault secret names:

```text
DJANGO-SECRET-KEY
DATABASE-URL
OPENAI-API-KEY
LEGALSERVER-API-TOKEN
SHAREPOINT-ACCESS-TOKEN
OFFICE365-CLIENT-SECRET
```

The PostgreSQL value should use SSL, for example:

```text
postgres://haddendraft:<password>@haddendraft-db.postgres.database.azure.com:5432/haddendraft?sslmode=require
```

If a value is not needed yet, either create an empty secret or remove the placeholder from `deploy/env.production.template`.

## Configure the production template

Edit the non-secret values in `deploy/env.production.template` before deploying. At minimum, update:

```text
DJANGO_ALLOWED_HOSTS
DJANGO_CSRF_TRUSTED_ORIGINS
DJANGO_CORS_ALLOWED_ORIGINS
FRONTEND_SITE_URL
LEGALSERVER_BASE_URL
OFFICE365_REDIRECT_URI
```

Secrets use the `{{KEY-VAULT-SECRET-NAME}}` syntax and are rendered by the deployment script into `/opt/haddendraft/.env`.

## Bootstrap a fresh VM

SSH into the VM and run from a checked-out copy of the repository:

```bash
sudo KEY_VAULT_NAME=haddendraft-prod-kv REPO_REF=main ./deploy/bootstrap-vm.sh
```

During PR testing, replace `main` with the deployment branch:

```bash
sudo KEY_VAULT_NAME=haddendraft-prod-kv REPO_REF=deployment/vm-clean-deploy-z ./deploy/bootstrap-vm.sh
```

The script will:

1. Install base Ubuntu packages and start Docker.
2. Verify that Docker Compose and Azure CLI are available.
3. Clone or update the repository under `/opt/haddendraft`.
4. Render `/opt/haddendraft/.env` from `deploy/env.production.template` and Azure Key Vault.
5. Build the backend and frontend containers.
6. Run Django migrations.
7. Run `collectstatic`.
8. Start the Compose services.

## Redeploy

After the VM has been bootstrapped, redeploy with:

```bash
sudo KEY_VAULT_NAME=haddendraft-prod-kv REPO_REF=main /opt/haddendraft/deploy/bootstrap-vm.sh
```

## Useful operations

Check status:

```bash
sudo docker compose \
  --project-name haddendraft \
  --file /opt/haddendraft/deploy/docker-compose.production.yml \
  ps
```

Follow logs:

```bash
sudo docker compose \
  --project-name haddendraft \
  --file /opt/haddendraft/deploy/docker-compose.production.yml \
  logs -f
```

Run migrations manually:

```bash
sudo docker compose \
  --project-name haddendraft \
  --file /opt/haddendraft/deploy/docker-compose.production.yml \
  run --rm web python backend/manage.py migrate --noinput
```

Create an initial superuser:

```bash
sudo docker compose \
  --project-name haddendraft \
  --file /opt/haddendraft/deploy/docker-compose.production.yml \
  run --rm web python backend/manage.py createsuperuser
```

## VM maintenance

Use Azure Update Manager for scheduled OS patching. A good starting point is a monthly Sunday early-morning maintenance window with reboot allowed.

Before patch windows:

1. Confirm Azure PostgreSQL backups are healthy.
2. Confirm the app build is known.
3. Optionally snapshot the VM disk.

After patch windows:

1. Confirm Docker is running.
2. Run the Compose status command.
3. Open the application and Django admin.

## Recovery model

The VM is disposable if these are true:

1. The production database is Azure PostgreSQL.
2. Production secrets are in Key Vault.
3. Uploaded or generated documents are not stored only on the VM. If local media is used, back it up or migrate it to durable storage.
4. The deployment branch and script can rebuild the app.

To recover from a VM failure, create a new VM, grant it Key Vault access, point DNS at it, and rerun `deploy/bootstrap-vm.sh`.
