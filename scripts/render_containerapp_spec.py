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
RAW_AREA = "raw"
PUBLISHED_AREA = "published"
STORAGE_AREA_SHARES = {
    RAW_AREA: f"{STORAGE_ROOT_MOUNT}/{RAW_AREA}",
    PUBLISHED_AREA: f"{STORAGE_ROOT_MOUNT}/{PUBLISHED_AREA}",
}


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


def storage_for(areas):
    """Volume and mount entries for the media share plus the named areas."""
    volumes = [{"name": "media", "storageType": "AzureFile", "storageName": "media"}]
    mounts = [{"volumeName": "media", "mountPath": MEDIA_MOUNT}]
    for area in sorted(areas):
        volumes.append({"name": area, "storageType": "AzureFile", "storageName": area})
        mounts.append({"volumeName": area, "mountPath": STORAGE_AREA_SHARES[area]})
    return volumes, mounts


def build_common(values: dict[str, str], args) -> tuple[list, list]:
    secrets = [{"name": secret_name(key), "value": value} for key, value in sorted(values.items())]
    env = [{"name": key, "secretRef": secret_name(key)} for key in sorted(values)]
    return secrets, env


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
    parser.add_argument(
        "--min-replicas",
        type=int,
        default=0,
        help=(
            "Replicas to keep running when idle. 0 scales to zero and pays a cold start "
            "on the first request after an idle period; 1 keeps a replica warm, billed at "
            "Azure's reduced idle rate."
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

    secrets, env = build_common(values, args)

    # Every Azure Files share is mounted before the container is allowed to
    # start, and each one costs a measurable few seconds of a cold start. The
    # raw area is the operator's upload staging ground: only the ingestion
    # management commands read it, and those all run in the bootstrap job. So
    # the app mounts what it serves and the job mounts everything.
    #
    # The practical consequence: run ingest_caselaw, fetch_cap_opinions,
    # enrich_caselaw_metadata or publish_private_content in the job, not with
    # `az containerapp exec` into a web replica, where raw/ is not there.
    app_volumes, app_mounts = storage_for([PUBLISHED_AREA])
    job_volumes, job_mounts = storage_for(STORAGE_AREA_SHARES)

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
                        "volumeMounts": app_mounts,
                        # The readiness probe is the last thing standing between
                        # a started replica and the request that woke it up, so
                        # its cadence is a direct component of cold-start
                        # latency. Polling every second against an endpoint that
                        # only Django can answer admits traffic within about a
                        # second of the app being able to serve it; the previous
                        # 5s delay plus 10s period spent up to fifteen seconds
                        # not asking, against an endpoint nginx would have
                        # answered before gunicorn had loaded.
                        "probes": [
                            {
                                "type": "Startup",
                                "httpGet": {"path": "/readyz", "port": 80},
                                "initialDelaySeconds": 1,
                                # Container Apps caps a probe's effective
                                # timeout at its period, whatever timeoutSeconds
                                # says: measured on 2026-08-13, a probe with
                                # periodSeconds 1 and timeoutSeconds 2 logged
                                # "failed with timeout in 1 seconds". So the
                                # period is really "how long one attempt gets",
                                # and polling every second gave Django's first
                                # request one second before cutting it off --
                                # which it lost, five times, on a cold replica.
                                # 3s per attempt, 20 attempts, still a 60s
                                # budget for a genuinely slow start.
                                "periodSeconds": 3,
                                "timeoutSeconds": 3,
                                "failureThreshold": 20,
                            },
                            {
                                "type": "Readiness",
                                "httpGet": {"path": "/readyz", "port": 80},
                                "initialDelaySeconds": 0,
                                "periodSeconds": 2,
                                "timeoutSeconds": 2,
                                "failureThreshold": 6,
                            },
                            {
                                "type": "Liveness",
                                "httpGet": {"path": "/healthz", "port": 80},
                                "initialDelaySeconds": 10,
                                "periodSeconds": 30,
                                "timeoutSeconds": 5,
                                "failureThreshold": 3,
                            },
                        ],
                    }
                ],
                # At 0 the app scales to zero when idle and the first request
                # after an idle period pays a cold start: starting a replica,
                # possibly pulling the image, then loading Django. Everything
                # else here is tuned to make that as short as it can be, but it
                # cannot be made to disappear.
                #
                # At 1 there is no cold start at all. A replica held at the
                # minimum replica count and not serving requests bills at Azure's
                # reduced *idle* rate rather than the active one, so a warm
                # replica costs far less than a busy one -- see --min-replicas.
                "scale": {"minReplicas": args.min_replicas, "maxReplicas": 3},
                "volumes": app_volumes,
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
                        "volumeMounts": job_mounts,
                    }
                ],
                "volumes": job_volumes,
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
