"""Developer debug permission service boundary.

Synopsis:
Moves debug permission/tier queries out of debug blueprint routes so route
handlers remain transport-only.
"""

from __future__ import annotations

from app.extensions import db
from app.models import Permission
from app.models.subscription_tier import SubscriptionTier


class DebugPermissionService:
    """Service helpers for developer debug permission endpoints."""

    @staticmethod
    def list_active_permissions() -> list[Permission]:
        return Permission.query.filter_by(is_active=True).all()

    @staticmethod
    def resolve_tier_permissions(current_tier) -> list[str]:
        try:
            tier_id = (
                int(current_tier) if isinstance(current_tier, str) else current_tier
            )
        except Exception:
            tier_id = None
        tier_obj = db.session.get(SubscriptionTier, tier_id) if tier_id else None
        return (
            [p.name for p in getattr(tier_obj, "permissions", [])] if tier_obj else []
        )

    @staticmethod
    def list_tier_configs() -> dict[str, dict]:
        tiers_config = {}
        tiers = SubscriptionTier.query.all()
        for tier in tiers:
            tiers_config[str(tier.id)] = {
                "name": tier.name,
                "permissions": [p.name for p in getattr(tier, "permissions", [])],
                "billing_provider": tier.billing_provider,
                "is_billing_exempt": tier.is_billing_exempt,
                "is_customer_facing": tier.is_customer_facing,
            }
        return tiers_config
