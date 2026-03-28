"""Developer integrations admin service.

Synopsis:
Provide service-layer helpers for integration checklist views and admin writes
so developer routes stay transport-focused.

Glossary:
- Stripe event summary: Aggregate + most recent webhook event metadata.
- Toggleable flags: Feature flags allowed to be changed from integrations UI.
"""

from __future__ import annotations

from typing import Any

from app.extensions import db


class IntegrationAdminService:
    """Service boundary for developer integrations admin operations."""

    @staticmethod
    def get_customer_facing_tier_count() -> int:
        from app.services.billing_service import BillingService

        return len(BillingService.get_available_tiers())

    @staticmethod
    def get_stripe_event_summary() -> dict[str, Any]:
        from app.models.stripe_event import StripeEvent

        total = StripeEvent.query.count()
        last = StripeEvent.query.order_by(StripeEvent.id.desc()).first()
        payload: dict[str, Any] = {"total_events": total}
        if last:
            payload.update(
                {
                    "last_event_id": last.event_id,
                    "last_event_type": last.event_type,
                    "last_status": last.status,
                    "last_processed_at": (
                        last.processed_at.isoformat() if last.processed_at else None
                    ),
                }
            )
        return payload

    @staticmethod
    def set_feature_flags(
        *,
        requested_flags: dict[str, Any],
        toggleable_keys: set[str] | list[str],
    ) -> None:
        from app.models.feature_flag import FeatureFlag

        allowed = set(toggleable_keys)
        try:
            for flag_key, enabled in requested_flags.items():
                if flag_key not in allowed:
                    continue
                feature_flag = FeatureFlag.query.filter_by(key=flag_key).first()
                if feature_flag:
                    feature_flag.enabled = bool(enabled)
                else:
                    db.session.add(
                        FeatureFlag(
                            key=flag_key,
                            enabled=bool(enabled),
                            description=f"Auto-created flag for {flag_key}",
                        )
                    )
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
