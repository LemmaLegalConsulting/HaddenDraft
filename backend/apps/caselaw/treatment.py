"""The controlled vocabulary for case-law treatment status, read from content/.

See content/caselaw-vocabulary/treatment-status.yaml for what the groups mean
and why dispositions are not folded into negative treatment.
"""

from __future__ import annotations

import re

import yaml

from apps.core.content_library import content_path

VOCABULARY_PATH = ("caselaw-vocabulary", "treatment-status.yaml")
_CACHE = {}


def _normalize(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def _vocabulary():
    path = content_path(*VOCABULARY_PATH)
    try:
        stat = path.stat()
        fingerprint = (stat.st_mtime_ns, stat.st_size)
    except OSError:
        fingerprint = None
    if "value" in _CACHE and _CACHE.get("fingerprint") == fingerprint:
        return _CACHE["value"]
    groups = {}
    if fingerprint is not None:
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            payload = {}
        for key, group in (payload.get("groups") or {}).items():
            label = str((group or {}).get("label") or key)
            names = [label, key, *((group or {}).get("aliases") or [])]
            groups[str(key)] = {"label": label, "names": {_normalize(name) for name in names}}
    by_name = {name: key for key, group in groups.items() for name in group["names"]}
    value = {"groups": groups, "by_name": by_name}
    _CACHE.update(fingerprint=fingerprint, value=value)
    return value


def treatment_group(value):
    """The group key for a stored value or a group's own label, else ""."""
    return _vocabulary()["by_name"].get(_normalize(value), "")


def treatment_label(group_key):
    group = _vocabulary()["groups"].get(group_key)
    return group["label"] if group else ""
