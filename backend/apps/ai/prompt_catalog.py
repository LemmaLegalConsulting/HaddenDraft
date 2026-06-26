"""File-backed prompt catalog with optional database overrides."""

from dataclasses import dataclass
from pathlib import Path
from string import Formatter

import yaml
from django.conf import settings


class PromptCatalogError(ValueError):
    """Raised when prompt catalog data is missing or malformed."""


class PromptRenderError(PromptCatalogError):
    """Raised when a prompt cannot be rendered from its supplied context."""


@dataclass(frozen=True)
class Prompt:
    key: str
    system: str
    user: str
    default_model: str
    default_reasoning_level: str
    source: str


def _catalog_paths(directory):
    directory = Path(directory)
    if not directory.exists():
        raise PromptCatalogError(f"Prompt catalog directory does not exist: {directory}")
    return sorted([*directory.glob("*.yaml"), *directory.glob("*.yml")])


def load_file_prompts(directory=None):
    """Load prompt records from every YAML file in the configured catalog directory."""
    directory = directory or settings.PROMPT_CATALOG_DIR
    prompts = {}
    paths = _catalog_paths(directory)
    if not paths:
        raise PromptCatalogError(f"No YAML prompt files found in: {directory}")
    for path in paths:
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise PromptCatalogError(f"Invalid YAML in prompt catalog file {path}: {exc}") from exc
        key = path.stem
        system = document.get("system prompt")
        user = document.get("user prompt")
        prompt_settings = document.get("settings")
        if not isinstance(system, str) or not isinstance(user, str) or not isinstance(prompt_settings, dict):
            raise PromptCatalogError(f"{path} must define string system prompt, user prompt, and settings values")
        default_model = prompt_settings.get("default model")
        default_reasoning_level = prompt_settings.get("default reasoning level")
        if not isinstance(default_model, str) or not isinstance(default_reasoning_level, str):
            raise PromptCatalogError(f"{path} settings must define string default model and default reasoning level")
        if key in prompts:
            raise PromptCatalogError(f"Duplicate prompt key {key!r} in {path}")
        prompts[key] = Prompt(
            key=key,
            system=system,
            user=user,
            default_model=default_model,
            default_reasoning_level=default_reasoning_level,
            source=str(path),
        )
    return prompts


def get_prompt(key, *, allow_database_override=True):
    """Return the enabled database override or the file-backed default for ``key``."""
    if allow_database_override:
        # Imported lazily so file-only catalog tests and non-Django tooling work.
        from apps.ai.models import PromptOverride

        override = PromptOverride.objects.filter(key=key, enabled=True).only(
            "key", "system", "user", "default_model", "default_reasoning_level"
        ).first()
        if override:
            return Prompt(
                key=key,
                system=override.system,
                user=override.user,
                default_model=override.default_model,
                default_reasoning_level=override.default_reasoning_level,
                source="database override",
            )
    try:
        return load_file_prompts()[key]
    except KeyError as exc:
        raise PromptCatalogError(f"Prompt {key!r} was not found in {settings.PROMPT_CATALOG_DIR}") from exc


def _required_fields(template):
    fields = set()
    for _, field_name, _, _ in Formatter().parse(template):
        if field_name:
            # Attribute/index access would make the catalog interface opaque.
            if any(character in field_name for character in ".["):
                raise PromptRenderError(f"Unsupported placeholder {field_name!r}; use a simple named field")
            fields.add(field_name)
    return fields


def render_prompt(key, *, allow_database_override=True, **context):
    """Render a system/user prompt pair using named ``{placeholder}`` fields."""
    prompt = get_prompt(key, allow_database_override=allow_database_override)
    required = _required_fields(prompt.system) | _required_fields(prompt.user)
    missing = sorted(required - context.keys())
    if missing:
        raise PromptRenderError(f"Prompt {key!r} is missing context values: {', '.join(missing)}")
    try:
        return Prompt(
            key=key,
            system=prompt.system.format_map(context),
            user=prompt.user.format_map(context),
            default_model=prompt.default_model,
            default_reasoning_level=prompt.default_reasoning_level,
            source=prompt.source,
        )
    except (KeyError, ValueError) as exc:
        raise PromptRenderError(f"Could not render prompt {key!r}: {exc}") from exc
