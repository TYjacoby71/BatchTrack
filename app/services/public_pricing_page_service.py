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
    _FALLBACK_COMPARISON_LABELS: tuple[str, ...] = (
        "Inventory Tracking",
        "Recipe Management",
        "Batch Production Workflow",
        "Real-time Stock Alerts",
        "FIFO Lot Tracking",
        "Organization Collaboration",
        "Advanced Analytics",
        "Priority Support",
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

        comparison_labels = cls._build_comparison_labels(pricing_tiers)
        comparison_rows = cls._build_comparison_rows(comparison_labels, pricing_tiers)
        lifetime_has_capacity = any(tier.get("lifetime_has_remaining") for tier in pricing_tiers)

        return {
            "pricing_tiers": pricing_tiers,
            "comparison_rows": comparison_rows,
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
        all_feature_labels: list[str] = []
        all_feature_set: set[str] = set()
        for raw_feature_name in raw_feature_names:
            feature_label = LifetimePricingService.format_feature_label(raw_feature_name)
            normalized_feature = cls._normalize_feature_label(feature_label)
            if not normalized_feature or normalized_feature in all_feature_set:
                continue
            all_feature_set.add(normalized_feature)
            all_feature_labels.append(feature_label)

        highlight_features: list[str] = []
        highlight_seen: set[str] = set()
        for feature in (tier_data or {}).get("features", []):
            feature_label = cls._display_feature_label(feature)
            normalized_feature = cls._normalize_feature_label(feature_label)
            if not normalized_feature or normalized_feature in highlight_seen:
                continue
            highlight_seen.add(normalized_feature)
            highlight_features.append(feature_label)

        if not highlight_features:
            highlight_features = all_feature_labels[:6]

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
            "feature_total": int((tier_data or {}).get("feature_total") or len(all_feature_labels)),
            "lifetime_offer": offer,
            "lifetime_has_remaining": has_lifetime_remaining,
            "signup_monthly_url": monthly_url,
            "signup_yearly_url": yearly_url,
            "signup_lifetime_url": lifetime_url,
        }

    @classmethod
    def _build_comparison_labels(cls, pricing_tiers: list[dict[str, Any]]) -> list[str]:
        """Return ordered unique feature labels for comparison table rows."""
        comparison_labels: list[str] = []
        comparison_seen: set[str] = set()

        for tier in pricing_tiers:
            for feature_label in tier.get("feature_highlights", []):
                normalized_label = cls._normalize_feature_label(feature_label)
                if not normalized_label or normalized_label in comparison_seen:
                    continue
                comparison_seen.add(normalized_label)
                comparison_labels.append(cls._display_feature_label(feature_label))

            for feature_label in tier.get("all_feature_labels", []):
                normalized_label = cls._normalize_feature_label(feature_label)
                if not normalized_label or normalized_label in comparison_seen:
                    continue
                comparison_seen.add(normalized_label)
                comparison_labels.append(cls._display_feature_label(feature_label))

        return comparison_labels or list(cls._FALLBACK_COMPARISON_LABELS)

    @classmethod
    def _build_comparison_rows(
        cls,
        comparison_labels: list[str],
        pricing_tiers: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Return feature availability rows for the pricing comparison table."""
        comparison_rows: list[dict[str, Any]] = []
        for feature_label in comparison_labels[:18]:
            normalized_label = cls._normalize_feature_label(feature_label)
            row: dict[str, Any] = {"label": feature_label}
            for tier in pricing_tiers:
                row[tier["key"]] = normalized_label in tier.get("all_feature_set", set())
            comparison_rows.append(row)
        return comparison_rows

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
