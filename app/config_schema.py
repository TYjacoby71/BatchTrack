"""Canonical configuration schema and helpers.

Synopsis:
Defines all supported configuration keys, defaults, and validation helpers.
Loads per-domain schema parts and exposes a single settings surface.

Glossary:
- Schema: Canonical definition of config keys and metadata.
- Field: Single configuration variable definition.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


# --- ConfigField ---
# Purpose: Define the metadata and defaults for one config key.
@dataclass(frozen=True)
class ConfigField:
    key: str
    cast: str
    default: Any
    description: str
    section: str
    required: bool = False
    required_in: tuple[str, ...] = ()
    recommended: str | None = None
    secret: bool = False
    note: str | None = None
    options: tuple[str, ...] = ()
    include_in_docs: bool = True
    include_in_checklist: bool = True
    default_by_env: dict[str, Any] | None = None

    def default_for_env(self, env_name: str) -> Any:
        if self.default_by_env and env_name in self.default_by_env:
            return self.default_by_env[env_name]
        return self.default

    def is_required(self, env_name: str) -> bool:
        return self.required or (self.required_in and env_name in self.required_in)


# --- ConfigSection ---
# Purpose: Group config fields into a named checklist section.
@dataclass(frozen=True)
class ConfigSection:
    key: str
    title: str
    note: str | None
    fields: tuple[ConfigField, ...]


# --- ResolvedField ---
# Purpose: Capture resolved config values with source metadata.
@dataclass(frozen=True)
class ResolvedField:
    field: ConfigField
    value: Any
    source: str
    present: bool
    required: bool


DEPRECATED_ENV_KEYS: dict[str, str] = {
    "WEB_CONCURRENCY": "GUNICORN_WORKERS",
    "WORKERS": "GUNICORN_WORKERS",
    "DATABASE_INTERNAL_URL": "DATABASE_URL",
    "RATELIMIT_STORAGE_URL": "RATELIMIT_STORAGE_URI",
    "CACHE_REDIS_URL": "REDIS_URL",
    "GOOGLE_GENERATIVE_AI_API_KEY": "GOOGLE_AI_API_KEY",
    "ENV": "FLASK_ENV",
    "SECRET_KEY": "FLASK_SECRET_KEY",
    "FLASK_DEBUG": "Use LOG_LEVEL and the production logging config instead.",
}


# --- Parse string ---
# Purpose: Convert raw string values while honoring empty defaults.
def _parse_str(value: str | None, default: Any, *, allow_empty: bool = False) -> Any:
    if value is None:
        return default
    stripped = value.strip()
    if stripped == "" and not allow_empty:
        return default
    return stripped


# --- Parse integer ---
# Purpose: Convert raw string values into integers with fallback messaging.
def _parse_int(value: str | None, default: Any) -> tuple[Any, str | None]:
    if value is None or value.strip() == "":
        return default, None
    try:
        return int(value), None
    except ValueError:
        return default, "expected integer"


# --- Parse float ---
# Purpose: Convert raw string values into floats with fallback messaging.
def _parse_float(value: str | None, default: Any) -> tuple[Any, str | None]:
    if value is None or value.strip() == "":
        return default, None
    try:
        return float(value), None
    except ValueError:
        return default, "expected float"


# --- Parse boolean ---
# Purpose: Convert raw string values into booleans with fallback messaging.
def _parse_bool(value: str | None, default: Any) -> tuple[Any, str | None]:
    if value is None or value.strip() == "":
        return default, None
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True, None
    if lowered in {"0", "false", "no", "off"}:
        return False, None
    return default, "expected boolean"


# --- Parse value ---
# Purpose: Dispatch raw values to the appropriate type parser.
def _parse_value(
    field: ConfigField, raw: str | None, default: Any
) -> tuple[Any, str | None]:
    if field.cast == "int":
        return _parse_int(raw, default)
    if field.cast == "float":
        return _parse_float(raw, default)
    if field.cast == "bool":
        return _parse_bool(raw, default)
    return _parse_str(raw, default), None


# --- Resolve settings ---
# Purpose: Convert raw env values into typed config values and warnings.
def resolve_settings(
    env: Mapping[str, str], env_name: str
) -> tuple[dict[str, Any], dict[str, ResolvedField], list[str]]:
    warnings: list[str] = []
    values: dict[str, Any] = {}
    resolved: dict[str, ResolvedField] = {}

    for field in CONFIG_FIELDS:
        raw = env.get(field.key)
        default = field.default_for_env(env_name)
        value, error = _parse_value(field, raw, default)
        source = "env" if raw not in (None, "") else "default"
        is_required = field.is_required(env_name)
        present = (
            raw not in (None, "")
            if is_required
            else (raw not in (None, "") or value not in (None, ""))
        )
        if error:
            warnings.append(f"{field.key} {error}; falling back to {default!r}.")
        if is_required and raw in (None, ""):
            warnings.append(f"{field.key} is required but missing.")

        values[field.key] = value
        resolved[field.key] = ResolvedField(
            field=field,
            value=value,
            source=source,
            present=present,
            required=is_required,
        )

    for key, replacement in DEPRECATED_ENV_KEYS.items():
        if env.get(key) not in (None, ""):
            warnings.append(f"{key} is deprecated; use {replacement} instead.")

    return values, resolved, warnings


# --- Iterate sections ---
# Purpose: Return the ordered config sections for docs and checklists.
def iter_sections() -> Iterable[ConfigSection]:
    return CONFIG_SECTIONS


# --- Build checklist sections ---
# Purpose: Transform schema fields into the integrations checklist payload.
def build_integration_sections(
    env: Mapping[str, str], env_name: str
) -> list[dict[str, Any]]:
    _, resolved, _ = resolve_settings(env, env_name)
    sections: list[dict[str, Any]] = []
    for section in CONFIG_SECTIONS:
        rows = []
        for field in section.fields:
            if not field.include_in_checklist:
                continue
            resolved_field = resolved[field.key]
            rows.append(
                {
                    "category": section.title,
                    "key": field.key,
                    "present": resolved_field.present,
                    "required": resolved_field.required,
                    "recommended": field.recommended,
                    "default_value": field.default_for_env(env_name),
                    "options": list(field.options),
                    "description": field.description,
                    "note": field.note,
                    "is_secret": field.secret,
                    "source": resolved_field.source,
                    "allow_config": not resolved_field.required,
                }
            )
        sections.append({"title": section.title, "note": section.note, "rows": rows})
    return sections


# --- Field helper ---
# Purpose: Build ConfigField instances with shared defaults.
def _field(
    key: str,
    cast: str,
    default: Any,
    description: str,
    section: str,
    *,
    required: bool = False,
    required_in: tuple[str, ...] = (),
    recommended: str | None = None,
    secret: bool = False,
    note: str | None = None,
    options: tuple[str, ...] | list[str] | None = None,
    include_in_docs: bool = True,
    include_in_checklist: bool = True,
    default_by_env: dict[str, Any] | None = None,
) -> ConfigField:
    return ConfigField(
        key=key,
        cast=cast,
        default=default,
        description=description,
        section=section,
        required=required,
        required_in=required_in,
        recommended=recommended,
        secret=secret,
        note=note,
        options=tuple(options or ()),
        include_in_docs=include_in_docs,
        include_in_checklist=include_in_checklist,
        default_by_env=default_by_env,
    )


# --- Part order ---
# Purpose: Define the ordered list of schema part modules.
_PART_ORDER = (
    "core",
    "database",
    "cache",
    "security",
    "email",
    "billing",
    "features",
    "ai",
    "oauth",
    "load",
    "gunicorn",
    "operations",
)


# --- Load part module ---
# Purpose: Load a schema part module from disk without importing the app package.
def _load_part(module_name: str):
    parts_dir = Path(__file__).with_name("config_schema_parts")
    module_path = parts_dir / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(
        f"config_schema_part_{module_name}", module_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load schema part {module_name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- Build sections ---
# Purpose: Assemble ConfigSection objects from schema part modules.
def _build_sections() -> tuple[ConfigSection, ...]:
    sections: list[ConfigSection] = []
    for module_name in _PART_ORDER:
        module = _load_part(module_name)
        meta = module.SECTION
        fields = tuple(_field(section=meta["key"], **field) for field in module.FIELDS)
        sections.append(
            ConfigSection(
                key=meta["key"],
                title=meta["title"],
                note=meta.get("note"),
                fields=fields,
            )
        )
    return tuple(sections)


CONFIG_SECTIONS: tuple[ConfigSection, ...] = _build_sections()
CONFIG_FIELDS: tuple[ConfigField, ...] = tuple(
    field for section in CONFIG_SECTIONS for field in section.fields
)
