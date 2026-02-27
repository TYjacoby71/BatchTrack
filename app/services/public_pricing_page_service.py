"""Public pricing page context builder.

Synopsis:
Builds view-ready data for the public `/pricing` page while delegating feature
presentation rules to `tier_presentation`.

Glossary:
- Tier card: Display payload for one of Hobbyist/Enthusiast/Fanatic columns.
- Comparison row: A feature label with availability/limit value by tier.
"""

from __future__ import annotations

from typing import Any

from flask import url_for

from .lifetime_pricing_service import LifetimePricingService
from .signup_checkout_service import SignupCheckoutService
from .tier_presentation import TierPresentationCore
from .tier_presentation.helpers import (
    coerce_int,
    normalize_feature_label,
    normalize_token_set,
)


# --- Public pricing page service ---
# Purpose: Build pricing-page tier cards and comparison-table payloads for templates.
# Inputs: Signup checkout request context and tier/lifetime catalog payloads.
# Outputs: Render-ready dictionary with pricing tiers, grouped comparison sections, and capacity flags.
class PublicPricingPageService:
    """Compose public pricing page data from signup catalog services."""

    _ORDERED_TIER_KEYS: tuple[str, ...] = ("hobbyist", "enthusiast", "fanatic")
    _tier_presentation = TierPresentationCore()

    @classmethod
    def build_context(cls, *, request) -> dict[str, Any]:
        """Return render-ready context for the `/pricing` page."""
        signup_context = SignupCheckoutService.build_request_context(
            request=request,
            oauth_user_info=None,
            allow_live_pricing_network=True,
        )
        available_tiers = signup_context.available_tiers
        lifetime_offers = signup_context.lifetime_offers
        offers_by_key = {
            str(offer.get("key", "")).strip().lower(): offer
            for offer in lifetime_offers
            if offer
        }
        offers_by_tier_id = {
            str(offer.get("tier_id") or ""): offer
            for offer in lifetime_offers
            if offer and offer.get("tier_id")
        }

        pricing_tiers: list[dict[str, Any]] = []
        for tier_key in cls._ORDERED_TIER_KEYS:
            tier_payload = cls._build_tier_payload(
                tier_key=tier_key,
                offer=offers_by_key.get(tier_key, {}),
                offers_by_tier_id=offers_by_tier_id,
                available_tiers=available_tiers,
            )
            pricing_tiers.append(tier_payload)

        comparison_sections = cls._tier_presentation.build_comparison_sections(
            pricing_tiers
        )
        lifetime_has_capacity = any(
            tier.get("lifetime_has_remaining") for tier in pricing_tiers
        )

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
        offers_by_tier_id: dict[str, dict[str, Any]],
        available_tiers: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Build one tier card payload for public pricing display."""
        tier_id = ""
        tier_data = None

        # Resolve by canonical pricing key first so cards/table columns stay stable
        # even when lifetime offer tier mappings drift.
        for candidate_tier_id, candidate_tier_data in available_tiers.items():
            candidate_name = str(candidate_tier_data.get("name", "")).strip().lower()
            if candidate_name == tier_key:
                tier_data = candidate_tier_data
                tier_id = str(candidate_tier_id)
                break

        if not tier_data:
            tier_id = str(offer.get("tier_id") or "")
            tier_data = available_tiers.get(tier_id) if tier_id else None

        resolved_offer = offer or {}
        if tier_id:
            resolved_offer = offers_by_tier_id.get(tier_id, resolved_offer)

        raw_feature_names = (tier_data or {}).get("all_features") or []
        permission_set = normalize_token_set(raw_feature_names)
        addon_key_set = normalize_token_set((tier_data or {}).get("all_addon_keys"))
        addon_function_set = normalize_token_set(
            (tier_data or {}).get("all_addon_function_keys")
        )
        addon_permission_set = normalize_token_set(
            (tier_data or {}).get("addon_permission_names")
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
            "user_limit": coerce_int((tier_data or {}).get("user_limit")),
            "max_recipes": coerce_int((tier_data or {}).get("max_recipes")),
            "max_batches": coerce_int((tier_data or {}).get("max_batches")),
            "max_products": coerce_int((tier_data or {}).get("max_products")),
            "max_monthly_batches": coerce_int(
                (tier_data or {}).get("max_monthly_batches")
            ),
            "max_batchbot_requests": coerce_int(
                (tier_data or {}).get("max_batchbot_requests")
            ),
        }
        retention_policy = (
            str((tier_data or {}).get("retention_policy") or "").strip().lower()
        )
        retention_label = str((tier_data or {}).get("retention_label") or "").strip()
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

        has_yearly_price = bool((tier_data or {}).get("yearly_price_display"))
        has_lifetime_remaining = bool(resolved_offer.get("has_remaining") and tier_id)

        monthly_url = (
            url_for(
                "core.signup_alias",
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
                "core.signup_alias",
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
                "core.signup_alias",
                billing_mode="lifetime",
                lifetime_tier=resolved_offer.get("key"),
                tier=tier_id,
                source=f"pricing_{tier_key}_lifetime",
            )
            if has_lifetime_remaining
            else None
        )

        return {
            "key": tier_key,
            "name": str((tier_data or {}).get("name") or tier_key.title()),
            "tagline": str(resolved_offer.get("tagline") or "Built for makers"),
            "future_scope": str(resolved_offer.get("future_scope") or ""),
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
            "feature_total": int(
                (tier_data or {}).get("feature_total") or len(all_feature_labels)
            ),
            "lifetime_offer": resolved_offer,
            "lifetime_has_remaining": has_lifetime_remaining,
            "signup_monthly_url": monthly_url,
            "signup_yearly_url": yearly_url,
            "signup_lifetime_url": lifetime_url,
        }
