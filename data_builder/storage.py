"""File IO helpers for writing golden source JSON."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from .schema import IngredientPayload


def _safe_slug(name: str) -> str:
    return (
        name.lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace(">", "-")
        .replace("&", "and")
    )


def _read_payloads(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, dict) and "ingredients" in data:
        return data["ingredients"]
    if isinstance(data, list):
        return data
    raise ValueError(f"Unsupported JSON structure in {path}")


def _write_payloads(path: Path, payloads: List[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump({"ingredients": payloads}, handle, indent=2, ensure_ascii=False)


def persist_payload(payload: IngredientPayload, output_dir: Path) -> Path:
    primary_tag = payload.ingredient.taxonomies.ingredient_category_tags[0]
    filename = f"{_safe_slug(primary_tag)}.json"
    target = output_dir / filename

    existing = _read_payloads(target)
    filtered = [p for p in existing if p.get("ingredient", {}).get("common_name") != payload.ingredient.common_name]
    filtered.append(payload.model_dump(mode="json"))

    _write_payloads(target, sorted(filtered, key=lambda entry: entry["ingredient"]["common_name"]))
    return target


__all__ = ["persist_payload"]
