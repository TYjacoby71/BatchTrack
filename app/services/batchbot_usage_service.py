from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from flask import current_app

from ..extensions import db
from ..models import BatchBotUsage, Organization, User
from ..utils.timezone_utils import TimezoneUtils
from .batchbot_credit_service import BatchBotCreditService


class BatchBotLimitError(RuntimeError):
    """Raised when an organization exceeds its BatchBot quota."""

    def __init__(
        self,
        *,
        allowed: int | None,
        used: int,
        window_end: date,
        credits_remaining: int = 0,
    ):
        super().__init__("BatchBot request limit reached for the current window.")
        self.allowed = allowed
        self.used = used
        self.window_end = window_end
        self.credits_remaining = credits_remaining


class BatchBotChatLimitError(RuntimeError):
    """Raised when chat-only allowance is exhausted."""

    def __init__(self, *, limit: int | None, used: int, window_end: date):
        super().__init__("Chat allowance reached for this window.")
        self.limit = limit
        self.used = used
        self.window_end = window_end


@dataclass(slots=True)
class BatchBotUsageSnapshot:
    allowed: Optional[int]
    used: int
    remaining: Optional[int]
    window_start: date
    window_end: date
    chat_limit: Optional[int]
    chat_used: int
    chat_remaining: Optional[int]


