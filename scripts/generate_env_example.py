"""Generate the production env example from config schema.

Synopsis:
Renders docs/operations/env.production.example from the canonical config schema.

Glossary:
- Schema: Canonical list of config fields and defaults.
- Example: Generated .env template for operations.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


# --- Load schema ---
# Purpose: Dynamically load the config schema module from disk.
def _load_schema():
    schema_path = Path(__file__).resolve().parents[1] / "app" / "config_schema.py"
    spec = importlib.util.spec_from_file_location("config_schema", schema_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load config schema module.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# --- Format value ---
# Purpose: Format values for .env output.
def _format_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


# --- Example value ---
# Purpose: Pick example values from recommended or default settings.
def _example_value(field, env_name: str, *, use_recommended: bool) -> str:
    if use_recommended and field.recommended is not None:
        return field.recommended
    default = field.default_for_env(env_name)
    if field.secret and (default is None or default == ""):
        return f"your-{field.key.lower()}"
    return _format_value(default)


# --- Generate env example ---
# Purpose: Render an env template for the chosen environment.
def generate_env_example(env_name: str = "production", *, use_recommended: bool = True) -> str:
    header = "Production" if env_name == "production" else "Development"
    lines = [
        f"# {header} Environment Configuration Template",
        "#",
        "# Synopsis: Generated from app/config_schema.py",
        "# Glossary: Schema = canonical config keys, Example = env template",
        "",
    ]

    schema = _load_schema()
    for section in schema.iter_sections():
        fields = [field for field in section.fields if field.include_in_docs]
        if not fields:
            continue
        lines.append(f"# === {section.title.upper()} ===")
        if section.note:
            lines.append(f"# {section.note}")
        for field in fields:
            required = field.is_required(env_name)
            value = _example_value(field, env_name, use_recommended=use_recommended)
            prefix = "" if required else "# "
            lines.append(f"{prefix}{field.key}={value}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# --- Main ---
# Purpose: Write generated env templates to disk.
def main() -> None:
    production_target = Path("docs/operations/env.production.example")
    production_target.write_text(
        generate_env_example("production", use_recommended=True),
        encoding="utf-8",
    )

    dev_target = Path(".env.example")
    dev_target.write_text(
        generate_env_example("development", use_recommended=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
