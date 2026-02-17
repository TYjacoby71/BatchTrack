"""Tier presentation orchestration service.

Synopsis:
Coordinates catalog rules and evaluators to generate customer-facing tier
comparison data and card highlights.

Glossary:
- Tier facts: Normalized per-tier capability sets and limits.
- Comparison section: Group of rows rendered in pricing comparison tables.
"""

from __future__ import annotations

from typing import Any

from .evaluators import build_comparison_cell, tier_matches_row_spec
from .helpers import coerce_int, normalize_feature_label
from .profiles import (
    get_public_pricing_feature_sections,
    get_public_pricing_highlight_rules,
    get_public_pricing_max_highlights,
)


# --- Tier presentation core ---
# Purpose: Orchestrate catalog rules into table sections and single-tier feature payloads.
# Inputs: Normalized tier fact dictionaries plus optional profile/cap settings.
# Outputs: Render-ready sections, feature lists, and highlight strings for pricing/signup surfaces.
class TierPresentationCore:
    """Build feature-table and highlight payloads from declarative rules."""

    def __init__(
        self,
        *,
        feature_sections: tuple[dict[str, Any], ...] | None = None,
        highlight_rules: tuple[dict[str, Any], ...] | None = None,
        max_highlights: int | None = None,
    ) -> None:
        self._feature_sections = (
            feature_sections
            if feature_sections is not None
            else get_public_pricing_feature_sections()
        )
        self._highlight_rules = (
            highlight_rules
            if highlight_rules is not None
            else get_public_pricing_highlight_rules()
        )
        self._max_highlights = (
            max_highlights if max_highlights is not None else get_public_pricing_max_highlights()
        )

    def build_comparison_sections(self, pricing_tiers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return grouped feature/limit rows for table rendering."""
        sections: list[dict[str, Any]] = []
        for section_spec in self._feature_sections:
            rows: list[dict[str, Any]] = []
            for row_spec in section_spec.get("rows", ()):
                row: dict[str, Any] = {"label": str(row_spec.get("label") or ""), "cells": {}}
                for tier in pricing_tiers:
                    row["cells"][tier["key"]] = build_comparison_cell(tier=tier, row_spec=row_spec)
                rows.append(row)
            sections.append({"title": str(section_spec.get("title") or ""), "rows": rows})
        return sections

    def build_single_tier_sections(
        self,
        *,
        tier: dict[str, Any],
        include_not_included: bool = False,
    ) -> list[dict[str, Any]]:
        """Return sectioned rows for one selected tier."""
        sections: list[dict[str, Any]] = []
        for section_spec in self._feature_sections:
            section_rows: list[dict[str, Any]] = []
            for row_spec in section_spec.get("rows", ()):
                kind = str(row_spec.get("kind") or "boolean").strip().lower()
                cell = build_comparison_cell(tier=tier, row_spec=row_spec)

                if not include_not_included and kind == "boolean" and not bool(cell.get("value")):
                    continue
                if (
                    not include_not_included
                    and kind in {"limit", "batchbot_limit"}
                    and str(cell.get("display") or "").strip().lower() in {"not included", "no assistant access"}
                ):
                    continue

                section_rows.append(
                    {
                        "label": str(row_spec.get("label") or ""),
                        "kind": kind,
                        "cell": cell,
                    }
                )
            if section_rows:
                sections.append({"title": str(section_spec.get("title") or ""), "rows": section_rows})
        return sections

    def build_single_tier_feature_list(
        self,
        *,
        tier: dict[str, Any],
        max_items: int | None = None,
    ) -> list[str]:
        """Return a flat feature checklist for one selected tier."""
        sections = self.build_single_tier_sections(tier=tier, include_not_included=False)
        items: list[str] = []
        seen: set[str] = set()
        for section in sections:
            for row in section.get("rows", ()):
                kind = str(row.get("kind") or "boolean").strip().lower()
                label = str(row.get("label") or "").strip()
                cell = row.get("cell") or {}
                display = str(cell.get("display") or "").strip()
                if not label:
                    continue

                if kind == "boolean":
                    item = label
                elif kind == "text":
                    item = f"{label}: {display}" if display else label
                else:
                    if not display:
                        continue
                    item = f"{label}: {display}"

                normalized_item = normalize_feature_label(item)
                if not normalized_item or normalized_item in seen:
                    continue
                seen.add(normalized_item)
                items.append(item)

                if max_items is not None and max_items > 0 and len(items) >= max_items:
                    return items
        return items

    def resolve_tier_highlights(
        self,
        *,
        tier_data: dict[str, Any] | None,
        all_feature_labels: list[str],
        permission_set: set[str],
        addon_key_set: set[str],
        limit_map: dict[str, int | None],
        has_retention_entitlement: bool,
    ) -> list[str]:
        """Return curated highlights, falling back to raw feature labels."""
        highlights = self.build_marketing_feature_highlights(
            permission_set=permission_set,
            addon_key_set=addon_key_set,
            limit_map=limit_map,
            has_retention_entitlement=has_retention_entitlement,
        )
        if highlights:
            return highlights
        return self.build_fallback_feature_highlights(tier_data=tier_data, all_feature_labels=all_feature_labels)

    def build_marketing_feature_highlights(
        self,
        *,
        permission_set: set[str],
        addon_key_set: set[str],
        limit_map: dict[str, int | None],
        has_retention_entitlement: bool,
    ) -> list[str]:
        """Return curated card highlights for one tier."""
        highlights: list[str] = []
        seen: set[str] = set()

        for rule in self._highlight_rules:
            label = str(rule.get("label") or "").strip()
            normalized_label = normalize_feature_label(label)
            if not normalized_label or normalized_label in seen:
                continue
            if not self._highlight_rule_matches(
                rule=rule,
                permission_set=permission_set,
                addon_key_set=addon_key_set,
                limit_map=limit_map,
                has_retention_entitlement=has_retention_entitlement,
            ):
                continue
            highlights.append(label)
            seen.add(normalized_label)
            if len(highlights) >= self._max_highlights:
                break

        batchbot_limit = coerce_int(limit_map.get("max_batchbot_requests"))
        has_batchbot_access = tier_matches_row_spec(
            tier={
                "permission_set": permission_set,
                "addon_key_set": addon_key_set,
                "addon_function_set": set(),
                "limits": limit_map,
            },
            row_spec={
                "permissions_any": ("ai.batchbot",),
                "addon_keys_any": ("batchbot_access",),
            },
        )
        if (
            batchbot_limit is not None
            and batchbot_limit > 0
            and has_batchbot_access
            and len(highlights) < self._max_highlights
        ):
            highlights.append(f"{batchbot_limit} BatchBot requests per usage window")

        return highlights

    def build_fallback_feature_highlights(
        self,
        *,
        tier_data: dict[str, Any] | None,
        all_feature_labels: list[str],
    ) -> list[str]:
        """Build fallback highlights from raw tier features."""
        fallback: list[str] = []
        seen: set[str] = set()
        for feature in (tier_data or {}).get("features", []):
            feature_label = self.display_feature_label(feature)
            normalized_feature = normalize_feature_label(feature_label)
            if not normalized_feature or normalized_feature in seen:
                continue
            seen.add(normalized_feature)
            fallback.append(feature_label)
            if len(fallback) >= self._max_highlights:
                return fallback
        return fallback or all_feature_labels[: self._max_highlights]

    def _highlight_rule_matches(
        self,
        *,
        rule: dict[str, Any],
        permission_set: set[str],
        addon_key_set: set[str],
        limit_map: dict[str, int | None],
        has_retention_entitlement: bool,
    ) -> bool:
        if rule.get("require_retention_entitlement") and not has_retention_entitlement:
            return False

        return tier_matches_row_spec(
            tier={
                "permission_set": permission_set,
                "addon_key_set": addon_key_set,
                "addon_function_set": set(),
                "limits": limit_map,
            },
            row_spec=rule,
        )

    @staticmethod
    def display_feature_label(value: str | None) -> str:
        """Convert feature labels into title-cased display copy."""
        normalized = normalize_feature_label(value)
        if not normalized:
            return ""
        return " ".join(token.capitalize() for token in normalized.split())

