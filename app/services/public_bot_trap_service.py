from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from flask import current_app, has_app_context
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.public_bot_trap import BotTrapHit, BotTrapIdentityBlock, BotTrapIpState

logger = logging.getLogger(__name__)


class PublicBotTrapService:
    # Kept for backward compatibility with existing callers/tests, but no longer used.
    BOT_TRAP_FILE = "data/bot_traps.json"

    STRIKE_THRESHOLD_CONFIG_KEY = "BOT_TRAP_STRIKE_THRESHOLD"
    STRIKE_WINDOW_SECONDS_CONFIG_KEY = "BOT_TRAP_STRIKE_WINDOW_SECONDS"
    BLOCK_SECONDS_CONFIG_KEY = "BOT_TRAP_IP_BLOCK_SECONDS"
    BLOCK_MAX_SECONDS_CONFIG_KEY = "BOT_TRAP_IP_BLOCK_MAX_SECONDS"
    PENALTY_RESET_SECONDS_CONFIG_KEY = "BOT_TRAP_PENALTY_RESET_SECONDS"
    ENABLE_PERMANENT_IP_BLOCKS_CONFIG_KEY = "BOT_TRAP_ENABLE_PERMANENT_IP_BLOCKS"

    # Optional audit logging controls (default off for hot-path safety).
    DB_LOG_HITS_CONFIG_KEY = "BOT_TRAP_LOG_HITS_TO_DB"
    DB_MAX_HITS_CONFIG_KEY = "BOT_TRAP_DB_MAX_HIT_ROWS"
    DB_HIT_TRIM_BATCH_CONFIG_KEY = "BOT_TRAP_DB_HIT_TRIM_BATCH"

    @staticmethod
    def _normalize_ip(raw_ip: Optional[str]) -> Optional[str]:
        if not raw_ip or not isinstance(raw_ip, str):
            return None
        ip = raw_ip.split(",")[0].strip()
        return ip or None

    @staticmethod
    def _normalize_email(raw: Optional[str]) -> Optional[str]:
        if not raw or not isinstance(raw, str):
            return None
        cleaned = raw.strip().lower()
        return cleaned or None

    @staticmethod
    def _normalize_user_id(raw: Optional[int | str]) -> Optional[int]:
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_value(raw: Optional[str], max_len: int = 160) -> Optional[str]:
        if not raw or not isinstance(raw, str):
            return None
        cleaned = raw.strip()
        if not cleaned:
            return None
        if len(cleaned) > max_len:
            return cleaned[:max_len]
        return cleaned

    @classmethod
    def resolve_request_ip(cls, request) -> Optional[str]:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return cls._normalize_ip(forwarded)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return cls._normalize_ip(real_ip)
        return cls._normalize_ip(getattr(request, "remote_addr", None))

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _as_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @classmethod
    def _policy_int(cls, key: str, default: int, *, min_value: int = 1) -> int:
        raw = default
        if has_app_context():
            raw = current_app.config.get(key, default)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return default
        if value < min_value:
            return default
        return value

    @classmethod
    def _policy_bool(cls, key: str, default: bool = False) -> bool:
        raw: Any = default
        if has_app_context():
            raw = current_app.config.get(key, default)
        if isinstance(raw, bool):
            return raw
        if raw is None:
            return default
        normalized = str(raw).strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return default

    @classmethod
    def _strike_threshold(cls) -> int:
        return cls._policy_int(cls.STRIKE_THRESHOLD_CONFIG_KEY, 3, min_value=1)

    @classmethod
    def _strike_window_seconds(cls) -> int:
        return cls._policy_int(cls.STRIKE_WINDOW_SECONDS_CONFIG_KEY, 600, min_value=30)

    @classmethod
    def _block_base_seconds(cls) -> int:
        return cls._policy_int(cls.BLOCK_SECONDS_CONFIG_KEY, 1800, min_value=60)

    @classmethod
    def _block_max_seconds(cls) -> int:
        configured = cls._policy_int(
            cls.BLOCK_MAX_SECONDS_CONFIG_KEY, 86400, min_value=60
        )
        return max(configured, cls._block_base_seconds())

    @classmethod
    def _penalty_reset_seconds(cls) -> int:
        return cls._policy_int(
            cls.PENALTY_RESET_SECONDS_CONFIG_KEY, 86400, min_value=300
        )

    @classmethod
    def _permanent_ip_blocks_enabled(cls) -> bool:
        return cls._policy_bool(cls.ENABLE_PERMANENT_IP_BLOCKS_CONFIG_KEY, False)

    @classmethod
    def _db_log_hits_enabled(cls) -> bool:
        return cls._policy_bool(cls.DB_LOG_HITS_CONFIG_KEY, False)

    @classmethod
    def _db_max_hit_rows(cls) -> int:
        return cls._policy_int(cls.DB_MAX_HITS_CONFIG_KEY, 5000, min_value=0)

    @classmethod
    def _db_hit_trim_batch(cls) -> int:
        return cls._policy_int(cls.DB_HIT_TRIM_BATCH_CONFIG_KEY, 500, min_value=1)

    @classmethod
    def _coerce_int(cls, value: Any, *, default: int = 0, min_value: int = 0) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        if parsed < min_value:
            return min_value
        return parsed

    @classmethod
    def _cleanup_ip_state_row(cls, row: BotTrapIpState, *, now: datetime) -> bool:
        changed = False
        blocked_until = cls._as_utc(row.blocked_until)
        if blocked_until is not None and blocked_until <= now:
            row.blocked_until = None
            changed = True

        strike_window_started_at = cls._as_utc(row.strike_window_started_at)
        if row.strike_count and strike_window_started_at is not None:
            age_seconds = (now - strike_window_started_at).total_seconds()
            if age_seconds > cls._strike_window_seconds():
                row.strike_count = 0
                row.strike_window_started_at = None
                changed = True
        elif row.strike_count and row.strike_window_started_at is None:
            row.strike_count = 0
            changed = True

        last_blocked_at = cls._as_utc(row.last_blocked_at)
        if row.penalty_level and last_blocked_at is not None:
            penalty_age = (now - last_blocked_at).total_seconds()
            if penalty_age > cls._penalty_reset_seconds():
                row.penalty_level = 0
                changed = True
        elif row.penalty_level and row.last_blocked_at is None:
            row.penalty_level = 0
            changed = True

        return changed

    @classmethod
    def _row_is_redundant(cls, row: BotTrapIpState, *, now: datetime) -> bool:
        if row.blocked_until is not None:
            return False
        if row.strike_count:
            return False
        if row.penalty_level:
            return False
        last_hit_at = cls._as_utc(row.last_hit_at)
        if last_hit_at is None:
            return True
        retention_window = max(cls._strike_window_seconds(), cls._penalty_reset_seconds())
        return (now - last_hit_at).total_seconds() > retention_window

    @classmethod
    def _get_or_create_ip_state(cls, ip: Optional[str]) -> BotTrapIpState | None:
        ip_value = cls._normalize_ip(ip)
        if not ip_value:
            return None
        state = BotTrapIpState.query.filter_by(ip=ip_value).first()
        if state is not None:
            return state
        state = BotTrapIpState(ip=ip_value)
        db.session.add(state)
        return state

    @classmethod
    def _upsert_identity_block(
        cls,
        *,
        block_type: str,
        value: Optional[str],
        reason: str,
        source: str,
    ) -> None:
        if not value:
            return
        existing = BotTrapIdentityBlock.query.filter_by(
            block_type=block_type,
            value=value,
        ).first()
        if existing is not None:
            existing.reason = cls._safe_value(reason, max_len=80) or existing.reason
            existing.source = cls._safe_value(source, max_len=80) or existing.source
            return
        db.session.add(
            BotTrapIdentityBlock(
                block_type=block_type,
                value=value,
                reason=cls._safe_value(reason, max_len=80),
                source=cls._safe_value(source, max_len=80),
            )
        )

    @classmethod
    def _identity_block_exists(cls, *, block_type: str, value: Optional[str]) -> bool:
        if not value:
            return False
        return (
            BotTrapIdentityBlock.query.with_entities(BotTrapIdentityBlock.id)
            .filter_by(block_type=block_type, value=value)
            .first()
            is not None
        )

    @classmethod
    def _build_entry(
        cls,
        *,
        now: datetime,
        request,
        source: str,
        reason: str,
        email: Optional[str],
        user_id: Optional[int],
        extra: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        entry = {
            "timestamp": now.isoformat(),
            "source": cls._safe_value(source, max_len=80) or "unknown",
            "reason": cls._safe_value(reason, max_len=80) or "unknown",
            "ip": cls.resolve_request_ip(request),
            "user_agent": cls._safe_value(request.headers.get("User-Agent")),
            "referer": cls._safe_value(request.headers.get("Referer")),
            "path": request.path,
            "method": request.method,
            "email": cls._normalize_email(email),
            "user_id": cls._normalize_user_id(user_id),
        }
        if extra:
            entry["extra"] = extra
        return entry

    @classmethod
    def _record_hit_row_if_enabled(cls, entry: Dict[str, Any]) -> None:
        if not cls._db_log_hits_enabled():
            return

        db.session.add(
            BotTrapHit(
                ip=entry.get("ip"),
                source=entry.get("source") or "unknown",
                reason=entry.get("reason") or "unknown",
                path=entry.get("path"),
                method=entry.get("method"),
                user_agent=entry.get("user_agent"),
                referer=entry.get("referer"),
                email=entry.get("email"),
                user_id=entry.get("user_id"),
                extra=entry.get("extra"),
            )
        )
        cls._trim_hits_if_needed()

    @classmethod
    def _trim_hits_if_needed(cls) -> None:
        max_rows = cls._db_max_hit_rows()
        if max_rows <= 0:
            BotTrapHit.query.delete(synchronize_session=False)
            return

        total_rows = db.session.query(func.count(BotTrapHit.id)).scalar() or 0
        overflow = total_rows - max_rows
        if overflow <= 0:
            return

        trim_count = max(overflow, cls._db_hit_trim_batch())
        oldest_ids = [
            row_id
            for (row_id,) in db.session.query(BotTrapHit.id)
            .order_by(BotTrapHit.id.asc())
            .limit(trim_count)
            .all()
        ]
        if not oldest_ids:
            return
        BotTrapHit.query.filter(BotTrapHit.id.in_(oldest_ids)).delete(
            synchronize_session=False
        )

    @classmethod
    def _apply_temporary_ip_block(
        cls,
        ip_state: BotTrapIpState | None,
        *,
        now: datetime,
        reason: str,
        source: str,
        fixed_seconds: Optional[int] = None,
    ) -> Dict[str, Any] | None:
        if ip_state is None:
            return None

        level = cls._coerce_int(ip_state.penalty_level, default=0, min_value=0)
        if (
            cls._as_utc(ip_state.last_blocked_at) is None
            or (
                now - cls._as_utc(ip_state.last_blocked_at)
            ).total_seconds()
            > cls._penalty_reset_seconds()
        ):
            level = 0
        level += 1

        if fixed_seconds is None:
            block_seconds = cls._block_base_seconds() * (2 ** (level - 1))
        else:
            block_seconds = cls._coerce_int(fixed_seconds, default=1, min_value=1)
        block_seconds = min(block_seconds, cls._block_max_seconds())

        blocked_until = now + timedelta(seconds=block_seconds)
        ip_state.blocked_until = blocked_until
        ip_state.penalty_level = level
        ip_state.last_blocked_at = now
        ip_state.last_source = cls._safe_value(source, max_len=80) or "unknown"
        ip_state.last_reason = cls._safe_value(reason, max_len=80) or "unknown"
        ip_state.last_hit_at = now

        return {
            "ip": ip_state.ip,
            "block_seconds": block_seconds,
            "level": level,
            "blocked_until": blocked_until.isoformat(),
        }

    @classmethod
    def _register_ip_strike(
        cls,
        ip_state: BotTrapIpState | None,
        *,
        now: datetime,
        source: str,
        reason: str,
    ) -> int:
        if ip_state is None:
            return 0

        strike_count = cls._coerce_int(ip_state.strike_count, default=0, min_value=0)
        window_start = cls._as_utc(ip_state.strike_window_started_at)
        if (
            window_start is None
            or (now - window_start).total_seconds() > cls._strike_window_seconds()
        ):
            strike_count = 0
            window_start = now

        strike_count += 1
        ip_state.strike_count = strike_count
        ip_state.strike_window_started_at = window_start
        ip_state.last_hit_at = now
        ip_state.last_source = cls._safe_value(source, max_len=80) or "unknown"
        ip_state.last_reason = cls._safe_value(reason, max_len=80) or "unknown"
        return strike_count

    @classmethod
    def is_blocked(
        cls,
        *,
        ip: Optional[str] = None,
        email: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> bool:
        now = cls._utcnow()
        ip_value = cls._normalize_ip(ip)
        email_value = cls._normalize_email(email)
        user_value = cls._normalize_user_id(user_id)

        try:
            if (
                cls._permanent_ip_blocks_enabled()
                and ip_value
                and cls._identity_block_exists(
                    block_type="ip_permanent",
                    value=ip_value,
                )
            ):
                return True

            if ip_value:
                ip_state = BotTrapIpState.query.filter_by(ip=ip_value).first()
                if ip_state is not None:
                    changed = cls._cleanup_ip_state_row(ip_state, now=now)
                    blocked = (
                        cls._as_utc(ip_state.blocked_until) is not None
                        and cls._as_utc(ip_state.blocked_until) > now
                    )
                    if not blocked and cls._row_is_redundant(ip_state, now=now):
                        db.session.delete(ip_state)
                        changed = True
                    if changed:
                        db.session.commit()
                    if blocked:
                        return True

            if email_value and cls._identity_block_exists(
                block_type="email",
                value=email_value,
            ):
                return True

            if user_value and cls._identity_block_exists(
                block_type="user",
                value=str(user_value),
            ):
                return True

            return False
        except Exception as exc:
            logger.warning("Bot trap block lookup failed (fail-open): %s", exc)
            try:
                db.session.rollback()
            except Exception:
                pass
            return False

    @classmethod
    def should_block_request(cls, request, user=None) -> bool:
        ip_value = cls.resolve_request_ip(request)
        user_id = None
        email = None
        if user is not None and getattr(user, "is_authenticated", False):
            user_id = getattr(user, "id", None)
            email = getattr(user, "email", None)
        return cls.is_blocked(ip=ip_value, email=email, user_id=user_id)

    @classmethod
    def add_block(
        cls,
        *,
        ip: Optional[str] = None,
        email: Optional[str] = None,
        user_id: Optional[int] = None,
        permanent_ip: bool = False,
        ip_block_seconds: Optional[int] = None,
        reason: str = "manual_block",
        source: str = "public_bot_trap_service",
    ) -> None:
        now = cls._utcnow()
        ip_value = cls._normalize_ip(ip)
        email_value = cls._normalize_email(email)
        user_value = cls._normalize_user_id(user_id)

        try:
            if permanent_ip and ip_value:
                cls._upsert_identity_block(
                    block_type="ip_permanent",
                    value=ip_value,
                    reason=reason,
                    source=source,
                )
            elif ip_value:
                ip_state = cls._get_or_create_ip_state(ip_value)
                cls._apply_temporary_ip_block(
                    ip_state,
                    now=now,
                    reason=reason,
                    source=source,
                    fixed_seconds=ip_block_seconds,
                )

            cls._upsert_identity_block(
                block_type="email",
                value=email_value,
                reason=reason,
                source=source,
            )
            cls._upsert_identity_block(
                block_type="user",
                value=str(user_value) if user_value is not None else None,
                reason=reason,
                source=source,
            )
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            logger.debug(
                "Bot trap add_block encountered concurrent insert; state likely already present."
            )
        except Exception as exc:
            logger.warning("Unable to persist bot trap block: %s", exc)
            try:
                db.session.rollback()
            except Exception:
                pass

    @classmethod
    def record_hit(
        cls,
        *,
        request,
        source: str,
        reason: str,
        email: Optional[str] = None,
        user_id: Optional[int] = None,
        extra: Optional[Dict[str, Any]] = None,
        block: bool = True,
    ) -> Dict[str, Any]:
        now = cls._utcnow()
        entry = cls._build_entry(
            now=now,
            request=request,
            source=source,
            reason=reason,
            email=email,
            user_id=user_id,
            extra=extra,
        )

        try:
            cls._record_hit_row_if_enabled(entry)

            if block:
                ip_state = cls._get_or_create_ip_state(entry.get("ip"))
                cls._apply_temporary_ip_block(
                    ip_state,
                    now=now,
                    reason=reason,
                    source=source,
                )
                cls._upsert_identity_block(
                    block_type="email",
                    value=entry.get("email"),
                    reason=reason,
                    source=source,
                )
                user_value = cls._normalize_user_id(entry.get("user_id"))
                cls._upsert_identity_block(
                    block_type="user",
                    value=str(user_value) if user_value is not None else None,
                    reason=reason,
                    source=source,
                )

            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            logger.debug(
                "Bot trap record_hit encountered concurrent insert; continuing safely."
            )
        except Exception as exc:
            logger.warning("Unable to record bot trap hit: %s", exc)
            try:
                db.session.rollback()
            except Exception:
                pass

        return entry

    @classmethod
    def record_suspicious_probe(
        cls,
        *,
        request,
        source: str,
        reason: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record a suspicious hit and apply adaptive strike-based IP blocking."""
        now = cls._utcnow()
        entry = cls._build_entry(
            now=now,
            request=request,
            source=source,
            reason=reason,
            email=None,
            user_id=None,
            extra=extra,
        )

        ip_value = entry.get("ip")
        strike_count = 0
        threshold = cls._strike_threshold()
        block_payload = None
        blocked = False

        try:
            ip_state = cls._get_or_create_ip_state(ip_value)
            strike_count = cls._register_ip_strike(
                ip_state,
                now=now,
                source=source,
                reason=reason,
            )

            if ip_state is not None and strike_count >= threshold:
                ip_state.strike_count = 0
                ip_state.strike_window_started_at = None
                block_payload = cls._apply_temporary_ip_block(
                    ip_state,
                    now=now,
                    reason=reason,
                    source=source,
                )
                blocked = block_payload is not None

            cls._record_hit_row_if_enabled(entry)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            logger.debug(
                "Bot trap suspicious probe encountered concurrent insert; retry skipped."
            )
        except Exception as exc:
            logger.warning("Unable to record suspicious probe: %s", exc)
            try:
                db.session.rollback()
            except Exception:
                pass

        return {
            "entry": entry,
            "ip": ip_value,
            "strike_count": strike_count,
            "threshold": threshold,
            "blocked": blocked,
            "block": block_payload,
        }

    @classmethod
    def block_user(cls, user, *, reason: str = "bot_trap") -> None:
        if not user:
            return
        try:
            if getattr(user, "is_active", True) is False:
                return
            user.is_active = False
            db.session.commit()
        except Exception as exc:
            logger.warning("Failed to deactivate user for %s: %s", reason, exc)
            try:
                db.session.rollback()
            except Exception:
                pass

    @classmethod
    def block_email_if_user_exists(cls, email: Optional[str]) -> Optional[int]:
        email_value = cls._normalize_email(email)
        if not email_value:
            return None
        try:
            from app.models import User

            user = User.query.filter_by(email=email_value).first()
            if user:
                cls.block_user(user, reason="bot_trap_email")
                return getattr(user, "id", None)
        except Exception as exc:
            logger.warning("Failed to deactivate user for bot email: %s", exc)
            try:
                db.session.rollback()
            except Exception:
                pass
        return None
