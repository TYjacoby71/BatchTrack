"""Lifetime tier presentation and seat-counter helpers.

Synopsis:
Builds marketing/signup lifetime tier payloads, maps tiers to Stripe yearly
prices, and calculates seat counters from promo-code usage.

Glossary:
- Lifetime tier: A limited-seat launch offer mapped to an existing paid tier.
- Display floor: Minimum seats-left value shown before real sales catch up.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence

from flask import current_app
from sqlalchemy import func

from ..extensions import db
from ..models.models import Organization
from ..models.subscription_tier import SubscriptionTier

logger = logging.getLogger(__name__)


class LifetimePricingService:
    """Single source for lifetime offer card data and counters."""

    DEFAULT_TIER_BLUEPRINTS = (
        {
            "key": "hobbyist",
            "name": "Hobbyist",
            "tagline": "Perfect for solo makers",
            "seat_total": 2000,
            "display_floor": 1997,
            "default_coupon_code": "LIFETIME-HOBBYIST",
            "future_scope": "Core platform features forever",
        },
        {
            "key": "enthusiast",
            "name": "Enthusiast",
            "tagline": "Built for growing teams",
            "seat_total": 1000,
            "display_floor": 995,
            "default_coupon_code": "LIFETIME-ENTHUSIAST",
            "future_scope": "Advanced workflows forever",
        },
        {
            "key": "fanatic",
            "name": "Fanatic",
            "tagline": "Everything now and in the future",
            "seat_total": 500,
            "display_floor": 492,
            "default_coupon_code": "LIFETIME-FANATIC",
            "future_scope": "All current + future features forever",
        },
    )

    @classmethod
    def build_lifetime_offers(cls, paid_tiers: Sequence[SubscriptionTier] | None = None) -> list[dict]:
        """Return normalized lifetime offers mapped to existing paid tiers."""
        tiers = cls._sort_paid_tiers(paid_tiers or cls._load_paid_tiers())
        yearly_lookup_map = cls._read_mapping("LIFETIME_YEARLY_LOOKUP_KEYS")
        coupon_code_map = cls._read_mapping("LIFETIME_COUPON_CODES")
        coupon_id_map = cls._read_mapping("LIFETIME_COUPON_IDS")
        promo_code_id_map = cls._read_mapping("LIFETIME_PROMOTION_CODE_IDS")

        resolved_coupon_codes: list[str] = []
        for blueprint in cls.DEFAULT_TIER_BLUEPRINTS:
            code = cls._resolve_coupon_code(blueprint, coupon_code_map)
            if code:
                resolved_coupon_codes.append(code.lower())
        sold_counts = cls._sold_count_by_coupon(resolved_coupon_codes)

        offers: list[dict] = []
        for index, blueprint in enumerate(cls.DEFAULT_TIER_BLUEPRINTS):
            tier = tiers[index] if index < len(tiers) else None
            coupon_code = cls._resolve_coupon_code(blueprint, coupon_code_map)
            sold_count = int(sold_counts.get(coupon_code.lower(), 0)) if coupon_code else 0
            seat_total = int(blueprint["seat_total"])
            display_floor = int(blueprint["display_floor"])
            threshold = max(0, seat_total - display_floor)
            true_spots_left = max(0, seat_total - sold_count)
            display_spots_left = display_floor if sold_count < threshold else true_spots_left

            yearly_lookup_key = cls._resolve_yearly_lookup_key(
                offer_key=blueprint["key"],
                tier=tier,
                yearly_lookup_map=yearly_lookup_map,
            )
            monthly_price_display = None
            if tier and getattr(tier, "stripe_lookup_key", None):
                monthly_pricing = cls._get_lookup_key_pricing(getattr(tier, "stripe_lookup_key", None))
                monthly_price_display = monthly_pricing.get("formatted_price") if monthly_pricing else None
            yearly_price_display = None
            if yearly_lookup_key:
                yearly_pricing = cls._get_lookup_key_pricing(yearly_lookup_key)
                yearly_price_display = (
                    yearly_pricing.get("formatted_price") if yearly_pricing else None
                )

            offer = {
                "key": blueprint["key"],
                "name": blueprint["name"],
                "tagline": blueprint["tagline"],
                "future_scope": blueprint["future_scope"],
                "seat_total": seat_total,
                "display_floor": display_floor,
                "sold_count": sold_count,
                "threshold": threshold,
                "true_spots_left": true_spots_left,
                "display_spots_left": display_spots_left,
                "has_remaining": true_spots_left > 0,
                "coupon_code": coupon_code,
                "stripe_coupon_id": cls._resolve_id_for_offer(
                    offer_key=blueprint["key"],
                    tier=tier,
                    id_map=coupon_id_map,
                ),
                "stripe_promotion_code_id": cls._resolve_id_for_offer(
                    offer_key=blueprint["key"],
                    tier=tier,
                    id_map=promo_code_id_map,
                ),
                "monthly_price_display": monthly_price_display,
                "yearly_lookup_key": yearly_lookup_key,
                "yearly_price_display": yearly_price_display,
                "lifetime_price_copy": (
                    f"{yearly_price_display} one-time"
                    if yearly_price_display
                    else "One-time price of 1 year"
                ),
                "tier_id": str(tier.id) if tier else "",
                "base_tier_name": tier.name if tier else "Unavailable",
            }
            offers.append(offer)

        return offers

    @staticmethod
    def any_seats_remaining(offers: Sequence[dict] | None) -> bool:
        """Return whether at least one lifetime offer is available."""
        return any(bool(offer.get("has_remaining")) for offer in (offers or []))

    @staticmethod
    def map_by_key(offers: Sequence[dict] | None) -> dict[str, dict]:
        """Index offers by lifetime key for quick route lookups."""
        return {
            str(offer.get("key")): offer
            for offer in (offers or [])
            if offer and offer.get("key")
        }

    @staticmethod
    def map_by_tier_id(offers: Sequence[dict] | None) -> dict[str, dict]:
        """Index offers by mapped subscription tier ID."""
        return {
            str(offer.get("tier_id")): offer
            for offer in (offers or [])
            if offer and offer.get("tier_id")
        }

    @staticmethod
    def format_feature_label(permission_name: str) -> str:
        """Convert permission-like keys into human-readable feature labels."""
        cleaned = (permission_name or "").replace(".", " ").replace("_", " ").strip()
        if not cleaned:
            return ""
        return " ".join(part.capitalize() for part in cleaned.split())

    @classmethod
    def summarize_features(cls, permission_names: Sequence[str], limit: int = 8) -> tuple[list[str], int]:
        """Return a concise list of display-ready feature labels."""
        labels = []
        seen = set()
        for raw in permission_names or []:
            label = cls.format_feature_label(raw)
            if not label:
                continue
            normalized = label.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            labels.append(label)

        total = len(labels)
        return labels[: max(1, limit)], total

    @classmethod
    def resolve_standard_yearly_lookup_key(cls, tier: SubscriptionTier | None) -> str | None:
        """Resolve the yearly lookup key for a paid (non-lifetime) tier."""
        if not tier:
            return None
        yearly_map = cls._read_mapping("STANDARD_YEARLY_LOOKUP_KEYS")
        for candidate in cls._id_candidates(offer_key="", tier=tier):
            if not candidate:
                continue
            value = yearly_map.get(candidate)
            if value:
                return value
        return cls._derive_yearly_lookup_from_monthly(getattr(tier, "stripe_lookup_key", None))

    @classmethod
    def _load_paid_tiers(cls) -> list[SubscriptionTier]:
        return (
            SubscriptionTier.query.filter_by(is_customer_facing=True, billing_provider="stripe")
            .order_by(SubscriptionTier.user_limit.asc(), SubscriptionTier.id.asc())
            .all()
        )

    @staticmethod
    def _sort_paid_tiers(tiers: Sequence[SubscriptionTier]) -> list[SubscriptionTier]:
        def _tier_sort_key(tier: SubscriptionTier):
            user_limit = getattr(tier, "user_limit", None)
            limit_sort_value = 1_000_000 if user_limit in (None, -1) else int(user_limit)
            return (limit_sort_value, int(getattr(tier, "id", 0) or 0))

        return sorted(list(tiers or []), key=_tier_sort_key)

    @staticmethod
    def _read_mapping(config_key: str) -> dict[str, str]:
        """Read a mapping from Flask config (dict, JSON, or CSV pairs)."""
        raw = current_app.config.get(config_key)
        if isinstance(raw, dict):
            return {
                str(key).strip().lower(): str(value).strip()
                for key, value in raw.items()
                if str(value).strip()
            }
        if not isinstance(raw, str) or not raw.strip():
            return {}

        stripped = raw.strip()
        parsed = None
        if stripped.startswith("{"):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON for %s, falling back to CSV parser.", config_key)
        if isinstance(parsed, dict):
            return {
                str(key).strip().lower(): str(value).strip()
                for key, value in parsed.items()
                if str(value).strip()
            }

        mapping: dict[str, str] = {}
        for chunk in stripped.split(","):
            part = chunk.strip()
            if not part or ":" not in part:
                continue
            key, value = part.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            if key and value:
                mapping[key] = value
        return mapping

    @classmethod
    def _resolve_coupon_code(cls, blueprint: dict, coupon_code_map: dict[str, str]) -> str:
        offer_key = str(blueprint["key"]).strip().lower()
        configured = coupon_code_map.get(offer_key)
        return (configured or blueprint["default_coupon_code"]).strip()

    @classmethod
    def _resolve_id_for_offer(cls, *, offer_key: str, tier: SubscriptionTier | None, id_map: dict[str, str]) -> str | None:
        for candidate in cls._id_candidates(offer_key=offer_key, tier=tier):
            value = id_map.get(candidate)
            if value:
                return value
        return None

    @classmethod
    def _resolve_yearly_lookup_key(
        cls,
        *,
        offer_key: str,
        tier: SubscriptionTier | None,
        yearly_lookup_map: dict[str, str],
    ) -> str | None:
        configured = cls._resolve_id_for_offer(
            offer_key=offer_key,
            tier=tier,
            id_map=yearly_lookup_map,
        )
        if configured:
            return configured
        if not tier:
            return None

        return cls._derive_yearly_lookup_from_monthly(getattr(tier, "stripe_lookup_key", None))

    @staticmethod
    def _derive_yearly_lookup_from_monthly(monthly_lookup_key: str | None) -> str | None:
        monthly_lookup = (monthly_lookup_key or "").strip()
        if not monthly_lookup:
            return None
        if "_monthly" in monthly_lookup:
            return monthly_lookup.replace("_monthly", "_yearly")
        if "-monthly" in monthly_lookup:
            return monthly_lookup.replace("-monthly", "-yearly")
        if monthly_lookup.endswith("monthly"):
            return f"{monthly_lookup[:-7]}yearly"
        return None

    @staticmethod
    def _id_candidates(*, offer_key: str, tier: SubscriptionTier | None) -> list[str]:
        candidates = []
        normalized_offer_key = offer_key.strip().lower()
        if normalized_offer_key:
            candidates.append(normalized_offer_key)
        if tier:
            candidates.append(str(tier.id).strip().lower())
            tier_name = (tier.name or "").strip().lower()
            if tier_name:
                candidates.append(tier_name)
            tier_lookup = (tier.stripe_lookup_key or "").strip().lower()
            if tier_lookup:
                candidates.append(tier_lookup)
        return candidates

    @staticmethod
    def _sold_count_by_coupon(coupon_codes_lower: Sequence[str]) -> dict[str, int]:
        cleaned_codes = [code.strip().lower() for code in coupon_codes_lower if code and code.strip()]
        if not cleaned_codes:
            return {}

        rows = (
            db.session.query(
                func.lower(Organization.promo_code).label("promo_code"),
                func.count(Organization.id).label("total"),
            )
            .filter(Organization.promo_code.isnot(None))
            .filter(func.lower(Organization.promo_code).in_(cleaned_codes))
            .group_by(func.lower(Organization.promo_code))
            .all()
        )
        return {str(row.promo_code): int(row.total or 0) for row in rows if row.promo_code}

    @staticmethod
    def _get_lookup_key_pricing(lookup_key: str) -> dict | None:
        if not lookup_key:
            return None
        try:
            from .billing_service import BillingService

            return BillingService.get_live_pricing_for_lookup_key(lookup_key)
        except Exception:
            return None
