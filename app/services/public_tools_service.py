"""Public tool availability and homepage card helpers.

Synopsis:
Centralizes feature-flag-driven public tool metadata so marketing pages and
tool routes stay aligned when developer toggles change.

Glossary:
- Public tool: Anonymous calculator/formulator exposed under /tools.
- Homepage card: Marketing card shown on the homepage tools row.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.models import FeatureFlag

PUBLIC_TOOL_CATALOG: tuple[Dict[str, Any], ...] = (
    {
        "slug": "soap",
        "flag_key": "TOOLS_SOAP",
        "route_endpoint": "tools_bp.tools_soap",
        "name": "Soap Maker Tool",
        "summary": "Build soap formulas, tune lye/water, and export recipe-ready drafts.",
        "icon": "SO",
        "homepage_rank": 0,
        "default_enabled": True,
    },
    {
        "slug": "lotions",
        "flag_key": "TOOLS_LOTIONS",
        "route_endpoint": "tools_bp.tools_lotions",
        "name": "Lotion Maker Tool",
        "summary": "Plan lotion phases, preservative targets, and temperature ranges.",
        "icon": "LO",
        "homepage_rank": 1,
        "default_enabled": True,
    },
    {
        "slug": "baker",
        "flag_key": "TOOLS_BAKING",
        "route_endpoint": "tools_bp.tools_baker",
        "name": "Baking Calculator",
        "summary": "Scale recipes with baker percentages, hydration, and preferments.",
        "icon": "BK",
        "homepage_rank": 2,
        "default_enabled": True,
    },
    {
        "slug": "candles",
        "flag_key": "TOOLS_CANDLES",
        "route_endpoint": "tools_bp.tools_candles",
        "name": "Candle Maker Tool",
        "summary": "Dial in wax blends, fragrance load, and vessel sizing math.",
        "icon": "CA",
        "homepage_rank": 3,
        "default_enabled": True,
    },
    {
        "slug": "herbal",
        "flag_key": "TOOLS_HERBAL",
        "route_endpoint": "tools_bp.tools_herbal",
        "name": "Herbalist Calculator",
        "summary": "Work through tincture ratios, infusions, and dilution helpers.",
        "icon": "HB",
        "homepage_rank": 4,
        "default_enabled": True,
    },
)

PINNED_HOMEPAGE_TOOL_SLUG = "soap"


def _tool_sort_key(tool: Dict[str, Any]) -> tuple[int, int, str]:
    return (
        0 if tool.get("slug") == PINNED_HOMEPAGE_TOOL_SLUG else 1,
        int(tool.get("homepage_rank", 999)),
        str(tool.get("name") or ""),
    )


def is_tool_flag_enabled(flag_key: str, default: bool = True) -> bool:
    """Resolve one tool feature flag with a safe fallback."""
    try:
        flag = FeatureFlag.query.filter_by(key=flag_key).first()
        if flag is not None:
            return bool(flag.enabled)
    except Exception:
        return bool(default)
    return bool(default)


def get_public_tool_flags() -> Dict[str, bool]:
    """Return enabled status per public tool slug."""
    flags: Dict[str, bool] = {
        tool["slug"]: bool(tool.get("default_enabled", True))
        for tool in PUBLIC_TOOL_CATALOG
    }
    key_to_slug = {
        tool["flag_key"]: tool["slug"]
        for tool in PUBLIC_TOOL_CATALOG
        if tool.get("flag_key")
    }
    if not key_to_slug:
        return flags

    try:
        rows = FeatureFlag.query.filter(FeatureFlag.key.in_(tuple(key_to_slug.keys()))).all()
    except Exception:
        rows = []

    for row in rows:
        slug = key_to_slug.get(getattr(row, "key", ""))
        if slug:
            flags[slug] = bool(getattr(row, "enabled", False))
    return flags


def get_enabled_public_tools(
    *, tool_flags: Dict[str, bool] | None = None
) -> List[Dict[str, Any]]:
    """Return enabled public tool metadata sorted by homepage rank."""
    resolved_flags = tool_flags if tool_flags is not None else get_public_tool_flags()
    enabled: List[Dict[str, Any]] = []
    for tool in PUBLIC_TOOL_CATALOG:
        slug = str(tool.get("slug") or "")
        default_enabled = bool(tool.get("default_enabled", True))
        if bool(resolved_flags.get(slug, default_enabled)):
            enabled.append(dict(tool))

    enabled.sort(key=_tool_sort_key)
    return enabled


def get_homepage_public_tools(
    *, tool_flags: Dict[str, bool] | None = None, max_cards: int = 3
) -> List[Dict[str, Any]]:
    """Return a capped list of homepage cards from enabled tools."""
    tools = get_enabled_public_tools(tool_flags=tool_flags)
    if max_cards <= 0:
        return []
    return tools[:max_cards]


def get_homepage_balanced_display_tools(
    *, tool_flags: Dict[str, bool] | None = None, max_cards: int = 3
) -> List[Dict[str, Any]]:
    """Return homepage cards padded to a stable count with disabled fallbacks.

    Enabled tools always render first (soap pinned via rank). If fewer than
    ``max_cards`` are enabled, this pads with the next-ranked tools as disabled
    cards so desktop layouts stay visually balanced.
    """
    if max_cards <= 0:
        return []

    resolved_flags = tool_flags if tool_flags is not None else get_public_tool_flags()
    enabled_cards = get_homepage_public_tools(
        tool_flags=resolved_flags,
        max_cards=max_cards,
    )
    display_cards: List[Dict[str, Any]] = []
    seen_slugs: set[str] = set()

    for tool in enabled_cards:
        slug = str(tool.get("slug") or "")
        seen_slugs.add(slug)
        with_state = dict(tool)
        with_state["is_enabled"] = True
        display_cards.append(with_state)

    if len(display_cards) >= max_cards:
        return display_cards[:max_cards]

    ranked_all: List[Dict[str, Any]] = [dict(tool) for tool in PUBLIC_TOOL_CATALOG]
    ranked_all.sort(key=_tool_sort_key)
    for tool in ranked_all:
        if len(display_cards) >= max_cards:
            break
        slug = str(tool.get("slug") or "")
        if slug in seen_slugs:
            continue
        default_enabled = bool(tool.get("default_enabled", True))
        enabled = bool(resolved_flags.get(slug, default_enabled))
        fallback = dict(tool)
        fallback["is_enabled"] = enabled
        fallback["is_fallback"] = True
        display_cards.append(fallback)
        seen_slugs.add(slug)

    return display_cards[:max_cards]


def build_public_tool_flag_signature(tool_flags: Dict[str, bool] | None = None) -> str:
    """Return a short deterministic signature suitable for cache keys."""
    resolved_flags = tool_flags if tool_flags is not None else get_public_tool_flags()
    if not resolved_flags:
        return "none"
    return "|".join(
        f"{slug}:{1 if bool(resolved_flags.get(slug)) else 0}"
        for slug in sorted(resolved_flags)
    )
