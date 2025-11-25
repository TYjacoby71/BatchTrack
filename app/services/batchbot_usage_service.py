from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from flask import current_app

from ..extensions import db
from ..models import BatchBotUsage, Organization, User


class BatchBotLimitError(RuntimeError):
    """Raised when an organization exceeds its BatchBot quota."""

    def __init__(self, *, allowed: int | None, used: int, window_end: date):
        super().__init__("BatchBot request limit reached for the current window.")
        self.allowed = allowed
        self.used = used
        self.window_end = window_end


@dataclass(slots=True)
class BatchBotUsageSnapshot:
    allowed: Optional[int]
    used: int
    remaining: Optional[int]
    window_start: date
    window_end: date


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

        used = record.request_count if record else 0
        remaining = None if allowed is None or allowed < 0 else max(allowed - used, 0)

        return BatchBotUsageSnapshot(
            allowed=allowed,
            used=used,
            remaining=remaining,
            window_start=window_start,
            window_end=window_end,
        )

    @staticmethod
    def ensure_within_limit(org: Organization) -> None:
        limits = BatchBotUsageService.get_usage_snapshot(org)
        if limits.allowed is None or limits.allowed < 0:
            return
        if limits.used >= limits.allowed:
            raise BatchBotLimitError(
                allowed=limits.allowed,
                used=limits.used,
                window_end=limits.window_end,
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
                metadata={"limit": allowed},
            )
            db.session.add(record)

        record.increment(delta=delta, metadata=metadata)
        db.session.commit()

        remaining = None if allowed is None or allowed < 0 else max(allowed - record.request_count, 0)
        return BatchBotUsageSnapshot(
            allowed=allowed,
            used=record.request_count,
            remaining=remaining,
            window_start=window_start,
            window_end=window_end,
        )

    @staticmethod
    def _window_bounds(now: Optional[datetime] = None) -> tuple[date, date]:
        now = now or datetime.utcnow()
        window_days = max(1, int(current_app.config.get("BATCHBOT_REQUEST_WINDOW_DAYS", 30)))

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
