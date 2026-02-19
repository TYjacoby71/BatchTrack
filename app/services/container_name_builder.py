from __future__ import annotations

import string
from decimal import Decimal, InvalidOperation
from typing import Optional

__all__ = ["build_container_name"]


def build_container_name(
    *,
    style: Optional[str] = None,
    material: Optional[str] = None,
    container_type: Optional[str] = None,
    color: Optional[str] = None,
    capacity: Optional[float | str] = None,
    capacity_unit: Optional[str] = None,
    fallback: str = "Custom Container",
) -> str:
    """Construct a canonical container name from structured attributes."""
    descriptor = _assemble_descriptor(
        color=color,
        style=style,
        material=material,
        container_type=container_type,
    )

    capacity_value = _format_capacity(capacity)
    capacity_segment = ""
    if capacity_value:
        unit = (capacity_unit or "").strip()
        capacity_segment = f"{capacity_value} {unit}".strip()

    if descriptor and capacity_segment:
        return f"{descriptor} - {capacity_segment}"
    if descriptor:
        return descriptor
    if capacity_segment:
        return f"{fallback} - {capacity_segment}" if fallback else capacity_segment
    return fallback


def _assemble_descriptor(
    *,
    color: Optional[str],
    style: Optional[str],
    material: Optional[str],
    container_type: Optional[str],
) -> str:
    """Order descriptor parts so similar containers group together."""
    ordered_values: list[str] = []

    for value in (color, style, material, container_type or "Container"):
        cleaned = _clean(value)
        if not cleaned:
            continue
        lower_existing = " ".join(ordered_values).lower()
        if cleaned.lower() in lower_existing:
            continue
        ordered_values.append(_title_case(cleaned))

    return " ".join(ordered_values).strip()


def _clean(value: Optional[str]) -> str:
    return (
        value.strip()
        if isinstance(value, str)
        else (str(value).strip() if value is not None else "")
    )


def _title_case(value: str) -> str:
    return string.capwords(value)


def _format_capacity(value: Optional[float | str]) -> str:
    if value in (None, "", "null"):
        return ""
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return ""
    if parsed <= 0:
        return ""

    normalized = parsed.normalize()
    text = format(normalized, "f").rstrip("0").rstrip(".")
    return text or format(normalized, "f")
