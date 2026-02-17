"""Tier presentation profiles.

Synopsis:
Exports profile-specific catalog selectors used by the tier presentation core.

Glossary:
- Profile: Predefined section/rule selection strategy for a UI surface.
"""

from .public_pricing import (
    get_public_pricing_feature_sections,
    get_public_pricing_highlight_rules,
    get_public_pricing_max_highlights,
)

__all__ = [
    "get_public_pricing_feature_sections",
    "get_public_pricing_highlight_rules",
    "get_public_pricing_max_highlights",
]
