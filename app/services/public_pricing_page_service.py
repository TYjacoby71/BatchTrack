"""Public pricing page context builder.

Synopsis:
Builds view-ready data for the public `/pricing` page so route handlers stay
focused on request/response concerns instead of pricing transformation logic.

Glossary:
- Tier card: Display payload for one of Hobbyist/Enthusiast/Fanatic columns.
- Comparison row: A feature label with boolean availability by tier.
"""

from __future__ import annotations

from typing import Any

from flask import url_for

from .lifetime_pricing_service import LifetimePricingService
from .signup_checkout_service import SignupCheckoutService


class PublicPricingPageService:
    """Compose public pricing page data from signup catalog services."""

    _ORDERED_TIER_KEYS: tuple[str, ...] = ("hobbyist", "enthusiast", "fanatic")
    _FEATURE_COMPARISON_SECTIONS: tuple[dict[str, Any], ...] = (
        {
            "title": "Core workflow features",
            "rows": (
                {
                    "label": "Inventory management (logging, adjustments, cost visibility)",
                    "kind": "boolean",
                    "permissions_any": (
                        "inventory.edit",
                        "inventory.adjust",
                        "inventory.view_costs",
                    ),
                },
                {
                    "label": "FIFO lot tracking and traceability",
                    "kind": "boolean",
                    "permissions_any": ("inventory.view",),
                },
                {
                    "label": "Recipe management and scaling",
                    "kind": "boolean",
                    "permissions_any": ("recipes.create", "recipes.edit", "recipes.scale"),
                },
                {
                    "label": "Production planning",
                    "kind": "boolean",
                    "permissions_any": ("recipes.plan_production",),
                },
                {
                    "label": "Batch production workflow",
                    "kind": "boolean",
                    "permissions_any": ("batches.create", "batches.finish"),
                },
                {
                    "label": "Product catalog and SKU workflows",
                    "kind": "boolean",
                    "permissions_any": ("products.create", "products.manage_variants"),
                },
                {
                    "label": "Recipe variation workflows",
                    "kind": "boolean",
                    "permissions_any": ("recipes.create_variations",),
                    "addon_keys_any": ("recipe_variations",),
                },
            ),
        },
        {
            "title": "Growth and channel features",
            "rows": (
                {
                    "label": "Recipe Library and Marketplace publishing",
                    "kind": "boolean",
                    "permissions_any": (
                        "recipes.marketplace_dashboard",
                        "recipes.sharing_controls",
                    ),
                },
                {
                    "label": "Paid recipe purchase controls",
                    "kind": "boolean",
                    "permissions_any": ("recipes.purchase_options",),
                },
                {
                    "label": "Global Inventory Library import",
                    "kind": "boolean",
                    "permissions_any": ("inventory.edit",),
                },
                {
                    "label": "Public maker tools (soap, candle, lotion, herbal, baking)",
                    "kind": "text",
                    "text": "Included for all visitors",
                },
                {
                    "label": "Shopify / marketplace / API integrations",
                    "kind": "boolean",
                    "permissions_any": (
                        "integrations.shopify",
                        "integrations.marketplace",
                        "integrations.api_access",
                    ),
                },
                {
                    "label": "Bulk inventory updates",
                    "kind": "boolean",
                    "permissions_any": ("inventory.adjust",),
                },
                {
                    "label": "Bulk production stock checks",
                    "kind": "boolean",
                    "permissions_any": ("recipes.plan_production",),
                },
            ),
        },
        {
            "title": "AI, team, and governance",
            "rows": (
                {
                    "label": "BatchBot assistant",
                    "kind": "boolean",
                    "permissions_any": ("ai.batchbot",),
                    "addon_keys_any": ("batchbot_access",),
                },
                {
                    "label": "Advanced analytics suite",
                    "kind": "boolean",
                    "permissions_any": ("reports.advanced", "reports.custom", "reports.analytics"),
                    "addon_keys_any": ("advanced_analytics",),
                },
                {
                    "label": "Organization dashboard",
                    "kind": "boolean",
                    "permissions_any": ("organization.view",),
                },
                {
                    "label": "Team member management",
                    "kind": "boolean",
                    "permissions_any": ("organization.manage_users",),
                    "min_user_limit": 2,
                },
                {
                    "label": "Role and permission management",
                    "kind": "boolean",
                    "permissions_any": ("organization.manage_roles",),
                    "min_user_limit": 2,
                },
                {
                    "label": "Billing management",
                    "kind": "boolean",
                    "permissions_any": ("organization.manage_billing",),
                },
            ),
        },
        {
            "title": "Limits and data policy",
            "rows": (
                {
                    "label": "Users per organization",
                    "kind": "limit",
                    "limit_field": "user_limit",
                    "singular": "seat",
                    "plural": "seats",
                    "none_display": "Contact support",
                },
                {
                    "label": "Recipe count",
                    "kind": "limit",
                    "limit_field": "max_recipes",
                    "permissions_any": ("recipes.view", "recipes.create"),
                    "singular": "recipe",
                    "plural": "recipes",
                },
                {
                    "label": "Product count",
                    "kind": "limit",
                    "limit_field": "max_products",
                    "permissions_any": ("products.view", "products.create"),
                    "singular": "product",
                    "plural": "products",
                },
                {
                    "label": "Batch limits",
                    "kind": "limit",
                    "limit_field": "max_monthly_batches",
                    "fallback_field": "max_batches",
                    "permissions_any": ("batches.view", "batches.create"),
                    "singular": "batch / month",
                    "plural": "batches / month",
                    "none_display": "Not specified",
                },
                {
                    "label": "BatchBot requests per usage window",
                    "kind": "batchbot_limit",
                },
                {
                    "label": "Data retention policy",
                    "kind": "retention",
                },
            ),
        },
    )

    @classmethod
    def build_context(cls, *, request) -> dict[str, Any]:
        """Return render-ready context for the `/pricing` page."""
        signup_context = SignupCheckoutService.build_request_context(request=request, oauth_user_info=None)
        available_tiers = signup_context.available_tiers
        lifetime_offers = signup_context.lifetime_offers
        offers_by_key = {
            str(offer.get("key", "")).strip().lower(): offer for offer in lifetime_offers if offer
        }

        pricing_tiers: list[dict[str, Any]] = []
        for tier_key in cls._ORDERED_TIER_KEYS:
            tier_payload = cls._build_tier_payload(
                tier_key=tier_key,
                offer=offers_by_key.get(tier_key, {}),
                available_tiers=available_tiers,
            )
            pricing_tiers.append(tier_payload)

        comparison_sections = cls._build_feature_comparison_sections(pricing_tiers)
        lifetime_has_capacity = any(tier.get("lifetime_has_remaining") for tier in pricing_tiers)

        return {
            "pricing_tiers": pricing_tiers,
            "comparison_sections": comparison_sections,
            "lifetime_has_capacity": lifetime_has_capacity,
        }

    @classmethod
    def _build_tier_payload(
        cls,
        *,
        tier_key: str,
        offer: dict[str, Any],
        available_tiers: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Build one tier card payload for public pricing display."""
        tier_id = str(offer.get("tier_id") or "")
        tier_data = available_tiers.get(tier_id) if tier_id else None

        if not tier_data:
            for candidate_tier_id, candidate_tier_data in available_tiers.items():
                candidate_name = str(candidate_tier_data.get("name", "")).strip().lower()
                if candidate_name == tier_key:
                    tier_data = candidate_tier_data
                    tier_id = str(candidate_tier_id)
                    break

        raw_feature_names = (tier_data or {}).get("all_features") or []
        permission_set = cls._normalize_token_set(raw_feature_names)
        addon_key_set = cls._normalize_token_set((tier_data or {}).get("all_addon_keys"))
        addon_function_set = cls._normalize_token_set((tier_data or {}).get("all_addon_function_keys"))
        addon_permission_set = cls._normalize_token_set((tier_data or {}).get("addon_permission_names"))
        all_feature_labels: list[str] = []
        all_feature_set: set[str] = set()
        for raw_feature_name in raw_feature_names:
            feature_label = LifetimePricingService.format_feature_label(raw_feature_name)
            normalized_feature = cls._normalize_feature_label(feature_label)
            if not normalized_feature or normalized_feature in all_feature_set:
                continue
            all_feature_set.add(normalized_feature)
            all_feature_labels.append(feature_label)

        limit_map = {
            "user_limit": cls._coerce_int((tier_data or {}).get("user_limit")),
            "max_recipes": cls._coerce_int((tier_data or {}).get("max_recipes")),
            "max_batches": cls._coerce_int((tier_data or {}).get("max_batches")),
            "max_products": cls._coerce_int((tier_data or {}).get("max_products")),
            "max_monthly_batches": cls._coerce_int((tier_data or {}).get("max_monthly_batches")),
            "max_batchbot_requests": cls._coerce_int((tier_data or {}).get("max_batchbot_requests")),
        }
        retention_policy = str((tier_data or {}).get("retention_policy") or "").strip().lower()
        retention_label = str((tier_data or {}).get("retention_label") or "").strip()
        has_retention_entitlement = bool(
            retention_policy == "subscribed" or "retention" in addon_function_set
        )

        highlight_features = cls._build_marketing_feature_highlights(
            permission_set=permission_set,
            addon_key_set=addon_key_set,
            limit_map=limit_map,
            has_retention_entitlement=has_retention_entitlement,
        )
        if not highlight_features:
            highlight_features = cls._build_fallback_feature_highlights(tier_data, all_feature_labels)

        has_yearly_price = bool((tier_data or {}).get("yearly_price_display"))
        has_lifetime_remaining = bool(offer.get("has_remaining") and tier_id)

        monthly_url = (
            url_for(
                "auth.signup_checkout",
                tier=tier_id,
                billing_mode="standard",
                billing_cycle="monthly",
                source=f"pricing_{tier_key}_monthly",
            )
            if tier_id
            else None
        )
        yearly_url = (
            url_for(
                "auth.signup_checkout",
                tier=tier_id,
                billing_mode="standard",
                billing_cycle="yearly",
                source=f"pricing_{tier_key}_yearly",
            )
            if tier_id and has_yearly_price
            else None
        )
        lifetime_url = (
            url_for(
                "auth.signup_checkout",
                billing_mode="lifetime",
                lifetime_tier=offer.get("key"),
                tier=tier_id,
                source=f"pricing_{tier_key}_lifetime",
            )
            if has_lifetime_remaining
            else None
        )

        return {
            "key": tier_key,
            "name": str(offer.get("name") or tier_key.title()),
            "tagline": str(offer.get("tagline") or "Built for makers"),
            "future_scope": str(offer.get("future_scope") or ""),
            "tier_id": tier_id,
            "monthly_price_display": (tier_data or {}).get("monthly_price_display"),
            "yearly_price_display": (tier_data or {}).get("yearly_price_display"),
            "feature_highlights": highlight_features,
            "all_feature_labels": all_feature_labels,
            "all_feature_set": all_feature_set,
            "permission_set": permission_set,
            "addon_key_set": addon_key_set,
            "addon_function_set": addon_function_set,
            "addon_permission_set": addon_permission_set,
            "limits": limit_map,
            "retention_policy": retention_policy,
            "retention_label": retention_label,
            "has_retention_entitlement": has_retention_entitlement,
            "feature_total": int((tier_data or {}).get("feature_total") or len(all_feature_labels)),
            "lifetime_offer": offer,
            "lifetime_has_remaining": has_lifetime_remaining,
            "signup_monthly_url": monthly_url,
            "signup_yearly_url": yearly_url,
            "signup_lifetime_url": lifetime_url,
        }

    @classmethod
    def _build_feature_comparison_sections(
        cls,
        pricing_tiers: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Return grouped feature/limit rows for the pricing comparison table."""
        sections: list[dict[str, Any]] = []
        for section_spec in cls._FEATURE_COMPARISON_SECTIONS:
            rows: list[dict[str, Any]] = []
            for row_spec in section_spec.get("rows", ()):
                row: dict[str, Any] = {"label": str(row_spec.get("label") or ""), "cells": {}}
                for tier in pricing_tiers:
                    row["cells"][tier["key"]] = cls._build_comparison_cell(tier=tier, row_spec=row_spec)
                rows.append(row)
            sections.append({"title": str(section_spec.get("title") or ""), "rows": rows})
        return sections

    @classmethod
    def _build_comparison_cell(cls, *, tier: dict[str, Any], row_spec: dict[str, Any]) -> dict[str, Any]:
        kind = str(row_spec.get("kind") or "boolean").strip().lower()
        if kind == "text":
            return {"type": "text", "display": str(row_spec.get("text") or "")}
        if kind == "limit":
            return {"type": "text", "display": cls._format_limit_cell(tier=tier, row_spec=row_spec)}
        if kind == "batchbot_limit":
            return {"type": "text", "display": cls._format_batchbot_limit_cell(tier)}
        if kind == "retention":
            return {"type": "text", "display": cls._format_retention_cell(tier)}

        enabled = cls._tier_matches_row_spec(tier=tier, row_spec=row_spec)
        return {
            "type": "boolean",
            "value": enabled,
            "display": "Included" if enabled else "Not included",
        }

    @classmethod
    def _tier_matches_row_spec(cls, *, tier: dict[str, Any], row_spec: dict[str, Any]) -> bool:
        permission_set = set(tier.get("permission_set") or set())
        addon_key_set = set(tier.get("addon_key_set") or set())
        addon_function_set = set(tier.get("addon_function_set") or set())
        limits = tier.get("limits") or {}

        permissions_any = cls._normalize_token_set(row_spec.get("permissions_any"))
        permissions_all = cls._normalize_token_set(row_spec.get("permissions_all"))
        addon_keys_any = cls._normalize_token_set(row_spec.get("addon_keys_any"))
        addon_functions_any = cls._normalize_token_set(row_spec.get("addon_functions_any"))

        if permissions_all and not permissions_all.issubset(permission_set):
            return False

        has_any_entitlement_rule = bool(permissions_any or addon_keys_any or addon_functions_any)
        entitlement_match = False
        if permissions_any and not permission_set.isdisjoint(permissions_any):
            entitlement_match = True
        if addon_keys_any and not addon_key_set.isdisjoint(addon_keys_any):
            entitlement_match = True
        if addon_functions_any and not addon_function_set.isdisjoint(addon_functions_any):
            entitlement_match = True
        if has_any_entitlement_rule and not entitlement_match:
            return False

        min_user_limit = cls._coerce_int(row_spec.get("min_user_limit"))
        if min_user_limit is not None:
            user_limit = cls._coerce_int(limits.get("user_limit"))
            if user_limit is None:
                return False
            if user_limit != -1 and user_limit < min_user_limit:
                return False

        return True

    @classmethod
    def _format_limit_cell(cls, *, tier: dict[str, Any], row_spec: dict[str, Any]) -> str:
        if not cls._tier_matches_row_spec(tier=tier, row_spec=row_spec):
            return "Not included"

        limits = tier.get("limits") or {}
        limit_field = str(row_spec.get("limit_field") or "").strip()
        fallback_field = str(row_spec.get("fallback_field") or "").strip()
        raw_limit = cls._coerce_int(limits.get(limit_field))
        if raw_limit is None and fallback_field:
            raw_limit = cls._coerce_int(limits.get(fallback_field))

        none_display = str(row_spec.get("none_display") or "Unlimited")
        singular = str(row_spec.get("singular") or "item")
        plural = str(row_spec.get("plural") or f"{singular}s")
        return cls._format_numeric_limit(
            value=raw_limit,
            singular=singular,
            plural=plural,
            none_display=none_display,
        )

    @classmethod
    def _format_batchbot_limit_cell(cls, tier: dict[str, Any]) -> str:
        has_access = cls._tier_matches_row_spec(
            tier=tier,
            row_spec={
                "permissions_any": ("ai.batchbot",),
                "addon_keys_any": ("batchbot_access",),
            },
        )
        if not has_access:
            return "No assistant access"

        raw_limit = cls._coerce_int((tier.get("limits") or {}).get("max_batchbot_requests"))
        if raw_limit is None:
            return "Contact support"
        if raw_limit < 0:
            return "Unlimited"
        if raw_limit == 0:
            return "No included requests"
        return f"{raw_limit} / window"

    @classmethod
    def _format_retention_cell(cls, tier: dict[str, Any]) -> str:
        if tier.get("has_retention_entitlement"):
            return "Retained while subscribed"

        retention_label = str(tier.get("retention_label") or "").strip()
        normalized_label = retention_label.lower()
        if normalized_label in {"subscribed", "while subscribed", "retained while subscribed"}:
            return "Retained while subscribed"
        if normalized_label in {"1 year", "one year"}:
            return "1 year standard retention"
        if retention_label:
            return retention_label

        if str(tier.get("retention_policy") or "").strip().lower() == "subscribed":
            return "Retained while subscribed"
        return "1 year standard retention"

    @classmethod
    def _build_marketing_feature_highlights(
        cls,
        *,
        permission_set: set[str],
        addon_key_set: set[str],
        limit_map: dict[str, int | None],
        has_retention_entitlement: bool,
    ) -> list[str]:
        """Return curated, customer-facing highlights for tier cards."""
        highlight_candidates = [
            (
                "Inventory tracking with FIFO lot history",
                bool({"inventory.view", "inventory.adjust"} & permission_set),
            ),
            (
                "Recipe management, scaling, and production planning",
                bool({"recipes.create", "recipes.scale", "recipes.plan_production"} & permission_set),
            ),
            (
                "Batch production workflow",
                bool({"batches.create", "batches.finish"} & permission_set),
            ),
            (
                "Product catalog with SKU and variant support",
                bool({"products.create", "products.manage_variants"} & permission_set),
            ),
            (
                "Recipe variation workflows",
                "recipes.create_variations" in permission_set or "recipe_variations" in addon_key_set,
            ),
            (
                "Sales tracking and reservation controls",
                bool({"products.sales_tracking", "inventory.reserve"} & permission_set),
            ),
            (
                "Team management and role controls",
                bool({"organization.manage_users", "organization.manage_roles"} & permission_set)
                and cls._is_multi_user(limit_map.get("user_limit")),
            ),
            (
                "Recipe Library and marketplace publishing",
                bool({"recipes.marketplace_dashboard", "recipes.sharing_controls"} & permission_set),
            ),
            (
                "Shopify, marketplace, and API integrations",
                bool(
                    {
                        "integrations.shopify",
                        "integrations.marketplace",
                        "integrations.api_access",
                    }
                    & permission_set
                ),
            ),
            (
                "BatchBot assistant access",
                "ai.batchbot" in permission_set or "batchbot_access" in addon_key_set,
            ),
            (
                "Data retained while subscribed",
                has_retention_entitlement,
            ),
        ]

        highlights: list[str] = []
        seen: set[str] = set()
        for label, is_enabled in highlight_candidates:
            normalized = cls._normalize_feature_label(label)
            if not is_enabled or not normalized or normalized in seen:
                continue
            highlights.append(label)
            seen.add(normalized)
            if len(highlights) >= 8:
                break

        batchbot_limit = cls._coerce_int(limit_map.get("max_batchbot_requests"))
        if (
            batchbot_limit is not None
            and batchbot_limit > 0
            and ("ai.batchbot" in permission_set or "batchbot_access" in addon_key_set)
            and len(highlights) < 8
        ):
            highlights.append(f"{batchbot_limit} BatchBot requests per usage window")

        return highlights

    @classmethod
    def _build_fallback_feature_highlights(
        cls,
        tier_data: dict[str, Any] | None,
        all_feature_labels: list[str],
    ) -> list[str]:
        fallback: list[str] = []
        seen: set[str] = set()
        for feature in (tier_data or {}).get("features", []):
            feature_label = cls._display_feature_label(feature)
            normalized_feature = cls._normalize_feature_label(feature_label)
            if not normalized_feature or normalized_feature in seen:
                continue
            seen.add(normalized_feature)
            fallback.append(feature_label)
            if len(fallback) >= 8:
                return fallback
        return fallback or all_feature_labels[:8]

    @staticmethod
    def _format_numeric_limit(
        *,
        value: int | None,
        singular: str,
        plural: str,
        none_display: str,
    ) -> str:
        if value is None:
            return none_display
        if value < 0:
            return "Unlimited"
        if value == 0:
            return "Not included"
        if value == 1:
            return f"1 {singular}"
        return f"Up to {value} {plural}"

    @staticmethod
    def _is_multi_user(user_limit: int | None) -> bool:
        if user_limit is None:
            return False
        return user_limit == -1 or user_limit > 1

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        if value in (None, "", "null"):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_token_set(values) -> set[str]:
        if not values:
            return set()
        normalized: set[str] = set()
        for value in values:
            token = str(value or "").strip().lower()
            if token:
                normalized.add(token)
        return normalized

    @staticmethod
    def _normalize_feature_label(value: str | None) -> str:
        """Normalize feature labels for consistent set membership checks."""
        cleaned = " ".join(str(value or "").replace(".", " ").replace("_", " ").split())
        return cleaned.strip().lower()

    @classmethod
    def _display_feature_label(cls, value: str | None) -> str:
        """Convert feature labels into title-cased display copy."""
        normalized = cls._normalize_feature_label(value)
        if not normalized:
            return ""
        return " ".join(token.capitalize() for token in normalized.split())
