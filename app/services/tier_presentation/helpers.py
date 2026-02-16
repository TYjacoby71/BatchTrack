"""Tier presentation helper utilities.

Synopsis:
Normalize and coerce values used by tier feature presentation services.

Glossary:
- Normalized token: Lowercased trimmed identifier used for set checks.
- Feature label key: Simplified label string used for de-duplication.
"""

from __future__ import annotations

from typing import Any


def coerce_int(value: Any) -> int | None:
    """Return integer representation when possible."""
    if value in (None, "", "null"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_token_set(values) -> set[str]:
    """Normalize iterable string-like values for membership checks."""
    if not values:
        return set()
    normalized: set[str] = set()
    for value in values:
        token = str(value or "").strip().lower()
        if token:
            normalized.add(token)
    return normalized


def normalize_feature_label(value: str | None) -> str:
    """Normalize a display label for stable matching."""
    cleaned = " ".join(str(value or "").replace(".", " ").replace("_", " ").split())
    return cleaned.strip().lower()

