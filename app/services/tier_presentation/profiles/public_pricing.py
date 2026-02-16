"""Public pricing profile for tier presentation.

Synopsis:
Defines which catalog sections and highlight rules are used by the public
pricing page renderer.
"""

from __future__ import annotations

from typing import Any

from ..catalog import FEATURE_COMPARISON_SECTIONS, MARKETING_HIGHLIGHT_RULES, MAX_MARKETING_HIGHLIGHTS


def get_public_pricing_feature_sections() -> tuple[dict[str, Any], ...]:
    """Return section definitions for `/pricing` comparison tables."""
    return FEATURE_COMPARISON_SECTIONS


def get_public_pricing_highlight_rules() -> tuple[dict[str, Any], ...]:
    """Return highlight definitions for public pricing tier cards."""
    return MARKETING_HIGHLIGHT_RULES


def get_public_pricing_max_highlights() -> int:
    """Return per-card highlight cap for the public pricing profile."""
    return MAX_MARKETING_HIGHLIGHTS

