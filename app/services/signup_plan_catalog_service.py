"""Signup pricing catalog helpers.

This module keeps view-ready tier payload construction out of Flask route files.
"""

from __future__ import annotations

from ..models.subscription_tier import SubscriptionTier
from .billing_service import BillingService
from .lifetime_pricing_service import LifetimePricingService


class SignupPlanCatalogService:
    """Build concise plan payloads for signup pages and APIs."""

    @staticmethod
    def load_customer_facing_tiers() -> list[SubscriptionTier]:
        return (
            SubscriptionTier.query.filter_by(is_customer_facing=True)
            .filter(SubscriptionTier.billing_provider != "exempt")
            .order_by(SubscriptionTier.user_limit.asc(), SubscriptionTier.id.asc())
            .all()
        )

    @classmethod
    def build_available_tiers_payload(cls, db_tiers) -> dict[str, dict]:
        available_tiers: dict[str, dict] = {}
        for tier_obj in db_tiers:
            raw_features = [p.name for p in getattr(tier_obj, "permissions", [])]
            feature_highlights, feature_total = LifetimePricingService.summarize_features(raw_features, limit=9)
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

            monthly_pricing = None
            if tier_obj.stripe_lookup_key:
                try:
                    monthly_pricing = BillingService.get_live_pricing_for_tier(tier_obj)
                except Exception:
                    monthly_pricing = None

            yearly_lookup_key = LifetimePricingService.resolve_standard_yearly_lookup_key(tier_obj)
            yearly_pricing = None
            if yearly_lookup_key:
                try:
                    yearly_pricing = BillingService.get_live_pricing_for_lookup_key(yearly_lookup_key)
                except Exception:
                    yearly_pricing = None
            if yearly_pricing and yearly_pricing.get("billing_cycle") != "yearly":
                yearly_pricing = None

            price_display = monthly_pricing["formatted_price"] if monthly_pricing else "Contact Sales"
            available_tiers[str(tier_obj.id)] = {
                "name": tier_obj.name,
                "price_display": price_display,
                "monthly_price_display": price_display,
                "yearly_price_display": yearly_pricing["formatted_price"] if yearly_pricing else None,
                "yearly_lookup_key": yearly_lookup_key,
                "features": feature_highlights,
                "feature_total": feature_total,
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
