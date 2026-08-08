#!/bin/bash
# Single-container entrypoint for the Docker Compose deployment, where one
# container both prepares the database and serves traffic.
#
# Azure Container Apps splits these: docker/bootstrap.sh runs as a job and
# docker/web.sh is the container command. Both deployments therefore run the
# same code for the same step.
set -Eeuo pipefail

/app/docker/bootstrap.sh
exec /app/docker/web.sh
