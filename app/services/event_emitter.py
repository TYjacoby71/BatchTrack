import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from flask_login import current_user
from sqlalchemy import func

from app.models import db
from app.models.domain_event import DomainEvent

logger = logging.getLogger(__name__)


class EventEmitter:
    """Lightweight event emitter that writes to DomainEvent (outbox style)."""

    _FIRST_LOGIN_EVENT = "user_login_succeeded"
    _CORE_USAGE_EVENTS = {
        "user_login_succeeded",
        "signup_checkout_started",
        "signup_checkout_completed",
        "purchase_completed",
        "onboarding_completed",
        "inventory_item_created",
        "inventory_item_custom_created",
        "inventory_item_global_created",
        "recipe_created",
        "recipe_variation_created",
        "recipe_test_created",
        "plan_production_requested",
        "stock_check_run",
        "batch_started",
        "batch_completed",
        "timer_started",
    }

    @staticmethod
    def _safe_event_count(*, event_name: str, user_id: int | None, org_id: int | None) -> tuple[int | None, int | None]:
        user_count = None
        org_count = None
        try:
            if user_id:
                user_count = (
                    db.session.query(func.count(DomainEvent.id))
                    .filter(
                        DomainEvent.event_name == event_name,
                        DomainEvent.user_id == int(user_id),
                    )
                    .scalar()
                ) or 0
            if org_id:
                org_count = (
                    db.session.query(func.count(DomainEvent.id))
                    .filter(
                        DomainEvent.event_name == event_name,
                        DomainEvent.organization_id == int(org_id),
                    )
                    .scalar()
                ) or 0
        except Exception:
            user_count = None
            org_count = None
        return user_count, org_count

    @staticmethod
    def _first_login_at(user_id: int | None) -> datetime | None:
        if not user_id:
            return None
        try:
            return (
                db.session.query(func.min(DomainEvent.occurred_at))
                .filter(
                    DomainEvent.user_id == int(user_id),
                    DomainEvent.event_name == EventEmitter._FIRST_LOGIN_EVENT,
                )
                .scalar()
            )
        except Exception:
            return None

    @staticmethod
    def _enrich_usage_properties(
        *,
        event_name: str,
        user_id: int | None,
        org_id: int | None,
        properties: Dict[str, Any],
        occurred_at: datetime,
    ) -> Dict[str, Any]:
        enriched = dict(properties or {})
        user_count, org_count = EventEmitter._safe_event_count(
            event_name=event_name,
            user_id=user_id,
            org_id=org_id,
        )

        if user_count is not None:
            user_use_index = int(user_count) + 1
            enriched["user_use_index"] = user_use_index
            enriched["is_first_user_use"] = user_use_index == 1
            enriched["is_second_user_use"] = user_use_index == 2

        if org_count is not None:
            org_use_index = int(org_count) + 1
            enriched["org_use_index"] = org_use_index
            enriched["is_first_org_use"] = org_use_index == 1
            enriched["is_second_org_use"] = org_use_index == 2

        first_login_at = EventEmitter._first_login_at(user_id)
        if first_login_at:
            elapsed = (occurred_at - first_login_at).total_seconds()
            enriched["seconds_since_first_login"] = max(0, int(elapsed))
            enriched["first_login_observed_at"] = first_login_at.isoformat()
        elif event_name == EventEmitter._FIRST_LOGIN_EVENT and user_id:
            enriched["seconds_since_first_login"] = 0
            enriched["first_login_observed_at"] = occurred_at.isoformat()

        return enriched

    @staticmethod
    def emit(
        event_name: str,
        properties: Optional[Dict[str, Any]] = None,
        *,
        organization_id: Optional[int] = None,
        user_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        correlation_id: Optional[str] = None,
        source: str = "app",
        schema_version: int = 1,
        auto_commit: bool = True,
        include_usage_metrics: Optional[bool] = None,
    ) -> DomainEvent:
        try:
            # Default tenant/user from session if available
            org_id = organization_id
            usr_id = user_id
            if current_user and getattr(current_user, "is_authenticated", False):
                org_id = org_id or getattr(current_user, "organization_id", None)
                usr_id = usr_id or getattr(current_user, "id", None)

            occurred_at = datetime.now(timezone.utc)
            include_metrics = (
                event_name in EventEmitter._CORE_USAGE_EVENTS
                if include_usage_metrics is None
                else bool(include_usage_metrics)
            )
            payload = dict(properties or {})
            if include_metrics:
                payload = EventEmitter._enrich_usage_properties(
                    event_name=event_name,
                    user_id=usr_id,
                    org_id=org_id,
                    properties=payload,
                    occurred_at=occurred_at,
                )

            event = DomainEvent(
                event_name=event_name,
                occurred_at=occurred_at,
                organization_id=org_id,
                user_id=usr_id,
                entity_type=entity_type,
                entity_id=entity_id,
                correlation_id=correlation_id or str(uuid.uuid4()),
                source=source,
                schema_version=schema_version,
                properties=payload,
                is_processed=False,
                delivery_attempts=0,
            )

            db.session.add(event)
            if auto_commit:
                db.session.commit()

            return event

        except Exception as e:
            logger.error(f"Failed to emit event {event_name}: {e}")
            # We must not crash the request; swallow after logging and keep transaction safe
            try:
                db.session.rollback()
            except Exception:
                pass
            return None
