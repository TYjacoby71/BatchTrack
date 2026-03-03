"""Public pricing page context builder.

Synopsis:
Builds view-ready data for the public `/pricing` page while delegating feature
presentation rules to `tier_presentation`.

Glossary:
- Tier card: Display payload for one customer-facing subscription tier.
- Comparison row: A feature label with availability/limit value by tier.
"""

from __future__ import annotations

import re
from typing import Any

from flask import url_for

from ..models.subscription_tier import SubscriptionTier
from ..utils.settings import is_feature_enabled
from .lifetime_pricing_service import LifetimePricingService
from .signup_plan_catalog_service import SignupPlanCatalogService
from .tier_presentation import TierPresentationCore
from .tier_presentation.helpers import (
    coerce_int,
    normalize_feature_label,
    normalize_token_set,
)


# --- Public pricing page service ---
# Purpose: Build pricing-page tier cards and comparison-table payloads for templates.
# Inputs: Customer-facing subscription tiers and optional lifetime offer payloads.
# Outputs: Render-ready dictionary with pricing tiers, grouped comparison sections, and capacity flags.
class PublicPricingPageService:
    """Compose public pricing page data from signup catalog services."""

    _TIER_KEY_SANITIZE_RE = re.compile(r"[^a-z0-9]+")
    _SIGNUP_FREE_TIER_FLAG_KEY = "FEATURE_PRICING_SIGNUP_FREE_TIER"
    _tier_presentation = TierPresentationCore()

    @classmethod
    def build_context(cls, *, request) -> dict[str, Any]:
        """Return render-ready context for the `/pricing` page."""
        del request

        db_tiers = cls._load_customer_facing_tiers()
        show_signup_free_tier = is_feature_enabled(cls._SIGNUP_FREE_TIER_FLAG_KEY)
        if not show_signup_free_tier:
            free_tier = SignupPlanCatalogService.load_customer_facing_free_tier()
            free_tier_id = str(getattr(free_tier, "id", "") or "") if free_tier else ""
            if free_tier_id:
                db_tiers = [
                    tier
                    for tier in db_tiers
                    if str(getattr(tier, "id", "") or "") != free_tier_id
                ]

        if not db_tiers:
            return {
                "pricing_tiers": [],
                "lifetime_tiers": [],
                "comparison_sections": [],
                "lifetime_has_capacity": False,
            }

        available_tiers = SignupPlanCatalogService.build_available_tiers_payload(
            db_tiers,
            include_live_pricing=True,
            allow_live_pricing_network=True,
        )

        pricing_tiers: list[dict[str, Any]] = []
        seen_tier_keys: set[str] = set()
        for tier_obj in db_tiers:
            tier_id = str(getattr(tier_obj, "id", "") or "")
            tier_data = available_tiers.get(tier_id)
            if not tier_data:
                continue

            tier_key = cls._next_tier_key(
                tier_name=str(tier_data.get("name") or ""),
                tier_id=tier_id,
                seen_tier_keys=seen_tier_keys,
            )
            tier_payload = cls._build_tier_payload(
                tier_key=tier_key,
                tier_id=tier_id,
                tier_data=tier_data,
                offer={},
                can_standard_checkout=cls._can_standard_checkout(tier_obj),
            )
            pricing_tiers.append(tier_payload)

        comparison_sections = cls._tier_presentation.build_comparison_sections(
            pricing_tiers
        )

        return {
            "pricing_tiers": pricing_tiers,
            "lifetime_tiers": [],
            "comparison_sections": comparison_sections,
            "lifetime_has_capacity": False,
        }

    @classmethod
    def _build_tier_payload(
        cls,
        *,
        tier_key: str,
        tier_id: str,
        tier_data: dict[str, Any],
        offer: dict[str, Any],
        can_standard_checkout: bool,
    ) -> dict[str, Any]:
        """Build one tier card payload for public pricing display."""
        resolved_offer = offer or {}
        raw_feature_names = tier_data.get("all_features") or []
        permission_set = normalize_token_set(raw_feature_names)
        addon_key_set = normalize_token_set(tier_data.get("all_addon_keys"))
        addon_function_set = normalize_token_set(
            tier_data.get("all_addon_function_keys")
        )
        addon_permission_set = normalize_token_set(
            tier_data.get("addon_permission_names")
        )

        all_feature_labels: list[str] = []
        all_feature_set: set[str] = set()
        for raw_feature_name in raw_feature_names:
            feature_label = LifetimePricingService.format_feature_label(
                raw_feature_name
            )
            normalized_feature = normalize_feature_label(feature_label)
            if not normalized_feature or normalized_feature in all_feature_set:
                continue
            all_feature_set.add(normalized_feature)
            all_feature_labels.append(feature_label)

        limit_map = {
            "user_limit": coerce_int(tier_data.get("user_limit")),
            "max_recipes": coerce_int(tier_data.get("max_recipes")),
            "max_batches": coerce_int(tier_data.get("max_batches")),
            "max_products": coerce_int(tier_data.get("max_products")),
            "max_monthly_batches": coerce_int(
                tier_data.get("max_monthly_batches")
            ),
            "max_batchbot_requests": coerce_int(
                tier_data.get("max_batchbot_requests")
            ),
        }
        retention_policy = str(tier_data.get("retention_policy") or "").strip().lower()
        retention_label = str(tier_data.get("retention_label") or "").strip()
        has_retention_entitlement = bool(
            retention_policy == "subscribed" or "retention" in addon_function_set
        )

        highlight_features = cls._tier_presentation.resolve_tier_highlights(
            tier_data=tier_data,
            all_feature_labels=all_feature_labels,
            permission_set=permission_set,
            addon_key_set=addon_key_set,
            limit_map=limit_map,
            has_retention_entitlement=has_retention_entitlement,
        )

        monthly_price_display = str(tier_data.get("monthly_price_display") or "").strip()
        yearly_price_display = str(tier_data.get("yearly_price_display") or "").strip()
        has_monthly_subscription = bool(
            can_standard_checkout
            and monthly_price_display
            and monthly_price_display.lower() != "contact sales"
        )
        has_yearly_subscription = bool(can_standard_checkout and yearly_price_display)
        has_lifetime_remaining = bool(resolved_offer.get("has_remaining") and tier_id)

        monthly_url = (
            url_for(
                "auth.signup_checkout",
                tier=tier_id,
                billing_mode="standard",
                billing_cycle="monthly",
                source=f"pricing_{tier_key}_monthly",
            )
            if tier_id and has_monthly_subscription
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
            if tier_id and has_yearly_subscription
            else None
        )
        lifetime_url = (
            url_for(
                "auth.signup_checkout",
                billing_mode="lifetime",
                lifetime_tier=resolved_offer.get("key"),
                tier=tier_id,
                source=f"pricing_{tier_key}_lifetime",
            )
            if has_lifetime_remaining and can_standard_checkout
            else None
        )

        return {
            "key": tier_key,
            "name": str(tier_data.get("name") or tier_key.title()),
            "tagline": str(resolved_offer.get("tagline") or "Built for makers"),
            "future_scope": str(resolved_offer.get("future_scope") or ""),
            "tier_id": tier_id,
            "monthly_price_display": monthly_price_display or None,
            "yearly_price_display": yearly_price_display or None,
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
            "feature_total": int(
                tier_data.get("feature_total") or len(all_feature_labels)
            ),
            "lifetime_offer": resolved_offer,
            "lifetime_has_remaining": has_lifetime_remaining,
            "signup_monthly_url": monthly_url,
            "signup_yearly_url": yearly_url,
            "signup_lifetime_url": lifetime_url,
            "has_monthly_subscription": has_monthly_subscription,
            "has_yearly_subscription": has_yearly_subscription,
            "can_standard_checkout": can_standard_checkout,
        }

    @classmethod
    def _load_customer_facing_tiers(cls) -> list[SubscriptionTier]:
        tiers = (
            SubscriptionTier.query.filter_by(is_customer_facing=True)
            .order_by(SubscriptionTier.user_limit.asc(), SubscriptionTier.id.asc())
            .all()
        )
        return sorted(tiers, key=cls._tier_sort_key)

    @staticmethod
    def _tier_sort_key(tier_obj: SubscriptionTier) -> tuple[int, int]:
        user_limit = getattr(tier_obj, "user_limit", None)
        limit_sort_value = 1_000_000 if user_limit in (None, -1) else int(user_limit)
        tier_id = int(getattr(tier_obj, "id", 0) or 0)
        return (limit_sort_value, tier_id)

    @classmethod
    def _next_tier_key(
        cls,
        *,
        tier_name: str,
        tier_id: str,
        seen_tier_keys: set[str],
    ) -> str:
        normalized_name = cls._TIER_KEY_SANITIZE_RE.sub(
            "_", str(tier_name or "").strip().lower()
        ).strip("_")
        base_key = normalized_name or f"tier_{tier_id}"
        candidate = base_key
        suffix = 2
        while candidate in seen_tier_keys:
            candidate = f"{base_key}_{suffix}"
            suffix += 1
        seen_tier_keys.add(candidate)
        return candidate

    @staticmethod
    def _can_standard_checkout(tier_obj: SubscriptionTier) -> bool:
        billing_provider = str(getattr(tier_obj, "billing_provider", "")).strip().lower()
        return billing_provider != "exempt"
