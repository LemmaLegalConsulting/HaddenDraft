"""Indexing the prepared advice-letter catalog into the database.

Follows the same provider precedence as prepared templates: an organization's
private catalog wins over the public placeholder with the same slug.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml
from django.db import transaction
from django.utils import timezone

from apps.core.content_library import content_library_roots
from apps.templates_app.content_library import TemplateManifestError
from apps.templates_app.models import AdviceLetterSection


ADVICE_LETTER_DIR = "advice-letters"
CATALOG_FILENAME = "catalog.yaml"


def iter_catalogs():
    seen = set()
    for provider_root in content_library_roots():
        path = provider_root / ADVICE_LETTER_DIR / CATALOG_FILENAME
        if not path.is_file():
            continue
        data = yaml.safe_load(path.read_text()) or {}
        slug = data.get("slug") or path.parent.name
        if slug in seen:
            continue
        seen.add(slug)
        yield path, data


def load_catalog(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    data = yaml.safe_load(raw) or {}
    missing = sorted({"schema_version", "sections"} - set(data))
    if missing:
        raise TemplateManifestError(f"{path}: missing {', '.join(missing)}")
    if data["schema_version"] != 1:
        raise TemplateManifestError(f"{path}: unsupported schema_version {data['schema_version']}")
    if not isinstance(data["sections"], list):
        raise TemplateManifestError(f"{path}: sections must be a list")
    slugs = [row.get("slug") for row in data["sections"]]
    if any(not slug for slug in slugs) or len(slugs) != len(set(slugs)):
        raise TemplateManifestError(f"{path}: section slugs must be present and unique")
    return data, hashlib.sha256(raw).hexdigest()


@transaction.atomic
def sync_advice_letters(*, deactivate_missing=True):
    """Index prepared advice-letter catalogs without discarding admin edits."""
    results = []
    seen = set()
    found_catalog = False

    for path, _preview in iter_catalogs():
        found_catalog = True
        data, checksum = load_catalog(path)
        for order, row in enumerate(data["sections"], start=1):
            slug = row["slug"]
            seen.add(slug)
            hints = {
                key: row.get(key)
                for key in ("triggers", "requires", "excludes", "summary", "usually_paired")
                if row.get(key) is not None
            }
            defaults = {
                "title": row.get("title") or slug.replace("-", " ").title(),
                "role": row.get("role", "body"),
                "topic": row.get("topic", ""),
                "letter_type": row.get("letter_type", "brief_advice"),
                "region": row.get("region", ""),
                "cleveland_specific": bool(row.get("cleveland_specific", False)),
                "status": row.get("status", "ready"),
                "body": row.get("body", ""),
                "content_path": f"{ADVICE_LETTER_DIR}/{row.get('docx', '')}" if row.get("docx") else "",
                "order": order * 10,
                "fields": row.get("fields", []),
                "slots": row.get("slots", []),
                "variants": row.get("variants", []),
                "selection_hints": hints,
                "readability": row.get("readability", {}),
                "notes": row.get("notes", []),
                "word_count": int(row.get("word_count", 0)),
                "source_kind": "content_library",
                "source_checksum": checksum,
                "is_active": True,
                "last_synced_at": timezone.now(),
            }
            existing = AdviceLetterSection.objects.filter(slug=slug).first()
            if existing and existing.source_kind != "content_library":
                results.append({"slug": slug, "status": "conflict"})
                continue
            if existing:
                for field, value in defaults.items():
                    setattr(existing, field, value)
                existing.save()
                results.append({"slug": slug, "status": "updated"})
            else:
                AdviceLetterSection.objects.create(slug=slug, **defaults)
                results.append({"slug": slug, "status": "created"})

    if found_catalog and deactivate_missing:
        AdviceLetterSection.objects.filter(
            source_kind="content_library", is_active=True
        ).exclude(slug__in=seen).update(is_active=False)
    return results


def sendable_sections(*, region="", letter_type="brief_advice"):
    """Sections an advocate can send without a review warning."""
    query = AdviceLetterSection.objects.filter(
        is_active=True, status="ready", role="body", letter_type=letter_type
    )
    if region:
        query = query.filter(region__in=["", region.upper()])
    return query


def wrapper_sections():
    return {
        section.role: section
        for section in AdviceLetterSection.objects.filter(
            is_active=True, role__in=["intro", "closing"]
        )
    }
