"""Analytics tracking facade.

Synopsis:
Provides a centralized, registry-backed relay for analytics emission.
Feature modules call semantic helper methods instead of constructing low-level
event payloads inline.

Glossary:
- Relay: Adapter that validates and forwards events to the outbox emitter.
- Registry validation: Guardrails ensuring only known event names are emitted.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from .analytics_event_registry import ANALYTICS_EVENT_REGISTRY, missing_required_properties
from .event_emitter import EventEmitter

logger = logging.getLogger(__name__)


class AnalyticsTrackingService:
    """Central analytics relay around EventEmitter + event registry."""

    @staticmethod
    def _normalize_seconds(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_code(value: Any) -> str | None:
        if value is None:
            return None
        parsed = str(value).strip()
        return parsed or None

    @staticmethod
    def _merge_properties(
        base: dict[str, Any], extra: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        payload = dict(base or {})
        if extra:
            payload.update(dict(extra))
        return payload

    @classmethod
    def emit(
        cls,
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
        if not name:
            return None

        spec = ANALYTICS_EVENT_REGISTRY.get(name)
        if spec is None:
            logger.error(
                "Blocked unregistered analytics event '%s'. Add it to analytics_event_registry.",
                name,
            )
            return None

        payload = dict(properties or {})
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

    @classmethod
    def emit_from_payload(cls, payload: Mapping[str, Any], *, auto_commit: bool = True):
        """Relay an event payload dictionary with EventEmitter-compatible keys."""
        if not payload:
            return None
        return cls.emit(
            event_name=str(payload.get("event_name") or ""),
            properties=dict(payload.get("properties") or {}),
            organization_id=payload.get("organization_id"),
            user_id=payload.get("user_id"),
            entity_type=payload.get("entity_type"),
            entity_id=payload.get("entity_id"),
            correlation_id=payload.get("correlation_id"),
            source=payload.get("source") or "app",
            schema_version=int(payload.get("schema_version") or 1),
            auto_commit=auto_commit,
            include_usage_metrics=payload.get("include_usage_metrics"),
        )

    @classmethod
    def build_code_usage_properties(
        cls,
        *,
        promo_code: Any = None,
        referral_code: Any = None,
    ) -> dict[str, Any]:
        normalized_promo = cls._coerce_code(promo_code)
        normalized_ref = cls._coerce_code(referral_code)
        return {
            "used_promo_code": bool(normalized_promo),
            "promo_code": normalized_promo,
            "used_referral_code": bool(normalized_ref),
            "referral_code": normalized_ref,
        }

    @classmethod
    def track_user_login_succeeded(
        cls,
        *,
        organization_id: int | None,
        user_id: int | None,
        is_first_login: bool,
        login_method: str,
        destination_hint: str,
        seconds_since_first_landing: int | None = None,
        extra_properties: Mapping[str, Any] | None = None,
    ):
        props = {
            "is_first_login": bool(is_first_login),
            "login_method": str(login_method or "unknown"),
            "destination_hint": str(destination_hint or "unknown"),
        }
        elapsed = cls._normalize_seconds(seconds_since_first_landing)
        if elapsed is not None:
            props["seconds_since_first_landing"] = elapsed
        props = cls._merge_properties(props, extra_properties)
        return cls.emit(
            event_name="user_login_succeeded",
            properties=props,
            organization_id=organization_id,
            user_id=user_id,
            entity_type="user",
            entity_id=user_id,
        )

    @classmethod
    def track_signup_checkout_started(
        cls,
        *,
        pending_signup_id: int,
        tier_id: str | int | None,
        billing_mode: str,
        billing_cycle: str,
        signup_source: str,
        is_oauth_signup: bool,
        seconds_since_first_landing: int | None = None,
    ):
        props = {
            "pending_signup_id": pending_signup_id,
            "tier_id": str(tier_id or ""),
            "billing_mode": str(billing_mode or ""),
            "billing_cycle": str(billing_cycle or ""),
            "signup_source": str(signup_source or "direct"),
            "is_oauth_signup": bool(is_oauth_signup),
        }
        elapsed = cls._normalize_seconds(seconds_since_first_landing)
        if elapsed is not None:
            props["seconds_since_first_landing"] = elapsed
        return cls.emit(event_name="signup_checkout_started", properties=props)

    @classmethod
    def track_billing_checkout_started(
        cls,
        *,
        organization_id: int | None,
        user_id: int | None,
        tier: str | int,
        billing_cycle: str,
        checkout_provider: str = "stripe",
        seconds_since_first_landing: int | None = None,
    ):
        props = {
            "tier": str(tier),
            "billing_cycle": str(billing_cycle or ""),
            "checkout_provider": str(checkout_provider or "stripe"),
        }
        elapsed = cls._normalize_seconds(seconds_since_first_landing)
        if elapsed is not None:
            props["seconds_since_first_landing"] = elapsed
        return cls.emit(
            event_name="billing_checkout_started",
            properties=props,
            organization_id=organization_id,
            user_id=user_id,
            entity_type="organization",
            entity_id=organization_id,
        )

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
        payload = cls._merge_properties(payload, properties)
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
    def track_signup_completed(
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
        """Alias using `track_*` naming for signup completion."""
        return cls.emit_signup_completed(
            organization_id=organization_id,
            user_id=user_id,
            entity_id=entity_id,
            signup_source=signup_source,
            signup_flow=signup_flow,
            billing_provider=billing_provider,
            tier_id=tier_id,
            is_oauth_signup=is_oauth_signup,
            purchase_completed=purchase_completed,
            promo_code=promo_code,
            referral_code=referral_code,
            properties=properties,
            auto_commit=auto_commit,
        )

    @classmethod
    def track_billing_stripe_checkout_completed(
        cls,
        *,
        organization_id: int | None,
        user_id: int | None,
        pending_signup_id: int,
        tier_id: int | str | None,
        checkout_session_id: str | None,
        stripe_customer_id: str | None,
    ):
        return cls.emit(
            event_name="billing.stripe_checkout_completed",
            organization_id=organization_id,
            user_id=user_id,
            properties={
                "pending_signup_id": pending_signup_id,
                "tier_id": tier_id,
                "checkout_session_id": checkout_session_id,
                "stripe_customer_id": stripe_customer_id,
            },
            auto_commit=True,
        )

    @classmethod
    def track_onboarding_completed(
        cls,
        *,
        organization_id: int | None,
        user_id: int | None,
        team_size: int,
        requires_password_setup: bool,
        checklist_completed: bool = True,
        seconds_since_first_landing: int | None = None,
    ):
        props = {
            "checklist_completed": bool(checklist_completed),
            "requires_password_setup": bool(requires_password_setup),
            "team_size": int(team_size or 0),
        }
        elapsed = cls._normalize_seconds(seconds_since_first_landing)
        if elapsed is not None:
            props["seconds_since_first_landing"] = elapsed
        return cls.emit(
            event_name="onboarding_completed",
            properties=props,
            organization_id=organization_id,
            user_id=user_id,
            entity_type="organization",
            entity_id=organization_id,
        )

    @classmethod
    def track_plan_production_requested(
        cls,
        *,
        organization_id: int | None,
        user_id: int | None,
        recipe_id: int,
        scale: float,
        container_id: int | None,
        success: bool,
        all_available: bool,
        issue_count: int,
    ):
        return cls.emit(
            event_name="plan_production_requested",
            properties={
                "recipe_id": recipe_id,
                "scale": scale,
                "container_id": container_id,
                "success": bool(success),
                "all_available": bool(all_available),
                "issue_count": int(issue_count or 0),
            },
            organization_id=organization_id,
            user_id=user_id,
            entity_type="recipe",
            entity_id=recipe_id,
        )

    @classmethod
    def track_stock_check_run(
        cls,
        *,
        organization_id: int | None,
        user_id: int | None,
        recipe_id: int,
        scale: float,
        success: bool,
        stock_item_count: int,
    ):
        return cls.emit(
            event_name="stock_check_run",
            properties={
                "recipe_id": recipe_id,
                "scale": scale,
                "success": bool(success),
                "stock_item_count": int(stock_item_count or 0),
            },
            organization_id=organization_id,
            user_id=user_id,
            entity_type="recipe",
            entity_id=recipe_id,
        )

    @classmethod
    def track_inventory_item_creation_events(
        cls,
        *,
        organization_id: int | None,
        user_id: int | None,
        entity_id: int,
        item_type: str,
        unit: str,
        creation_source: str,
        global_item_id: int | None,
        is_tracked: bool,
        initial_quantity: float,
        auto_commit: bool = True,
    ) -> None:
        payload = {
            "item_type": item_type,
            "unit": unit,
            "creation_source": creation_source,
            "global_item_id": global_item_id,
            "is_tracked": bool(is_tracked),
            "initial_quantity": float(initial_quantity or 0.0),
        }
        cls.emit(
            event_name="inventory_item_created",
            properties=payload,
            organization_id=organization_id,
            user_id=user_id,
            entity_type="inventory_item",
            entity_id=entity_id,
            auto_commit=auto_commit,
        )
        source_event = (
            "inventory_item_global_created"
            if creation_source == "global"
            else "inventory_item_custom_created"
        )
        cls.emit(
            event_name=source_event,
            properties=payload,
            organization_id=organization_id,
            user_id=user_id,
            entity_type="inventory_item",
            entity_id=entity_id,
            auto_commit=auto_commit,
        )

    @classmethod
    def track_recipe_created_events(
        cls,
        *,
        organization_id: int | None,
        user_id: int | None,
        recipe_id: int,
        properties: Mapping[str, Any],
        is_test: bool,
        is_variation: bool,
    ) -> None:
        payload = dict(properties or {})
        cls.emit(
            event_name="recipe_created",
            properties=payload,
            organization_id=organization_id,
            user_id=user_id,
            entity_type="recipe",
            entity_id=recipe_id,
        )
        if is_test:
            cls.emit(
                event_name="recipe_test_created",
                properties=payload,
                organization_id=organization_id,
                user_id=user_id,
                entity_type="recipe",
                entity_id=recipe_id,
            )
        elif is_variation:
            cls.emit(
                event_name="recipe_variation_created",
                properties=payload,
                organization_id=organization_id,
                user_id=user_id,
                entity_type="recipe",
                entity_id=recipe_id,
            )

    @classmethod
    def track_recipe_lifecycle_event(
        cls,
        *,
        event_name: str,
        organization_id: int | None,
        user_id: int | None,
        recipe_id: int,
        properties: Mapping[str, Any] | None = None,
    ):
        return cls.emit(
            event_name=event_name,
            properties=dict(properties or {}),
            organization_id=organization_id,
            user_id=user_id,
            entity_type="recipe",
            entity_id=recipe_id,
        )

    @classmethod
    def track_batch_lifecycle_event(
        cls,
        *,
        event_name: str,
        organization_id: int | None,
        user_id: int | None,
        batch_id: int,
        properties: Mapping[str, Any] | None = None,
    ):
        return cls.emit(
            event_name=event_name,
            properties=dict(properties or {}),
            organization_id=organization_id,
            user_id=user_id,
            entity_type="batch",
            entity_id=batch_id,
        )

    @classmethod
    def track_timer_event(
        cls,
        *,
        event_name: str,
        organization_id: int | None,
        user_id: int | None,
        timer_id: int,
        properties: Mapping[str, Any] | None = None,
    ):
        return cls.emit(
            event_name=event_name,
            properties=dict(properties or {}),
            organization_id=organization_id,
            user_id=user_id,
            entity_type="timer",
            entity_id=timer_id,
        )

    @classmethod
    def track_product_event(
        cls,
        *,
        event_name: str,
        organization_id: int | None,
        user_id: int | None,
        entity_type: str,
        entity_id: int,
        properties: Mapping[str, Any] | None = None,
    ):
        return cls.emit(
            event_name=event_name,
            properties=dict(properties or {}),
            organization_id=organization_id,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
        )

    @classmethod
    def track_global_item_event(
        cls,
        *,
        event_name: str,
        user_id: int | None,
        entity_id: int,
        properties: Mapping[str, Any] | None = None,
    ):
        return cls.emit(
            event_name=event_name,
            properties=dict(properties or {}),
            user_id=user_id,
            entity_type="global_item",
            entity_id=entity_id,
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

