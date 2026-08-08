#!/usr/bin/env python3
"""Render the Container Apps YAML for the web app and the bootstrap job.

Both specs run the same image with the same configuration and the same mounted
shares; they differ only in what they execute and how they scale. Generating
them from one place keeps them from drifting apart, which is the usual way a
migration job ends up running against different settings than the app it is
preparing the database for.

Every value from the env file is stored as a Container Apps secret rather than a
plain environment variable, so connection strings and API tokens do not show up
in `az containerapp show` output or in the portal's revision view.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Left behind by the nginx-proxy / acme-companion setup on the VM. Container
# Apps ingress issues certificates itself, so carrying these forward would only
# confuse the next person reading the configuration.
DROPPED_KEYS = {"VIRTUAL_HOST", "LETSENCRYPT_HOST", "ENV"}

MEDIA_MOUNT = "/app/media"

# The document store's two areas are mounted as separate shares under one root,
# so DOCUMENT_STORAGE_ROOT=/app/storage sees raw/ and published/ as ordinary
# directories. Separate shares rather than subdirectories of one: it keeps the
# operator-writable area and the application-served area independently sized and
# independently permissionable, and it let the existing corpus move by
# server-side copy instead of a re-upload.
STORAGE_ROOT_MOUNT = "/app/storage"
STORAGE_AREA_SHARES = {"raw": f"{STORAGE_ROOT_MOUNT}/raw", "published": f"{STORAGE_ROOT_MOUNT}/published"}


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in DROPPED_KEYS:
            continue
        values[key] = value.strip().strip("\"'")
    return values


def secret_name(key: str) -> str:
    """Container Apps secret names allow lowercase alphanumerics and dashes."""
    name = re.sub(r"[^a-z0-9-]", "-", key.lower().replace("_", "-"))
    return re.sub(r"-+", "-", name).strip("-")


def build_common(values: dict[str, str], args) -> tuple[list, list, list, list]:
    secrets = [{"name": secret_name(key), "value": value} for key, value in sorted(values.items())]
    env = [{"name": key, "secretRef": secret_name(key)} for key in sorted(values)]
    volumes = [{"name": "media", "storageType": "AzureFile", "storageName": "media"}]
    mounts = [{"volumeName": "media", "mountPath": MEDIA_MOUNT}]
    for area, mount_path in sorted(STORAGE_AREA_SHARES.items()):
        volumes.append({"name": area, "storageType": "AzureFile", "storageName": area})
        mounts.append({"volumeName": area, "mountPath": mount_path})
    return secrets, env, volumes, mounts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--image", required=True)
    parser.add_argument("--location", required=True)
    parser.add_argument("--environment-id", required=True)
    parser.add_argument("--identity-id", required=True)
    parser.add_argument("--registry-server", required=True)
    parser.add_argument("--postgres-host", required=True)
    parser.add_argument(
        "--custom-domains-json",
        default="",
        help=(
            "The live app's ingress.customDomains, as JSON. Carried through so a deploy "
            "does not strip a bound hostname and its certificate."
        ),
    )
    parser.add_argument("--app-output", required=True, type=Path)
    parser.add_argument("--job-output", required=True, type=Path)
    args = parser.parse_args()

    values = parse_env_file(args.env_file)

    # The server FQDN is a deployment fact, not something the operator should
    # have to keep in sync by hand in the env file.
    values["POSTGRES_HOST"] = args.postgres_host

    missing = [key for key in ("POSTGRES_USER", "POSTGRES_PASSWORD", "DJANGO_SECRET_KEY") if not values.get(key)]
    if missing:
        print(f"Missing required settings in {args.env_file}: {', '.join(missing)}", file=sys.stderr)
        return 1

    secrets, env, volumes, mounts = build_common(values, args)
    identity = {"type": "UserAssigned", "userAssignedIdentities": {args.identity_id: {}}}
    registries = [{"server": args.registry_server, "identity": args.identity_id}]

    # A full-spec update replaces the ingress block, so a bound custom domain has
    # to be echoed back or the deploy silently unbinds the hostname and its
    # managed certificate — the site would keep answering on its default FQDN and
    # start failing on the real one.
    ingress = {
        "external": True,
        "targetPort": 80,
        "transport": "auto",
        "allowInsecure": False,
        "traffic": [{"latestRevision": True, "weight": 100}],
    }
    if args.custom_domains_json.strip():
        custom_domains = json.loads(args.custom_domains_json)
        if custom_domains:
            ingress["customDomains"] = custom_domains

    app_spec = {
        "location": args.location,
        "identity": identity,
        "properties": {
            "environmentId": args.environment_id,
            "workloadProfileName": "Consumption",
            "configuration": {
                "activeRevisionsMode": "Single",
                "ingress": ingress,
                "registries": registries,
                "secrets": secrets,
            },
            "template": {
                "containers": [
                    {
                        "name": "app",
                        "image": args.image,
                        "command": ["/app/docker/web.sh"],
                        "resources": {"cpu": 1.0, "memory": "2.0Gi"},
                        "env": env,
                        "volumeMounts": mounts,
                        "probes": [
                            {
                                "type": "Liveness",
                                "httpGet": {"path": "/healthz", "port": 80},
                                "initialDelaySeconds": 20,
                                "periodSeconds": 30,
                                "failureThreshold": 3,
                            },
                            {
                                "type": "Readiness",
                                "httpGet": {"path": "/healthz", "port": 80},
                                "initialDelaySeconds": 5,
                                "periodSeconds": 10,
                                "failureThreshold": 6,
                            },
                        ],
                    }
                ],
                # Scale to zero when idle. The first request after an idle
                # period pays a cold start — pulling the image, then Django
                # startup — so expect it to take seconds rather than
                # milliseconds. That is the deliberate trade for not paying for
                # an always-warm replica.
                "scale": {"minReplicas": 0, "maxReplicas": 3},
                "volumes": volumes,
            },
        },
    }

    job_spec = {
        "location": args.location,
        "identity": identity,
        "properties": {
            "environmentId": args.environment_id,
            "workloadProfileName": "Consumption",
            "configuration": {
                "triggerType": "Manual",
                "replicaTimeout": 1800,
                "replicaRetryLimit": 1,
                "manualTriggerConfig": {"parallelism": 1, "replicaCompletionCount": 1},
                "registries": registries,
                "secrets": secrets,
            },
            "template": {
                "containers": [
                    {
                        "name": "bootstrap",
                        "image": args.image,
                        "command": ["/app/docker/bootstrap.sh"],
                        "resources": {"cpu": 1.0, "memory": "2.0Gi"},
                        "env": env,
                        "volumeMounts": mounts,
                    }
                ],
                "volumes": volumes,
            },
        },
    }

    # `az containerapp ... --yaml` accepts JSON, which avoids depending on PyYAML
    # being installed on whatever machine runs the deploy.
    args.app_output.write_text(json.dumps(app_spec, indent=2))
    args.job_output.write_text(json.dumps(job_spec, indent=2))
    print(f"Rendered {args.app_output} and {args.job_output} ({len(secrets)} secrets)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
