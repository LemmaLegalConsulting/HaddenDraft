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


def _review_defaults(row) -> dict:
    """Decide whether a section needs an attorney's eye, and say why.

    Everything is loaded regardless, because the practical way to review this
    corpus is to read it in place. The flag is what separates checked text from
    unchecked, not whether the row exists.
    """
    status = row.get("status", "ready")
    copyedit = row.get("copyedit") or {}
    flags = copyedit.get("flags") or []

    reasons = []
    if status == "ai_drafted":
        reasons.append("drafted here, not maintained")
    if status == "stub":
        reasons.append("too short to send, or retired")
    source = row.get("source") or {}
    if source.get("tracked_changes"):
        reasons.append(f"{source['tracked_changes']} tracked change(s) accepted here")
    if source.get("comments"):
        reasons.append(f"{source['comments']} reviewer comment(s) dropped")
    merge_flags = [flag for flag in flags if flag.get("kind") == "merge_boundary"]
    if merge_flags:
        reasons.append(f"{len(merge_flags)} passage(s) sat on a merge boundary")

    return {
        "copyedit": copyedit,
        "needs_attorney_review": bool(reasons),
        "review_reason": "; ".join(reasons)[:255],
    }


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
            defaults.update(_review_defaults(row))

            existing = AdviceLetterSection.objects.filter(slug=slug).first()
            if existing and existing.source_kind != "content_library":
                results.append({"slug": slug, "status": "conflict"})
                continue
            if existing and existing.is_locally_edited:
                # Someone edited this in admin. Refresh provenance, but leave
                # their text and their review decision alone -- re-ingesting
                # must not silently undo an attorney's read.
                for field in ("content_path", "source_checksum", "last_synced_at", "order"):
                    setattr(existing, field, defaults[field])
                existing.save(
                    update_fields=["content_path", "source_checksum", "last_synced_at", "order", "updated_at"]
                )
                results.append({"slug": slug, "status": "preserved"})
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


def selectable_sections(*, region="", letter_type="brief_advice", reviewed_only=False):
    """Sections the picker may offer.

    Everything active is offered. Withholding unreviewed sections meant the most
    relevant one for a case -- the 3-day-notice defect -- was silently missing
    because its file still had tracked changes. An advocate is better served by
    seeing it with a warning than by not seeing it.
    """
    query = AdviceLetterSection.objects.filter(
        is_active=True, role="body", letter_type=letter_type
    ).exclude(status="stub")
    if reviewed_only:
        query = query.filter(needs_attorney_review=False)
    if region:
        query = query.filter(region__in=["", region.upper()])
    return query


def sections_awaiting_review():
    return AdviceLetterSection.objects.filter(is_active=True, needs_attorney_review=True)


def wrapper_sections():
    return {
        section.role: section
        for section in AdviceLetterSection.objects.filter(
            is_active=True, role__in=["intro", "closing"]
        )
    }
