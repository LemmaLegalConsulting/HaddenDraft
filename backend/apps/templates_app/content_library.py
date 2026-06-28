from __future__ import annotations

import hashlib
from pathlib import Path

import yaml
from django.db import transaction
from django.utils import timezone

from apps.core.content_library import content_library_dir
from apps.templates_app.models import DocumentTemplate, TemplateBlock


PREPARED_TEMPLATE_DIR = "document-templates"


class TemplateManifestError(ValueError):
    pass


def logical_content_path(path: Path) -> str:
    root = content_library_dir().resolve()
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError as exc:
        raise TemplateManifestError(f"Template asset is outside CONTENT_LIBRARY_DIR: {path}") from exc


def resolve_content_asset(logical_path: str) -> Path:
    root = content_library_dir().resolve()
    candidate = (root / logical_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise TemplateManifestError(f"Content path escapes CONTENT_LIBRARY_DIR: {logical_path}") from exc
    return candidate


def _checksum_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_manifest(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    data = yaml.safe_load(raw) or {}
    required = {"schema_version", "slug", "title", "kind", "render", "blocks"}
    missing = sorted(required - set(data))
    if missing:
        raise TemplateManifestError(f"{path}: missing {', '.join(missing)}")
    if data["schema_version"] != 1:
        raise TemplateManifestError(f"{path}: unsupported schema_version {data['schema_version']}")
    if not isinstance(data["blocks"], list) or not data["blocks"]:
        raise TemplateManifestError(f"{path}: blocks must be a non-empty list")
    keys = [row.get("key") for row in data["blocks"]]
    if any(not key for key in keys) or len(keys) != len(set(keys)):
        raise TemplateManifestError(f"{path}: block keys must be present and unique")
    render_path = data["render"].get("docx")
    if not render_path or not (path.parent / render_path).is_file():
        raise TemplateManifestError(f"{path}: render.docx does not exist")
    return data, _checksum_bytes(raw)


def iter_manifests():
    root = content_library_dir() / PREPARED_TEMPLATE_DIR
    if not root.exists():
        return
    yield from sorted(root.glob("*/manifest.yaml"))


def _template_metadata(manifest: dict) -> dict:
    return {
        "schemaVersion": manifest["schema_version"],
        "render": manifest.get("render", {}),
        "fields": manifest.get("fields", []),
        "source": manifest.get("source", {}),
    }


@transaction.atomic
def sync_prepared_templates(*, deactivate_missing=True):
    """Index prepared packages without overwriting database/admin templates."""
    results = []
    seen = set()
    for path in iter_manifests() or []:
        manifest, checksum = load_manifest(path)
        slug = manifest["slug"]
        seen.add(slug)
        existing = DocumentTemplate.objects.filter(slug=slug).first()
        if existing and existing.source_kind != "content_library":
            results.append({"slug": slug, "status": "conflict", "template": existing})
            continue
        manifest_block_keys = {row["key"] for row in manifest["blocks"]}
        if (
            existing
            and existing.source_checksum == checksum
            and existing.is_active == bool(manifest.get("active", True))
            and set(existing.blocks.values_list("key", flat=True)) == manifest_block_keys
        ):
            results.append({"slug": slug, "status": "unchanged", "template": existing})
            continue

        defaults = {
            "title": manifest["title"],
            "kind": manifest["kind"],
            "description": manifest.get("description", ""),
            "jurisdiction": manifest.get("jurisdiction", ""),
            "source_label": manifest.get("source_label", "Content library"),
            "metadata": _template_metadata(manifest),
            "source_kind": "content_library",
            "content_path": logical_content_path(path),
            "source_checksum": checksum,
            "is_active": bool(manifest.get("active", True)),
            "last_synced_at": timezone.now(),
        }
        if existing:
            for field, value in defaults.items():
                setattr(existing, field, value)
            existing.save(update_fields=[*defaults.keys(), "updated_at"])
            template = existing
            status = "updated"
        else:
            template = DocumentTemplate.objects.create(slug=slug, **defaults)
            status = "created"

        block_keys = set()
        for row in manifest["blocks"]:
            block_keys.add(row["key"])
            block_defaults = {
                "label": row.get("label") or row["key"].replace("-", " ").title(),
                "block_type": row.get("type", "optional_clause"),
                "order": int(row.get("order", 0)),
                "body": row.get("body", ""),
                "required": bool(row.get("required", True)),
                "ai_fill_mode": row.get("ai_fill_mode", "none"),
                "selection_rule": row.get("selection_rule", {}),
                "supporting_sources": row.get("supporting_sources", []),
                "content_path": row.get("docx", ""),
                "source_checksum": row.get("sha256", ""),
                "input_schema": {key: value for key, value in (row.get("input") or {}).items() if value is not None},
                "lexical_config": {key: value for key, value in (row.get("lexical") or {}).items() if value is not None},
                "editable": bool(row.get("editable", True)),
            }
            TemplateBlock.objects.update_or_create(template=template, key=row["key"], defaults=block_defaults)
        template.blocks.exclude(key__in=block_keys).delete()
        results.append({"slug": slug, "status": status, "template": template})

    if deactivate_missing:
        DocumentTemplate.objects.filter(source_kind="content_library").exclude(slug__in=seen).update(is_active=False)
    return results


def full_template_path(template):
    if not template or template.source_kind != "content_library" or not template.content_path:
        return None
    manifest_path = resolve_content_asset(template.content_path)
    manifest, _checksum = load_manifest(manifest_path)
    path = (manifest_path.parent / manifest["render"]["docx"]).resolve()
    resolve_content_asset(logical_content_path(path))
    return path