class BatchBotUsageService:
    """Encapsulates monthly (or configurable) usage metering for BatchBot."""

    @staticmethod
    def get_usage_snapshot(org: Organization) -> BatchBotUsageSnapshot:
        limits = BatchBotUsageService._resolve_limit(org)
        allowed = limits
        window_start, window_end = BatchBotUsageService._window_bounds()

        record = BatchBotUsage.query.filter_by(
            organization_id=org.id,
            window_start=window_start,
        ).first()

        metadata = (
            record.details
            if isinstance(record, BatchBotUsage) and isinstance(record.details, dict)
            else {}
        )
        used = record.request_count if record else 0
        remaining = None if allowed is None or allowed < 0 else max(allowed - used, 0)

        chat_limit = BatchBotUsageService._resolve_chat_limit()
        chat_used = int((metadata or {}).get("chat_messages", 0) or 0)
        chat_remaining = (
            None
            if chat_limit is None or chat_limit < 0
            else max(chat_limit - chat_used, 0)
        )

        return BatchBotUsageSnapshot(
            allowed=allowed,
            used=used,
            remaining=remaining,
            window_start=window_start,
            window_end=window_end,
            chat_limit=chat_limit,
            chat_used=chat_used,
            chat_remaining=chat_remaining,
        )

    @staticmethod
    def ensure_within_limit(org: Organization) -> None:
        limits = BatchBotUsageService.get_usage_snapshot(org)
        if limits.allowed is None or limits.allowed < 0:
            return
        if limits.used < limits.allowed:
            return
        credits_available = BatchBotCreditService.available_credits(org)
        if credits_available > 0:
            return
        raise BatchBotLimitError(
            allowed=limits.allowed,
            used=limits.used,
            window_end=limits.window_end,
            credits_remaining=credits_available,
        )

    @staticmethod
    def record_request(
        *,
        org: Organization,
        user: User,
        metadata: Optional[dict] = None,
        delta: int = 1,
    ) -> BatchBotUsageSnapshot:
        BatchBotUsageService.ensure_within_limit(org)

        allowed = BatchBotUsageService._resolve_limit(org)
        window_start, window_end = BatchBotUsageService._window_bounds()

        record = BatchBotUsage.query.filter_by(
            organization_id=org.id,
            window_start=window_start,
        ).first()

        if record is None:
            record = BatchBotUsage(
                organization_id=org.id,
                user_id=user.id if user else None,
                window_start=window_start,
                window_end=window_end,
                request_count=0,
                details={"limit": allowed, "credits_consumed": 0, "chat_messages": 0},
            )
            db.session.add(record)

        record.increment(delta=delta, metadata=metadata)

        metadata_dict = record.details if isinstance(record.details, dict) else {}
        credits_consumed = int(metadata_dict.get("credits_consumed", 0) or 0)
        chat_messages = int(metadata_dict.get("chat_messages", 0) or 0)

        if allowed is not None and allowed >= 0:
            overage = max(record.request_count - allowed, 0)
            new_credit_need = max(overage - credits_consumed, 0)
            if new_credit_need > 0:
                BatchBotCreditService.consume(org, new_credit_need)
                credits_consumed += new_credit_need
                metadata_dict.update(
                    {
                        "limit": allowed,
                        "credits_consumed": credits_consumed,
                        "chat_messages": chat_messages,
                    }
                )
                record.details = metadata_dict

        db.session.commit()

        remaining = (
            None
            if allowed is None or allowed < 0
            else max(allowed - record.request_count, 0)
        )
        chat_limit = BatchBotUsageService._resolve_chat_limit()
        chat_remaining = (
            None
            if chat_limit is None or chat_limit < 0
            else max(chat_limit - chat_messages, 0)
        )

        return BatchBotUsageSnapshot(
            allowed=allowed,
            used=record.request_count,
            remaining=remaining,
            window_start=window_start,
            window_end=window_end,
            chat_limit=chat_limit,
            chat_used=chat_messages,
            chat_remaining=chat_remaining,
        )

    @staticmethod
    def record_chat(
        *, org: Organization, user: User | None, delta: int = 1
    ) -> BatchBotUsageSnapshot:
        BatchBotUsageService._ensure_chat_quota(org, delta=delta)

        allowed = BatchBotUsageService._resolve_limit(org)
        window_start, window_end = BatchBotUsageService._window_bounds()

        record = BatchBotUsage.query.filter_by(
            organization_id=org.id,
            window_start=window_start,
        ).first()

        if record is None:
            record = BatchBotUsage(
                organization_id=org.id,
                user_id=user.id if user else None,
                window_start=window_start,
                window_end=window_end,
                request_count=0,
                details={"limit": allowed, "credits_consumed": 0, "chat_messages": 0},
            )
            db.session.add(record)

        metadata_dict = record.details if isinstance(record.details, dict) else {}
        chat_messages = int(metadata_dict.get("chat_messages", 0) or 0)
        metadata_dict["chat_messages"] = chat_messages + max(delta, 0)
        metadata_dict.setdefault("limit", allowed)
        metadata_dict.setdefault("credits_consumed", 0)
        record.details = metadata_dict

        db.session.commit()
        return BatchBotUsageService.get_usage_snapshot(org)

    @staticmethod
    def _window_bounds(now: Optional[datetime] = None) -> tuple[date, date]:
        now = now or TimezoneUtils.utc_now()
        window_days = max(
            1, int(current_app.config.get("BATCHBOT_REQUEST_WINDOW_DAYS", 30))
        )

        epoch = date(2024, 1, 1)
        delta_days = (now.date() - epoch).days
        bucket_index = delta_days // window_days
        window_start = epoch + timedelta(days=bucket_index * window_days)
        window_end = window_start + timedelta(days=window_days)
        return window_start, window_end

    @staticmethod
    def _resolve_limit(org: Organization) -> Optional[int]:
        tier_limit = None
        if org and org.tier:
            tier_limit = getattr(org.tier, "max_batchbot_requests", None)

        if tier_limit is not None:
            return tier_limit

        default_limit = current_app.config.get("BATCHBOT_DEFAULT_MAX_REQUESTS")
        return int(default_limit) if default_limit is not None else 0

    @staticmethod
    def _resolve_chat_limit() -> Optional[int]:
        limit = current_app.config.get("BATCHBOT_CHAT_MAX_MESSAGES")
        if limit is None:
            return None
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 0
        return limit

    @staticmethod
    def _ensure_chat_quota(org: Organization, *, delta: int = 1) -> None:
        limit = BatchBotUsageService._resolve_chat_limit()
        if limit is None or limit < 0:
            return
        snapshot = BatchBotUsageService.get_usage_snapshot(org)
        projected = snapshot.chat_used + max(delta, 0)
        if limit and projected > limit:
            raise BatchBotChatLimitError(
                limit=limit, used=snapshot.chat_used, window_end=snapshot.window_end
            )
