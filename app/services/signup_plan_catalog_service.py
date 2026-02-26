"""Signup pricing catalog helpers.

Synopsis:
Builds customer-facing tier payloads used by signup and checkout surfaces.
Combines billing price data, permission/add-on entitlements, and tier
presentation outputs into a concise view model.

Glossary:
- Available tier payload: JSON-serializable plan dictionary used by templates.
- Presentation features: Customer-facing single-tier feature list from tier rules.
"""

from __future__ import annotations

from ..models.subscription_tier import SubscriptionTier
from .billing_service import BillingService
from .lifetime_pricing_service import LifetimePricingService
from .tier_presentation import TierPresentationCore
from .tier_presentation.helpers import coerce_int, normalize_token_set


# --- Signup plan catalog service ---
# Purpose: Provide normalized tier payloads for signup UIs and pricing APIs.
# Inputs: Customer-facing SubscriptionTier ORM records and pricing lookup services.
# Outputs: Mapping keyed by tier id with prices, limits, add-ons, and presentation features.
class SignupPlanCatalogService:
    """Build concise plan payloads for signup pages and APIs."""

    _tier_presentation = TierPresentationCore()
    _SIGNUP_PRESENTATION_FEATURE_LIMIT = 9

    @staticmethod
    def load_customer_facing_tiers() -> list[SubscriptionTier]:
        return (
            SubscriptionTier.query.filter_by(is_customer_facing=True)
            .filter(SubscriptionTier.billing_provider != "exempt")
            .order_by(SubscriptionTier.user_limit.asc(), SubscriptionTier.id.asc())
            .all()
        )

    @classmethod
    def build_available_tiers_payload(
        cls,
        db_tiers,
        *,
        include_live_pricing: bool = True,
        allow_live_pricing_network: bool = True,
    ) -> dict[str, dict]:
        available_tiers: dict[str, dict] = {}
        for tier_obj in db_tiers:
            raw_features = [p.name for p in getattr(tier_obj, "permissions", [])]
            feature_highlights, feature_total = (
                LifetimePricingService.summarize_features(raw_features, limit=9)
            )
            allowed_addons = list(getattr(tier_obj, "allowed_addons", []) or [])
            included_addons = list(getattr(tier_obj, "included_addons", []) or [])

            allowed_addon_keys = sorted(
                {
                    str(addon.key).strip().lower()
                    for addon in allowed_addons
                    if addon and getattr(addon, "key", None)
                }
            )
            included_addon_keys = sorted(
                {
                    str(addon.key).strip().lower()
                    for addon in included_addons
                    if addon and getattr(addon, "key", None)
                }
            )
            all_addon_keys = sorted(set(allowed_addon_keys) | set(included_addon_keys))

            allowed_addon_function_keys = sorted(
                {
                    str(addon.function_key).strip().lower()
                    for addon in allowed_addons
                    if addon and getattr(addon, "function_key", None)
                }
            )
            included_addon_function_keys = sorted(
                {
                    str(addon.function_key).strip().lower()
                    for addon in included_addons
                    if addon and getattr(addon, "function_key", None)
                }
            )
            all_addon_function_keys = sorted(
                set(allowed_addon_function_keys) | set(included_addon_function_keys)
            )

            addon_permission_names = sorted(
                {
                    str(addon.permission_name).strip().lower()
                    for addon in (allowed_addons + included_addons)
                    if addon and getattr(addon, "permission_name", None)
                }
            )

            permission_set = normalize_token_set(raw_features)
            addon_key_set = set(all_addon_keys)
            addon_function_set = set(all_addon_function_keys)
            limit_map = {
                "user_limit": coerce_int(tier_obj.user_limit),
                "max_recipes": coerce_int(tier_obj.max_recipes),
                "max_batches": coerce_int(tier_obj.max_batches),
                "max_products": coerce_int(tier_obj.max_products),
                "max_monthly_batches": coerce_int(tier_obj.max_monthly_batches),
                "max_batchbot_requests": coerce_int(tier_obj.max_batchbot_requests),
            }
            retention_policy = (
                str(getattr(tier_obj, "retention_policy", None) or "").strip().lower()
            )
            retention_label = str(
                getattr(tier_obj, "retention_label", None) or ""
            ).strip()
            has_retention_entitlement = bool(
                retention_policy == "subscribed" or "retention" in addon_function_set
            )
            presentation_tier = {
                "permission_set": permission_set,
                "addon_key_set": addon_key_set,
                "addon_function_set": addon_function_set,
                "limits": limit_map,
                "retention_policy": retention_policy,
                "retention_label": retention_label,
                "has_retention_entitlement": has_retention_entitlement,
            }
            all_presentation_features = (
                cls._tier_presentation.build_single_tier_feature_list(
                    tier=presentation_tier
                )
            )
            presentation_feature_limit = cls._SIGNUP_PRESENTATION_FEATURE_LIMIT
            presentation_features = all_presentation_features[
                :presentation_feature_limit
            ]
            presentation_feature_total = len(all_presentation_features)

            monthly_lookup_key = (getattr(tier_obj, "stripe_lookup_key", None) or "").strip()
            monthly_pricing = None
            if include_live_pricing and monthly_lookup_key:
                try:
                    monthly_pricing = BillingService.get_live_pricing_for_tier(
                        tier_obj,
                        allow_network=allow_live_pricing_network,
                    )
                except Exception:
                    monthly_pricing = None

            yearly_lookup_key = (
                LifetimePricingService.resolve_standard_yearly_lookup_key(
                    tier_obj,
                    allow_network=allow_live_pricing_network,
                )
            )
            yearly_pricing = None
            if include_live_pricing and yearly_lookup_key:
                try:
                    yearly_pricing = BillingService.get_live_pricing_for_lookup_key(
                        yearly_lookup_key,
                        allow_network=allow_live_pricing_network,
                    )
                except Exception:
                    yearly_pricing = None
            if yearly_pricing and yearly_pricing.get("billing_cycle") != "yearly":
                yearly_pricing = None

            monthly_price_display = (
                monthly_pricing["formatted_price"]
                if monthly_pricing
                else (
                    "Monthly pricing at secure checkout"
                    if monthly_lookup_key
                    else "Contact Sales"
                )
            )
            yearly_price_display = (
                yearly_pricing["formatted_price"]
                if yearly_pricing
                else (
                    "Yearly pricing at secure checkout"
                    if yearly_lookup_key
                    else None
                )
            )
            price_display = monthly_price_display or "Contact Sales"
            available_tiers[str(tier_obj.id)] = {
                "name": tier_obj.name,
                "price_display": price_display,
                "monthly_price_display": monthly_price_display,
                "yearly_price_display": yearly_price_display,
                "yearly_lookup_key": yearly_lookup_key,
                "features": feature_highlights,
                "feature_total": feature_total,
                "presentation_features": presentation_features or feature_highlights,
                "presentation_feature_total": (
                    presentation_feature_total
                    if presentation_features
                    else feature_total
                ),
                "all_features": raw_features,
                "user_limit": tier_obj.user_limit,
                "max_recipes": tier_obj.max_recipes,
                "max_batches": tier_obj.max_batches,
                "max_products": tier_obj.max_products,
                "max_monthly_batches": tier_obj.max_monthly_batches,
                "max_batchbot_requests": tier_obj.max_batchbot_requests,
                "retention_policy": getattr(tier_obj, "retention_policy", None),
                "retention_label": getattr(tier_obj, "retention_label", None),
                "allowed_addon_keys": allowed_addon_keys,
                "included_addon_keys": included_addon_keys,
                "all_addon_keys": all_addon_keys,
                "allowed_addon_function_keys": allowed_addon_function_keys,
                "included_addon_function_keys": included_addon_function_keys,
                "all_addon_function_keys": all_addon_function_keys,
                "addon_permission_names": addon_permission_names,
                "whop_product_id": tier_obj.whop_product_key or "",
            }
        return available_tiers
