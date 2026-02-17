import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from flask_login import current_user

from app.models import db
from app.models.domain_event import DomainEvent

logger = logging.getLogger(__name__)


class EventEmitter:
    """Lightweight event emitter that writes to DomainEvent (outbox style)."""

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
    ) -> DomainEvent:
        try:
            # Default tenant/user from session if available
            org_id = organization_id
            usr_id = user_id
            if current_user and getattr(current_user, "is_authenticated", False):
                org_id = org_id or getattr(current_user, "organization_id", None)
                usr_id = usr_id or getattr(current_user, "id", None)

            event = DomainEvent(
                event_name=event_name,
                occurred_at=datetime.now(timezone.utc),
                organization_id=org_id,
                user_id=usr_id,
                entity_type=entity_type,
                entity_id=entity_id,
                correlation_id=correlation_id or str(uuid.uuid4()),
                source=source,
                schema_version=schema_version,
                properties=(properties or {}),
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
