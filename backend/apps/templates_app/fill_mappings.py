"""Reviewed, deterministic LegalServer field mappings. No model dependency."""
import yaml

from apps.core.content_library import content_path
from apps.core.models import OrganizationSettings
from apps.matters.client_letter_context import format_address
from .fill_paths import canonical_path, read_path
from .models import TemplateFieldMapping


def seed_mappings():
    organization = OrganizationSettings.objects.first()
    if organization is None:
        organization, _ = OrganizationSettings.objects.get_or_create(pk=1)
    path = content_path("template-field-maps", "legalserver.yaml")
    data = yaml.safe_load(path.read_text())
    count = 0
    for field, source in data["mappings"].items():
        _, created = TemplateFieldMapping.objects.get_or_create(
            organization=organization, template_slug="", field=canonical_path(field),
            defaults={"source_path": source, "formatter": data.get("formatters", {}).get(field, "display")},
        )
        count += created
    return count


def mapping_index(slug):
    organization = OrganizationSettings.objects.first()
    rows = TemplateFieldMapping.objects.filter(organization=organization, template_slug__in=["", slug])
    result = {}
    for row in sorted(rows, key=lambda r: bool(r.template_slug)):
        result[canonical_path(row.field)] = row
    return result


def mapped_value(mapping, payload, *, collection=False):
    if not mapping.enabled:
        raise ValueError("Mapping disabled by your organization")
    value = read_path(payload, mapping.source_path)
    if value is None or value == "":
        raise ValueError(f"No value at {mapping.source_path}")
    if mapping.formatter == "address":
        if not isinstance(value, dict):
            raise ValueError("Expected an address object")
        value = format_address(value)
    elif mapping.formatter == "display" and isinstance(value, dict):
        for key in ("lookup_value_name", "text_value", "raw_value"):
            if key in value and value[key] not in (None, "", "N/A"):
                value = value[key]
                break
    if isinstance(value, (dict, list)) and not collection:
        raise ValueError("This value is an object or list; map a specific key or use a formatter")
    return value
