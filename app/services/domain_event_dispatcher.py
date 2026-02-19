"""Domain event outbox dispatcher.

Synopsis:
Dispatches pending DomainEvent rows to an external webhook endpoint.

Glossary:
- Outbox: Persisted events queued for delivery.
- Dispatcher: Worker that sends events to external systems.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import requests
from flask import current_app, has_app_context
from sqlalchemy import select

from app.extensions import db
from app.models.domain_event import DomainEvent

logger = logging.getLogger(__name__)


# --- DomainEventDispatcher ---
# Purpose: Deliver queued domain events to external webhooks.
class DomainEventDispatcher:
    """Outbox dispatcher for processing DomainEvent records asynchronously."""

    def __init__(
        self,
        *,
        webhook_url: Optional[str] = None,
        batch_size: int = 100,
        max_retry_attempts: int = 6,
    ) -> None:
        if webhook_url:
            self.webhook_url = webhook_url
        elif has_app_context():
            self.webhook_url = current_app.config.get("DOMAIN_EVENT_WEBHOOK_URL")
        else:
            self.webhook_url = None
        if has_app_context():
            self.posthog_api_key = (
                current_app.config.get("POSTHOG_PROJECT_API_KEY") or ""
            ).strip() or None
            self.posthog_host = (
                current_app.config.get("POSTHOG_HOST") or "https://us.i.posthog.com"
            ).rstrip("/")
        else:
            self.posthog_api_key = None
            self.posthog_host = None
        self.posthog_enabled = bool(self.posthog_api_key and self.posthog_host)
        self.batch_size = max(1, batch_size)
        self.max_retry_attempts = max_retry_attempts

    def dispatch_pending_events(
        self, *, batch_size: Optional[int] = None
    ) -> Dict[str, int]:
        """Dispatch a batch of pending events and return processing metrics."""
        limit = max(1, batch_size or self.batch_size)
        processed = 0
        succeeded = 0
        failed = 0

        try:
            stmt = (
                select(DomainEvent)
                .where(DomainEvent.is_processed.is_(False))
                .order_by(DomainEvent.id.asc())
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            events = db.session.execute(stmt).scalars().all()
        except Exception:
            logger.exception("Failed to load pending domain events")
            db.session.rollback()
            return {"processed": 0, "succeeded": 0, "failed": 0}

        if not events:
            db.session.rollback()
            return {"processed": 0, "succeeded": 0, "failed": 0}

        now_utc = datetime.now(timezone.utc)

        for event in events:
            processed += 1
            try:
                delivered = self._deliver_event(event)
            except Exception:
                logger.exception(
                    "Domain event delivery raised unexpectedly",
                    extra={"event_id": event.id},
                )
                delivered = False

            if delivered:
                succeeded += 1
                event.is_processed = True
                event.processed_at = now_utc
            else:
                failed += 1
                event.delivery_attempts = (event.delivery_attempts or 0) + 1
                if (
                    self.max_retry_attempts
                    and event.delivery_attempts >= self.max_retry_attempts
                ):
                    logger.error(
                        "Domain event %s exceeded max retry attempts (%s). Marking as processed.",
                        event.id,
                        self.max_retry_attempts,
                    )
                    event.is_processed = True
                    event.processed_at = now_utc
                    props = dict(event.properties or {})
                    errors = list(props.get("_dispatch_errors", []))
                    errors.append("max_retry_exceeded")
                    props["_dispatch_errors"] = errors
                    event.properties = props

        try:
            db.session.commit()
        except Exception:
            logger.exception("Failed to commit domain event dispatch results")
            db.session.rollback()
        finally:
            db.session.close()

        return {"processed": processed, "succeeded": succeeded, "failed": failed}

    def run_forever(
        self, *, poll_interval: float = 5.0, batch_size: Optional[int] = None
    ) -> None:
        """Continuously dispatch events until interrupted."""
        interval = max(0.5, poll_interval)
        logger.info(
            "DomainEventDispatcher started (webhook=%s, batch_size=%s, poll_interval=%ss)",
            bool(self.webhook_url),
            batch_size or self.batch_size,
            interval,
        )

        try:
            while True:
                metrics = self.dispatch_pending_events(batch_size=batch_size)
                if metrics["processed"] == 0:
                    time.sleep(interval)
                else:
                    # When work was done, poll sooner for backlog, but avoid busy spin.
                    time.sleep(min(interval, 1.0))
        except KeyboardInterrupt:
            logger.info("DomainEventDispatcher interrupted; shutting down cleanly")

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------

    def _deliver_event(self, event: DomainEvent) -> bool:
        """Deliver the event to configured sinks."""
        if not self.webhook_url and not self.posthog_enabled:
            logger.debug(
                "No domain-event sinks configured; marking event %s as processed.",
                event.id,
            )
            return True

        sink_results: list[bool] = []
        if self.webhook_url:
            sink_results.append(self._deliver_webhook(event))
        if self.posthog_enabled:
            sink_results.append(self._deliver_to_posthog(event))
        return all(sink_results) if sink_results else True

    @staticmethod
    def _build_payload(event: DomainEvent) -> Dict[str, Any]:
        return {
            "id": event.id,
            "event_name": event.event_name,
            "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
            "organization_id": event.organization_id,
            "user_id": event.user_id,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "correlation_id": event.correlation_id,
            "source": event.source,
            "schema_version": event.schema_version,
            "properties": event.properties or {},
        }

    def _deliver_webhook(self, event: DomainEvent) -> bool:
        payload = self._build_payload(event)
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=5)
            response.raise_for_status()
            logger.debug("Domain event %s delivered to webhook", event.id)
            return True
        except requests.RequestException as exc:
            logger.warning(
                "Domain event %s webhook delivery failed: %s",
                event.id,
                exc,
                extra={"status_code": getattr(exc.response, "status_code", None)},
            )
            return False

    def _deliver_to_posthog(self, event: DomainEvent) -> bool:
        try:
            distinct_id = (
                str(event.user_id)
                if event.user_id
                else (
                    f"org:{event.organization_id}"
                    if event.organization_id
                    else f"domain_event:{event.id}"
                )
            )
            properties = dict(event.properties or {})
            properties.setdefault("organization_id", event.organization_id)
            properties.setdefault("entity_type", event.entity_type)
            properties.setdefault("entity_id", event.entity_id)
            properties.setdefault("source", event.source)
            properties.setdefault("schema_version", event.schema_version)
            properties.setdefault("domain_event_id", event.id)
            properties.setdefault("correlation_id", event.correlation_id)
            if event.organization_id:
                groups = properties.get("$groups")
                if not isinstance(groups, dict):
                    groups = {}
                groups.setdefault("organization", str(event.organization_id))
                properties["$groups"] = groups

            payload = {
                "api_key": self.posthog_api_key,
                "event": event.event_name,
                "distinct_id": distinct_id,
                "timestamp": (
                    event.occurred_at.isoformat() if event.occurred_at else None
                ),
                "properties": properties,
            }
            endpoint = urljoin(f"{self.posthog_host}/", "capture/")
            response = requests.post(endpoint, json=payload, timeout=5)
            response.raise_for_status()
            logger.debug("Domain event %s delivered to PostHog", event.id)
            return True
        except requests.RequestException as exc:
            logger.warning(
                "Domain event %s PostHog delivery failed: %s",
                event.id,
                exc,
                extra={"status_code": getattr(exc.response, "status_code", None)},
            )
            return False
