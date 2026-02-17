"""Public pricing profile for tier presentation.

Synopsis:
Defines which catalog sections and highlight rules are used by the public
pricing page renderer.

Glossary:
- Public pricing profile: Default rule selection for `/pricing` displays.
"""

from __future__ import annotations

from typing import Any

from ..catalog import (
    FEATURE_COMPARISON_SECTIONS,
    MARKETING_HIGHLIGHT_RULES,
    MAX_MARKETING_HIGHLIGHTS,
)


# --- Get public pricing feature sections ---
# Purpose: Provide comparison-table section definitions for the pricing page.
# Inputs: None.
# Outputs: Tuple of section dictionaries consumed by tier presentation core.
def get_public_pricing_feature_sections() -> tuple[dict[str, Any], ...]:
    """Return section definitions for `/pricing` comparison tables."""
    return FEATURE_COMPARISON_SECTIONS


# --- Get public pricing highlight rules ---
# Purpose: Provide tier-card highlight rule definitions for pricing cards.
# Inputs: None.
# Outputs: Tuple of highlight rule dictionaries for core evaluation.
def get_public_pricing_highlight_rules() -> tuple[dict[str, Any], ...]:
    """Return highlight definitions for public pricing tier cards."""
    return MARKETING_HIGHLIGHT_RULES


# --- Get public pricing highlight cap ---
# Purpose: Provide max highlight count for pricing tier cards.
# Inputs: None.
# Outputs: Integer cap applied during highlight list construction.
def get_public_pricing_max_highlights() -> int:
    """Return per-card highlight cap for the public pricing profile."""
    return MAX_MARKETING_HIGHLIGHTS
