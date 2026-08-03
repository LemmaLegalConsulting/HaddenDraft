"""Indexing letterheads that ship in the content library.

Cleveland Legal Aid's stationery is organization-private, so it belongs under
`ORGANIZATION_CONTENT_LIBRARY_DIR`. A neutral placeholder ships in the public
`content/` tree so a fresh checkout can still draft and export a letter without
anyone's branding.

Private entries win over public ones with the same slug, which is the same
precedence the prepared-template index uses.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml
from django.db import transaction
from django.utils import timezone

from apps.core.content_library import content_library_roots
from apps.templates_app.content_library import TemplateManifestError, resolve_content_asset
from apps.templates_app.models import Letterhead


LETTERHEAD_DIR = "letterheads"
PLACEHOLDER_SLUG = "example-legal-aid"


def iter_letterhead_manifests():
    seen = set()
    for provider_root in content_library_roots():
        root = provider_root / LETTERHEAD_DIR
        if not root.exists():
            continue
        for path in sorted(root.glob("*/manifest.yaml")):
            if path.parent.name in seen:
                continue
            seen.add(path.parent.name)
            yield path


def load_letterhead_manifest(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    data = yaml.safe_load(raw) or {}
    missing = sorted({"schema_version", "slug", "title", "docx"} - set(data))
    if missing:
        raise TemplateManifestError(f"{path}: missing {', '.join(missing)}")
    if data["schema_version"] != 1:
        raise TemplateManifestError(f"{path}: unsupported schema_version {data['schema_version']}")
    docx_path = (path.parent / data["docx"]).resolve()
    if not docx_path.is_file():
        raise TemplateManifestError(f"{path}: docx does not exist: {data['docx']}")
    return data, hashlib.sha256(raw).hexdigest()


@transaction.atomic
def sync_letterheads():
    """Index letterhead packages without clobbering admin-uploaded records."""
    results = []
    for path in iter_letterhead_manifests():
        manifest, checksum = load_letterhead_manifest(path)
        slug = manifest["slug"]
        existing = Letterhead.objects.filter(slug=slug).first()
        if existing and existing.source_kind != "content_library":
            results.append({"slug": slug, "status": "conflict"})
            continue

        relative_docx = (path.parent / manifest["docx"]).resolve()
        for root in content_library_roots():
            try:
                logical = relative_docx.relative_to(root.resolve()).as_posix()
                break
            except ValueError:
                continue
        else:
            raise TemplateManifestError(f"{path}: docx is outside the content providers")

        defaults = {
            "title": manifest["title"],
            "description": manifest.get("description", ""),
            "organization": manifest.get("organization", ""),
            "content_path": logical,
            "source_kind": "content_library",
            "is_default": bool(manifest.get("default", False)),
            "is_active": bool(manifest.get("active", True)),
            "is_placeholder": bool(manifest.get("placeholder", False)),
            "variables": manifest.get("variables", []),
            "source_checksum": checksum,
            "last_synced_at": timezone.now(),
        }
        if existing and existing.source_checksum == checksum:
            results.append({"slug": slug, "status": "unchanged"})
            continue
        if existing:
            for field, value in defaults.items():
                setattr(existing, field, value)
            existing.save()
            results.append({"slug": slug, "status": "updated"})
        else:
            Letterhead.objects.create(slug=slug, **defaults)
            results.append({"slug": slug, "status": "created"})

    _ensure_single_default()
    return results


def _ensure_single_default():
    defaults = Letterhead.objects.filter(is_default=True, is_active=True).order_by(
        "is_placeholder", "id"
    )
    keeper = defaults.first()
    if keeper:
        Letterhead.objects.filter(is_default=True).exclude(pk=keeper.pk).update(is_default=False)
        return
    # A real letterhead outranks the shipped placeholder when nothing is marked.
    fallback = Letterhead.objects.filter(is_active=True).order_by("is_placeholder", "id").first()
    if fallback:
        Letterhead.objects.filter(pk=fallback.pk).update(is_default=True)


def letterhead_path(letterhead):
    """Where the renderable DOCX lives, admin upload taking precedence."""
    if not letterhead:
        return None
    if letterhead.docx:
        return Path(letterhead.docx.path)
    if letterhead.content_path:
        path = resolve_content_asset(letterhead.content_path)
        if path.is_file():
            return path
    return None


def default_letterhead():
    return (
        Letterhead.objects.filter(is_active=True, is_default=True).first()
        or Letterhead.objects.filter(is_active=True).order_by("is_placeholder", "id").first()
    )


def letterhead_for_author(author_profile):
    """Pick the letterhead for an author, preferring one matching their office."""
    office = (author_profile or {}).get("officeName", "").strip().casefold()
    if office:
        for candidate in Letterhead.objects.filter(is_active=True):
            haystack = f"{candidate.title} {candidate.organization} {candidate.slug}".casefold()
            if office and office in haystack:
                return candidate
    return default_letterhead()
