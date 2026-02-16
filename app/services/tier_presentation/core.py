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

