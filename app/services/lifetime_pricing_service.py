"""Lifetime tier presentation and seat-counter helpers.

Synopsis:
Builds marketing/signup lifetime tier payloads from existing paid tiers while
keeping the app's single-lookup-key-per-tier model.

Glossary:
- Lifetime tier: Limited-seat launch offer mapped to an existing paid tier.
- Display floor: Minimum seats-left value shown before real sales catch up.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from sqlalchemy import func

from ..extensions import db
from ..models.models import Organization
from ..models.subscription_tier import SubscriptionTier


class LifetimePricingService:
    """Single source for lifetime offer card data and counters."""

    _VERSION_SUFFIX_RE = re.compile(r"([_-])v\d+$", re.IGNORECASE)

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
        coupon_codes = [str(blueprint["default_coupon_code"]).lower() for blueprint in cls.DEFAULT_TIER_BLUEPRINTS]
        sold_counts = cls._sold_count_by_coupon(coupon_codes)

        offers: list[dict] = []
        for index, blueprint in enumerate(cls.DEFAULT_TIER_BLUEPRINTS):
            tier = tiers[index] if index < len(tiers) else None
            coupon_code = str(blueprint["default_coupon_code"]).strip()
            sold_count = int(sold_counts.get(coupon_code.lower(), 0))
            seat_total = int(blueprint["seat_total"])
            display_floor = int(blueprint["display_floor"])
            threshold = max(0, seat_total - display_floor)
            true_spots_left = max(0, seat_total - sold_count)
            display_spots_left = display_floor if sold_count < threshold else true_spots_left

            monthly_lookup_key = (getattr(tier, "stripe_lookup_key", None) or "").strip() if tier else ""
            yearly_lookup_key = cls.resolve_standard_yearly_lookup_key(tier)
            lifetime_lookup_key = cls.resolve_standard_lifetime_lookup_key(tier)

            monthly_pricing = cls._get_lookup_key_pricing(monthly_lookup_key)
            yearly_pricing = cls._get_lookup_key_pricing(yearly_lookup_key)
            lifetime_pricing = cls._get_lookup_key_pricing(lifetime_lookup_key)

            lifetime_price_is_valid = bool(
                lifetime_pricing and lifetime_pricing.get("billing_cycle") == "one-time"
            )
            has_remaining = bool(tier and lifetime_price_is_valid and true_spots_left > 0)

            lifetime_price_copy = "Configure lifetime Stripe price"
            if lifetime_price_is_valid and lifetime_pricing:
                lifetime_price_copy = f"{lifetime_pricing.get('formatted_price')} one-time"
            elif yearly_pricing:
                lifetime_price_copy = f"{yearly_pricing.get('formatted_price')} yearly available"
            elif monthly_pricing:
                lifetime_price_copy = f"{monthly_pricing.get('formatted_price')} monthly available"

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
                "has_remaining": has_remaining,
                "coupon_code": coupon_code,
                "stripe_coupon_id": None,
                "stripe_promotion_code_id": None,
                "tier_id": str(tier.id) if tier else "",
                "base_tier_name": tier.name if tier else "Unavailable",
                "monthly_lookup_key": monthly_lookup_key or None,
                "monthly_price_display": monthly_pricing.get("formatted_price") if monthly_pricing else None,
                "yearly_lookup_key": yearly_lookup_key,
                "yearly_price_display": yearly_pricing.get("formatted_price") if yearly_pricing else None,
                "lifetime_lookup_key": lifetime_lookup_key,
                "lifetime_price_display": lifetime_pricing.get("formatted_price") if lifetime_pricing else None,
                "lifetime_price_copy": lifetime_price_copy,
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
        """Resolve yearly lookup key from a tier's single configured lookup key."""
        if not tier:
            return None
        return cls._resolve_lookup_variant(
            base_lookup_key=getattr(tier, "stripe_lookup_key", None),
            target_variant="yearly",
            expected_cycle="yearly",
        )

    @classmethod
    def resolve_standard_lifetime_lookup_key(cls, tier: SubscriptionTier | None) -> str | None:
        """Resolve lifetime lookup key from a tier's single configured lookup key."""
        if not tier:
            return None
        return cls._resolve_lookup_variant(
            base_lookup_key=getattr(tier, "stripe_lookup_key", None),
            target_variant="lifetime",
            expected_cycle="one-time",
        )

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
    def _derive_lookup_variant(base_lookup_key: str | None, target_variant: str) -> str | None:
        """Derive related lookup keys via naming convention.

        Supported conventions:
        - *_monthly -> *_yearly or *_lifetime
        - *-monthly -> *-yearly or *-lifetime
        - ...monthly (suffix) -> ...yearly or ...lifetime
        """
        lookup = (base_lookup_key or "").strip()
        variant = (target_variant or "").strip().lower()
        if not lookup or variant not in {"monthly", "yearly", "lifetime"}:
            return None

        replacements = (
            ("_monthly", f"_{variant}"),
            ("-monthly", f"-{variant}"),
            ("monthly", variant),
            ("_yearly", f"_{variant}"),
            ("-yearly", f"-{variant}"),
            ("yearly", variant),
            ("_lifetime", f"_{variant}"),
            ("-lifetime", f"-{variant}"),
            ("lifetime", variant),
        )
        for from_token, to_token in replacements:
            if lookup.endswith(from_token):
                return f"{lookup[:-len(from_token)]}{to_token}"
            if from_token in lookup:
                return lookup.replace(from_token, to_token)
        return None

    @classmethod
    def _resolve_lookup_variant(
        cls,
        *,
        base_lookup_key: str | None,
        target_variant: str,
        expected_cycle: str | None = None,
    ) -> str | None:
        """Resolve the first existing Stripe lookup variant.

        This is intentionally defensive: if strict versioned keys are missing, it
        retries likely non-versioned and delimiter variants to keep pricing UI
        functional instead of breaking card rendering.
        """
        candidates = cls._lookup_variant_candidates(base_lookup_key, target_variant)
        for candidate in candidates:
            pricing = cls._get_lookup_key_pricing(candidate)
            if not pricing:
                continue
            if expected_cycle and pricing.get("billing_cycle") != expected_cycle:
                continue
            return candidate
        return None

    @classmethod
    def _lookup_variant_candidates(cls, base_lookup_key: str | None, target_variant: str) -> list[str]:
        lookup = (base_lookup_key or "").strip()
        if not lookup:
            return []

        variants = []

        primary = cls._derive_lookup_variant(lookup, target_variant)
        if primary:
            variants.append(primary)

        stripped = cls._strip_version_suffix(lookup)
        if stripped and stripped != lookup:
            secondary = cls._derive_lookup_variant(stripped, target_variant)
            if secondary:
                variants.append(secondary)

        expanded = []
        for value in variants:
            expanded.extend(cls._delimiter_variants(value))

        deduped = []
        seen = set()
        for candidate in expanded:
            cleaned = (candidate or "").strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            deduped.append(cleaned)
        return deduped

    @classmethod
    def _strip_version_suffix(cls, lookup_key: str | None) -> str:
        return cls._VERSION_SUFFIX_RE.sub("", (lookup_key or "").strip())

    @staticmethod
    def _delimiter_variants(value: str) -> list[str]:
        value = (value or "").strip()
        if not value:
            return []
        output = [value]
        if "_" in value:
            output.append(value.replace("_", "-"))
        if "-" in value:
            output.append(value.replace("-", "_"))
        return output

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
    def _get_lookup_key_pricing(lookup_key: str | None) -> dict | None:
        if not lookup_key:
            return None
        try:
            from .billing_service import BillingService

            return BillingService.get_live_pricing_for_lookup_key(lookup_key)
        except Exception:
            return None
