"""Marketing lead capture and query helpers.

Synopsis:
Persists normalized marketing contacts and source-keyed capture events so
multiple waitlist/marketing sources can be tracked in one DB-backed surface.

Glossary:
- Waitlist capture: A lead event created from waitlist or quiz email collection.
- Source key: Normalized payload field used for filtering by traffic channel.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from app.extensions import db
from app.models.marketing_lead import MarketingContact, MarketingLeadEvent

logger = logging.getLogger(__name__)


class MarketingLeadService:
    """Service helpers for DB-backed marketing lead capture."""

    WAITLIST_EVENT_TYPE = "waitlist_join"
    _DEFAULT_SOURCE_KEY = "waitlist"
    _DEFAULT_CONTEXT = "public_site"

    @staticmethod
    def _normalize_email(raw_value: Optional[str]) -> Optional[str]:
        if not raw_value or not isinstance(raw_value, str):
            return None
        normalized = raw_value.strip().lower()
        return normalized or None

    @staticmethod
    def _normalize_key(raw_value: Optional[str], *, fallback: str) -> str:
        if not raw_value or not isinstance(raw_value, str):
            return fallback
        cleaned = raw_value.strip().lower()
        cleaned = re.sub(r"[^a-z0-9._:-]+", "_", cleaned)
        cleaned = cleaned.strip("._:-")
        return cleaned or fallback

    @staticmethod
    def _safe_str(raw_value: Any) -> Optional[str]:
        if raw_value is None:
            return None
        text = str(raw_value).strip()
        return text or None

    @classmethod
    def record_waitlist_capture(
        cls,
        *,
        email: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        business_type: Optional[str] = None,
        source_key: Optional[str] = None,
        waitlist_key: Optional[str] = None,
        context: Optional[str] = None,
        notes: Optional[str] = None,
        tags: Optional[List[str]] = None,
        payload: Optional[Dict[str, Any]] = None,
        organization_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> bool:
        """Persist a waitlist capture event with normalized source metadata."""
        normalized_email = cls._normalize_email(email)
        if not normalized_email:
            return False

        normalized_source = cls._normalize_key(
            source_key, fallback=cls._DEFAULT_SOURCE_KEY
        )
        normalized_waitlist_key = cls._normalize_key(
            waitlist_key or source_key,
            fallback=cls._DEFAULT_SOURCE_KEY,
        )
        normalized_context = cls._normalize_key(context, fallback=cls._DEFAULT_CONTEXT)

        first_name_value = cls._safe_str(first_name)
        last_name_value = cls._safe_str(last_name)
        business_type_value = cls._safe_str(business_type)
        notes_value = cls._safe_str(notes)
        tags_value = [str(tag).strip() for tag in (tags or []) if str(tag).strip()]
        payload_value = payload if isinstance(payload, dict) else {}

        try:
            contact = MarketingContact.query.filter_by(
                email_normalized=normalized_email
            ).first()
            if contact is None:
                contact = MarketingContact(
                    email=normalized_email,
                    email_normalized=normalized_email,
                    first_name=first_name_value,
                    last_name=last_name_value,
                    business_type=business_type_value,
                    traits_json={},
                )
                db.session.add(contact)
            else:
                contact.email = normalized_email
                if first_name_value and not contact.first_name:
                    contact.first_name = first_name_value
                if last_name_value and not contact.last_name:
                    contact.last_name = last_name_value
                if business_type_value and (
                    not contact.business_type
                    or contact.business_type.lower()
                    in {"not_specified", "not specified"}
                ):
                    contact.business_type = business_type_value

            existing_traits = (
                contact.traits_json if isinstance(contact.traits_json, dict) else {}
            )
            merged_traits = {
                **existing_traits,
                "last_source_key": normalized_source,
                "last_waitlist_key": normalized_waitlist_key,
                "last_context": normalized_context,
            }
            contact.traits_json = merged_traits

            event = MarketingLeadEvent(
                contact=contact,
                organization_id=organization_id,
                user_id=user_id,
                event_type=cls.WAITLIST_EVENT_TYPE,
                source_key=normalized_source,
                waitlist_key=normalized_waitlist_key,
                context=normalized_context,
                notes=notes_value,
                tags_json=tags_value,
                payload_json=payload_value,
            )
            db.session.add(event)
            db.session.commit()
            return True
        except Exception:
            logger.warning(
                "Suppressed exception fallback at app/services/marketing_lead_service.py:133",
                exc_info=True,
            )
            db.session.rollback()
            return False

    @classmethod
    def waitlist_capture_exists(
        cls,
        *,
        email: str,
        waitlist_key: Optional[str] = None,
    ) -> bool:
        """Check whether a waitlist capture already exists for email + waitlist key."""
        normalized_email = cls._normalize_email(email)
        if not normalized_email:
            return False

        normalized_waitlist_key = cls._normalize_key(
            waitlist_key,
            fallback=cls._DEFAULT_SOURCE_KEY,
        )

        try:
            contact = MarketingContact.query.filter_by(
                email_normalized=normalized_email
            ).first()
            if contact is None:
                return False

            events = MarketingLeadEvent.query.filter_by(
                contact_id=contact.id,
                event_type=cls.WAITLIST_EVENT_TYPE,
            ).all()
            for event in events:
                event_waitlist_key = cls._normalize_key(
                    event.waitlist_key or event.source_key,
                    fallback=cls._DEFAULT_SOURCE_KEY,
                )
                if event_waitlist_key == normalized_waitlist_key:
                    return True
            return False
        except Exception:
            logger.warning(
                "Suppressed exception fallback at app/services/marketing_lead_service.py:185",
                exc_info=True,
            )
            return False

    @classmethod
    def fetch_waitlist_rows(cls) -> List[Dict[str, Any]]:
        """Return waitlist rows shaped like legacy JSON entries."""
        try:
            rows = (
                db.session.query(MarketingLeadEvent, MarketingContact)
                .join(
                    MarketingContact,
                    MarketingLeadEvent.contact_id == MarketingContact.id,
                )
                .filter(MarketingLeadEvent.event_type == cls.WAITLIST_EVENT_TYPE)
                .order_by(
                    MarketingLeadEvent.occurred_at.desc(), MarketingLeadEvent.id.desc()
                )
                .all()
            )
        except Exception:
            logger.warning(
                "Suppressed exception fallback at app/services/marketing_lead_service.py:151",
                exc_info=True,
            )
            return []

        waitlist_rows: List[Dict[str, Any]] = []
        for event, contact in rows:
            payload = event.payload_json if isinstance(event.payload_json, dict) else {}
            first_name = (
                cls._safe_str(payload.get("first_name")) or contact.first_name or ""
            )
            last_name = (
                cls._safe_str(payload.get("last_name")) or contact.last_name or ""
            )
            business_type = (
                cls._safe_str(payload.get("business_type"))
                or cls._safe_str(contact.business_type)
                or "not_specified"
            )

            timestamp = (
                event.occurred_at.isoformat() if event.occurred_at is not None else None
            ) or (
                event.created_at.isoformat() if event.created_at is not None else None
            )
            source_key = (
                cls._safe_str(event.source_key)
                or cls._safe_str(payload.get("source"))
                or cls._DEFAULT_SOURCE_KEY
            )
            waitlist_key = (
                cls._safe_str(event.waitlist_key)
                or cls._safe_str(payload.get("waitlist_key"))
                or source_key
            )
            context = (
                cls._safe_str(event.context)
                or cls._safe_str(payload.get("context"))
                or cls._DEFAULT_CONTEXT
            )
            notes = (
                cls._safe_str(event.notes) or cls._safe_str(payload.get("notes")) or ""
            )
            tags = (
                event.tags_json
                if isinstance(event.tags_json, list)
                else payload.get("tags", [])
            )

            waitlist_rows.append(
                {
                    "email": contact.email_normalized,
                    "first_name": first_name,
                    "last_name": last_name,
                    "business_type": business_type,
                    "timestamp": timestamp,
                    "source": source_key,
                    "waitlist_key": waitlist_key,
                    "context": context,
                    "notes": notes,
                    "tags": tags if isinstance(tags, list) else [],
                }
            )

        return waitlist_rows
