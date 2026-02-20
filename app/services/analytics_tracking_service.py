"""Analytics tracking facade.

Synopsis:
Provides a thin, centralized relay API for analytics emission. Feature code
calls this service, which validates against the registry and forwards to
`EventEmitter` for persistence/outbox delivery.

Glossary:
- Relay: Thin adapter that normalizes payloads before handing off to emitter.
- Registry validation: Required-property checks against canonical event specs.
"""

from __future__ import annotations

import logging
from typing import Any

from .analytics_event_registry import (
    ANALYTICS_EVENT_REGISTRY,
    missing_required_properties,
)
from .event_emitter import EventEmitter

logger = logging.getLogger(__name__)


# --- Analytics tracking service ---
# Purpose: Centralize analytics event emission and payload normalization.
# Inputs: Event metadata + optional context identifiers and payload properties.
# Outputs: Delegated DomainEvent emission result from EventEmitter.
class AnalyticsTrackingService:
    """Central analytics relay around EventEmitter + event registry."""

    @staticmethod
    def emit(
        event_name: str,
        properties: dict[str, Any] | None = None,
        *,
        organization_id: int | None = None,
        user_id: int | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        correlation_id: str | None = None,
        source: str = "app",
        schema_version: int = 1,
        auto_commit: bool = True,
        include_usage_metrics: bool | None = None,
    ):
        """Validate and relay analytics emission to EventEmitter."""
        name = str(event_name or "").strip()
        payload = dict(properties or {})

        spec = ANALYTICS_EVENT_REGISTRY.get(name)
        if spec is None:
            logger.debug("Analytics event '%s' is not in analytics_event_registry.", name)
        else:
            missing = missing_required_properties(name, payload)
            if missing:
                logger.warning(
                    "Analytics event '%s' missing required properties: %s",
                    name,
                    ", ".join(missing),
                )
                for key in missing:
                    payload.setdefault(key, None)

        return EventEmitter.emit(
            event_name=name,
            properties=payload,
            organization_id=organization_id,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            correlation_id=correlation_id,
            source=source,
            schema_version=schema_version,
            auto_commit=auto_commit,
            include_usage_metrics=include_usage_metrics,
        )

    @staticmethod
    def _coerce_code(value: Any) -> str | None:
        if value is None:
            return None
        parsed = str(value).strip()
        return parsed or None

    @classmethod
    def build_code_usage_properties(
        cls,
        *,
        promo_code: Any = None,
        referral_code: Any = None,
    ) -> dict[str, Any]:
        """Normalize promo/referral metadata into boolean + value properties."""
        normalized_promo = cls._coerce_code(promo_code)
        normalized_ref = cls._coerce_code(referral_code)
        return {
            "used_promo_code": bool(normalized_promo),
            "promo_code": normalized_promo,
            "used_referral_code": bool(normalized_ref),
            "referral_code": normalized_ref,
        }

    @classmethod
    def emit_signup_completed(
        cls,
        *,
        organization_id: int | None,
        user_id: int | None,
        entity_id: int | None,
        signup_source: str,
        signup_flow: str,
        billing_provider: str,
        tier_id: int | str | None,
        is_oauth_signup: bool,
        purchase_completed: bool,
        promo_code: Any = None,
        referral_code: Any = None,
        properties: dict[str, Any] | None = None,
        auto_commit: bool = True,
    ):
        """Emit normalized `signup_completed` with code usage attribution fields."""
        payload = {
            "signup_source": str(signup_source or "direct"),
            "signup_flow": str(signup_flow or "unknown"),
            "billing_provider": str(billing_provider or "unknown"),
            "tier_id": tier_id,
            "is_oauth_signup": bool(is_oauth_signup),
            "purchase_completed": bool(purchase_completed),
            **cls.build_code_usage_properties(
                promo_code=promo_code,
                referral_code=referral_code,
            ),
        }
        if properties:
            payload.update(properties)

        return cls.emit(
            event_name="signup_completed",
            properties=payload,
            organization_id=organization_id,
            user_id=user_id,
            entity_type="organization",
            entity_id=entity_id,
            auto_commit=auto_commit,
        )

    @classmethod
    def emit_checkout_completion_bundle(
        cls,
        *,
        organization_id: int | None,
        user_id: int | None,
        entity_id: int | None,
        completion_properties: dict[str, Any],
    ) -> None:
        """Emit signup + checkout + purchase completion events together."""
        for event_name in (
            "signup_completed",
            "signup_checkout_completed",
            "purchase_completed",
        ):
            cls.emit(
                event_name=event_name,
                properties=completion_properties,
                organization_id=organization_id,
                user_id=user_id,
                entity_type="organization",
                entity_id=entity_id,
                auto_commit=True,
            )

