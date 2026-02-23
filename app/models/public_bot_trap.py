"""Database models backing bot-trap blocking state.

Synopsis:
Stores temporary IP strike/block state and durable identity blocks (email/user/IP)
used by request middleware and public trap endpoints.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.extensions import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BotTrapIpState(db.Model):
    """Per-IP adaptive strike and temporary block state."""

    __tablename__ = "bot_trap_ip_state"

    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(64), nullable=False, unique=True, index=True)
    strike_count = db.Column(db.Integer, nullable=False, default=0)
    strike_window_started_at = db.Column(db.DateTime, nullable=True)
    last_hit_at = db.Column(db.DateTime, nullable=True, index=True)
    blocked_until = db.Column(db.DateTime, nullable=True, index=True)
    penalty_level = db.Column(db.Integer, nullable=False, default=0)
    last_blocked_at = db.Column(db.DateTime, nullable=True)
    last_source = db.Column(db.String(80), nullable=True)
    last_reason = db.Column(db.String(80), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<BotTrapIpState ip={self.ip!r} blocked_until={self.blocked_until!r}>"


class BotTrapIdentityBlock(db.Model):
    """Durable identity block list (email/user/permanent-ip)."""

    __tablename__ = "bot_trap_identity_block"

    id = db.Column(db.Integer, primary_key=True)
    block_type = db.Column(db.String(32), nullable=False, index=True)
    value = db.Column(db.String(255), nullable=False, index=True)
    source = db.Column(db.String(80), nullable=True)
    reason = db.Column(db.String(80), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    __table_args__ = (
        db.UniqueConstraint(
            "block_type", "value", name="uq_bot_trap_identity_block_type_value"
        ),
        db.Index("ix_bot_trap_identity_block_type_value", "block_type", "value"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<BotTrapIdentityBlock {self.block_type}:{self.value}>"


class BotTrapHit(db.Model):
    """Optional event log row for trap hits."""

    __tablename__ = "bot_trap_hit"

    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(64), nullable=True, index=True)
    source = db.Column(db.String(80), nullable=False, index=True)
    reason = db.Column(db.String(80), nullable=False, index=True)
    path = db.Column(db.String(255), nullable=True)
    method = db.Column(db.String(16), nullable=True)
    user_agent = db.Column(db.String(160), nullable=True)
    referer = db.Column(db.String(160), nullable=True)
    email = db.Column(db.String(255), nullable=True, index=True)
    user_id = db.Column(db.Integer, nullable=True, index=True)
    extra = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow, index=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<BotTrapHit {self.source}:{self.reason} ip={self.ip!r}>"
