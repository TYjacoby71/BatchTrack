from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from flask import current_app, has_app_context
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.public_bot_trap import BotTrapHit, BotTrapIdentityBlock, BotTrapIpState
from app.utils.redis_pool import get_redis_pool

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
    REDIS_ENABLED_CONFIG_KEY = "BOT_TRAP_REDIS_ENABLED"
    REDIS_PREFIX_CONFIG_KEY = "BOT_TRAP_REDIS_PREFIX"
    DEFAULT_REDIS_PREFIX = "bottrap:v1"
    GOOGLE_ADS_USER_AGENT_TOKENS = (
        "adsbot-google",
        "adsbot-google-mobile",
        "google-adwords-instant",
        "google-adwords-instant-mobile",
        "google-adwords-express",
    )
    GOOGLE_ADS_REFERER_HOSTS = (
        "ads.google.com",
        "googleads.g.doubleclick.net",
        "googleadservices.com",
    )

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
    def _normalize_host(raw_url: Optional[str]) -> Optional[str]:
        if not raw_url or not isinstance(raw_url, str):
            return None
        candidate = raw_url.strip()
        if not candidate:
            return None
        parsed = urlparse(candidate)
        host = parsed.hostname or None
        if host:
            return host.strip().lower()
        if "://" not in candidate:
            parsed = urlparse(f"https://{candidate}")
            host = parsed.hostname or None
            if host:
                return host.strip().lower()
        return None

    @staticmethod
    def _host_matches(host: Optional[str], allowed_hosts: tuple[str, ...]) -> bool:
        if not host:
            return False
        normalized_host = host.strip().lower()
        for allowed in allowed_hosts:
            normalized_allowed = allowed.strip().lower()
            if (
                normalized_host == normalized_allowed
                or normalized_host.endswith(f".{normalized_allowed}")
            ):
                return True
        return False

    @classmethod
    def is_google_ads_verification_request(cls, request) -> bool:
        """Return True for known Google Ads verification crawlers/checkers."""
        if request is None:
            return False

        method = str(getattr(request, "method", "") or "").upper()
        if method not in {"GET", "HEAD"}:
            return False

        user_agent = (
            str(request.headers.get("User-Agent", "") or "").strip().lower()
            if hasattr(request, "headers")
            else ""
        )
        if not user_agent:
            return False

        if user_agent == "google":
            return True

        if any(token in user_agent for token in cls.GOOGLE_ADS_USER_AGENT_TOKENS):
            return True

        referer_host = cls._normalize_host(
            request.headers.get("Referer") if hasattr(request, "headers") else None
        )
        if (
            cls._host_matches(referer_host, cls.GOOGLE_ADS_REFERER_HOSTS)
            and "chrome/" in user_agent
        ):
            return True

        return False

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
    def _redis_enabled(cls) -> bool:
        return cls._policy_bool(cls.REDIS_ENABLED_CONFIG_KEY, True)

    @classmethod
    def _redis_prefix(cls) -> str:
        raw: Any = cls.DEFAULT_REDIS_PREFIX
        if has_app_context():
            raw = current_app.config.get(
                cls.REDIS_PREFIX_CONFIG_KEY,
                cls.DEFAULT_REDIS_PREFIX,
            )
        prefix = str(raw).strip() if raw is not None else cls.DEFAULT_REDIS_PREFIX
        if not prefix:
            return cls.DEFAULT_REDIS_PREFIX
        return prefix.strip(":")

    @classmethod
    def _redis_client(cls):
        if not cls._redis_enabled():
            return None
        try:
            import redis
        except Exception:  # pragma: no cover - optional dependency
            logger.warning("Suppressed exception fallback at app/services/public_bot_trap_service.py:267", exc_info=True)
            return None

        app_obj = None
        redis_url = None
        if has_app_context():
            try:
                app_obj = current_app._get_current_object()
                redis_url = app_obj.config.get("REDIS_URL")
            except RuntimeError:
                app_obj = None
        if not redis_url:
            redis_url = os.environ.get("REDIS_URL")
        if not redis_url:
            return None

        try:
            pool = get_redis_pool(app_obj)
            if pool is not None:
                return redis.Redis(connection_pool=pool, decode_responses=True)
            return redis.Redis.from_url(redis_url, decode_responses=True)
        except Exception as exc:
            logger.debug("Bot trap Redis unavailable; continuing with DB path: %s", exc)
            return None

    @classmethod
    def _redis_key(cls, *parts: Any) -> str:
        segments = [cls._redis_prefix()]
        segments.extend(str(part) for part in parts if part not in (None, ""))
        return ":".join(segments)

    @classmethod
    def _redis_temp_ip_block_key(cls, ip: str) -> str:
        return cls._redis_key("block", "ip", ip)

    @classmethod
    def _redis_permanent_ip_block_key(cls, ip: str) -> str:
        return cls._redis_key("block", "ip_permanent", ip)

    @classmethod
    def _redis_email_block_key(cls, email: str) -> str:
        return cls._redis_key("block", "email", email)

    @classmethod
    def _redis_user_block_key(cls, user_id: int | str) -> str:
        return cls._redis_key("block", "user", user_id)

    @classmethod
    def _redis_ip_strike_key(cls, ip: str) -> str:
        return cls._redis_key("strike", ip)

    @classmethod
    def _redis_ip_penalty_key(cls, ip: str) -> str:
        return cls._redis_key("penalty", ip)

    @classmethod
    def _redis_exists(cls, redis_client, key: Optional[str]) -> bool:
        if redis_client is None or not key:
            return False
        try:
            return bool(redis_client.exists(key))
        except Exception:
            logger.warning("Suppressed exception fallback at app/services/public_bot_trap_service.py:328", exc_info=True)
            return False

    @classmethod
    def _cache_temporary_ip_block(
        cls,
        redis_client,
        *,
        ip: Optional[str],
        block_seconds: Optional[int],
    ) -> None:
        ip_value = cls._normalize_ip(ip)
        ttl = cls._coerce_int(block_seconds, default=0, min_value=0)
        if redis_client is None or not ip_value or ttl <= 0:
            return
        try:
            redis_client.set(cls._redis_temp_ip_block_key(ip_value), "1", ex=ttl)
        except Exception as exc:
            logger.debug("Failed to cache temporary bot-trap IP block in Redis: %s", exc)

    @classmethod
    def _cache_penalty_level(
        cls,
        redis_client,
        *,
        ip: Optional[str],
        level: Optional[int],
    ) -> None:
        ip_value = cls._normalize_ip(ip)
        normalized_level = cls._coerce_int(level, default=0, min_value=0)
        if redis_client is None or not ip_value or normalized_level <= 0:
            return
        try:
            redis_client.set(
                cls._redis_ip_penalty_key(ip_value),
                str(normalized_level),
                ex=cls._penalty_reset_seconds(),
            )
        except Exception as exc:
            logger.debug("Failed to cache bot-trap penalty level in Redis: %s", exc)

    @classmethod
    def _cache_identity_block(
        cls,
        redis_client,
        *,
        block_type: str,
        value: Optional[str],
    ) -> None:
        if redis_client is None or not value:
            return
        if block_type == "email":
            key = cls._redis_email_block_key(value)
        elif block_type == "user":
            key = cls._redis_user_block_key(value)
        elif block_type == "ip_permanent":
            key = cls._redis_permanent_ip_block_key(value)
        else:
            return
        try:
            redis_client.set(key, "1")
        except Exception as exc:
            logger.debug("Failed to cache bot-trap identity block in Redis: %s", exc)

    @staticmethod
    def _session_has_changes() -> bool:
        return bool(db.session.new or db.session.dirty or db.session.deleted)

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
        redis_client = cls._redis_client()

        try:
            # Fast path: check Redis first to avoid DB work on hot blocked identities.
            if redis_client is not None:
                if ip_value and cls._redis_exists(
                    redis_client, cls._redis_temp_ip_block_key(ip_value)
                ):
                    return True
                if (
                    cls._permanent_ip_blocks_enabled()
                    and ip_value
                    and cls._redis_exists(
                        redis_client,
                        cls._redis_permanent_ip_block_key(ip_value),
                    )
                ):
                    return True
                if email_value and cls._redis_exists(
                    redis_client, cls._redis_email_block_key(email_value)
                ):
                    return True
                if user_value is not None and cls._redis_exists(
                    redis_client,
                    cls._redis_user_block_key(str(user_value)),
                ):
                    return True

            if (
                cls._permanent_ip_blocks_enabled()
                and ip_value
                and cls._identity_block_exists(
                    block_type="ip_permanent",
                    value=ip_value,
                )
            ):
                cls._cache_identity_block(
                    redis_client,
                    block_type="ip_permanent",
                    value=ip_value,
                )
                return True

            if ip_value:
                ip_state = BotTrapIpState.query.filter_by(ip=ip_value).first()
                if ip_state is not None:
                    changed = cls._cleanup_ip_state_row(ip_state, now=now)
                    blocked_until = cls._as_utc(ip_state.blocked_until)
                    blocked = (
                        blocked_until is not None
                        and blocked_until > now
                    )
                    if not blocked and cls._row_is_redundant(ip_state, now=now):
                        db.session.delete(ip_state)
                        changed = True
                    if changed:
                        db.session.commit()
                    if blocked:
                        remaining_seconds = max(
                            1,
                            int((blocked_until - now).total_seconds()),
                        )
                        cls._cache_temporary_ip_block(
                            redis_client,
                            ip=ip_value,
                            block_seconds=remaining_seconds,
                        )
                        cls._cache_penalty_level(
                            redis_client,
                            ip=ip_value,
                            level=ip_state.penalty_level,
                        )
                        return True

            if email_value and cls._identity_block_exists(
                block_type="email",
                value=email_value,
            ):
                cls._cache_identity_block(
                    redis_client,
                    block_type="email",
                    value=email_value,
                )
                return True

            if user_value is not None and cls._identity_block_exists(
                block_type="user",
                value=str(user_value),
            ):
                cls._cache_identity_block(
                    redis_client,
                    block_type="user",
                    value=str(user_value),
                )
                return True

            return False
        except Exception as exc:
            logger.warning("Bot trap block lookup failed (fail-open): %s", exc)
            try:
                db.session.rollback()
            except Exception:
                logger.warning("Suppressed exception fallback at app/services/public_bot_trap_service.py:764", exc_info=True)
                pass
            return False

    @classmethod
    def should_block_request(cls, request, user=None) -> bool:
        if cls.is_google_ads_verification_request(request):
            return False
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
        redis_client = cls._redis_client()
        temp_block_payload: Dict[str, Any] | None = None

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
                temp_block_payload = cls._apply_temporary_ip_block(
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

            if redis_client is not None:
                if permanent_ip and ip_value:
                    cls._cache_identity_block(
                        redis_client,
                        block_type="ip_permanent",
                        value=ip_value,
                    )
                if temp_block_payload is not None:
                    cls._cache_temporary_ip_block(
                        redis_client,
                        ip=ip_value,
                        block_seconds=temp_block_payload.get("block_seconds"),
                    )
                    cls._cache_penalty_level(
                        redis_client,
                        ip=ip_value,
                        level=temp_block_payload.get("level"),
                    )
                cls._cache_identity_block(
                    redis_client,
                    block_type="email",
                    value=email_value,
                )
                cls._cache_identity_block(
                    redis_client,
                    block_type="user",
                    value=str(user_value) if user_value is not None else None,
                )
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
                logger.warning("Suppressed exception fallback at app/services/public_bot_trap_service.py:868", exc_info=True)
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
        redis_client = cls._redis_client()
        entry = cls._build_entry(
            now=now,
            request=request,
            source=source,
            reason=reason,
            email=email,
            user_id=user_id,
            extra=extra,
        )

        block_payload: Dict[str, Any] | None = None
        user_value = cls._normalize_user_id(entry.get("user_id"))

        try:
            cls._record_hit_row_if_enabled(entry)

            if block:
                ip_state = cls._get_or_create_ip_state(entry.get("ip"))
                block_payload = cls._apply_temporary_ip_block(
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
                cls._upsert_identity_block(
                    block_type="user",
                    value=str(user_value) if user_value is not None else None,
                    reason=reason,
                    source=source,
                )

            db.session.commit()

            if redis_client is not None and block:
                if block_payload is not None:
                    cls._cache_temporary_ip_block(
                        redis_client,
                        ip=entry.get("ip"),
                        block_seconds=block_payload.get("block_seconds"),
                    )
                    cls._cache_penalty_level(
                        redis_client,
                        ip=entry.get("ip"),
                        level=block_payload.get("level"),
                    )
                cls._cache_identity_block(
                    redis_client,
                    block_type="email",
                    value=entry.get("email"),
                )
                cls._cache_identity_block(
                    redis_client,
                    block_type="user",
                    value=str(user_value) if user_value is not None else None,
                )
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
                logger.warning("Suppressed exception fallback at app/services/public_bot_trap_service.py:955", exc_info=True)
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
        redis_client = cls._redis_client()

        if redis_client is not None and ip_value:
            try:
                strike_key = cls._redis_ip_strike_key(ip_value)
                penalty_key = cls._redis_ip_penalty_key(ip_value)
                strike_count = cls._coerce_int(
                    redis_client.incr(strike_key),
                    default=0,
                    min_value=0,
                )
                if strike_count == 1:
                    redis_client.expire(strike_key, cls._strike_window_seconds())

                if strike_count >= threshold:
                    redis_client.delete(strike_key)
                    penalty_level = cls._coerce_int(
                        redis_client.incr(penalty_key),
                        default=1,
                        min_value=1,
                    )
                    redis_client.expire(penalty_key, cls._penalty_reset_seconds())

                    block_seconds = cls._block_base_seconds() * (2 ** (penalty_level - 1))
                    block_seconds = min(block_seconds, cls._block_max_seconds())
                    blocked_until = now + timedelta(seconds=block_seconds)
                    redis_client.set(
                        cls._redis_temp_ip_block_key(ip_value),
                        "1",
                        ex=block_seconds,
                    )
                    block_payload = {
                        "ip": ip_value,
                        "block_seconds": block_seconds,
                        "level": penalty_level,
                        "blocked_until": blocked_until.isoformat(),
                    }
                    blocked = True

                    # Persist compact block metadata for Redis-miss fallback and ops visibility.
                    ip_state = cls._get_or_create_ip_state(ip_value)
                    if ip_state is not None:
                        ip_state.strike_count = 0
                        ip_state.strike_window_started_at = None
                        ip_state.blocked_until = blocked_until
                        ip_state.penalty_level = penalty_level
                        ip_state.last_blocked_at = now
                        ip_state.last_source = cls._safe_value(source, max_len=80) or "unknown"
                        ip_state.last_reason = cls._safe_value(reason, max_len=80) or "unknown"
                        ip_state.last_hit_at = now

                cls._record_hit_row_if_enabled(entry)
                if cls._session_has_changes():
                    db.session.commit()

                return {
                    "entry": entry,
                    "ip": ip_value,
                    "strike_count": strike_count,
                    "threshold": threshold,
                    "blocked": blocked,
                    "block": block_payload,
                }
            except Exception as exc:
                logger.warning(
                    "Redis suspicious-probe path failed; falling back to DB path: %s",
                    exc,
                )
                try:
                    db.session.rollback()
                except Exception:
                    logger.warning("Suppressed exception fallback at app/services/public_bot_trap_service.py:1056", exc_info=True)
                    pass

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

            if blocked and block_payload is not None:
                cls._cache_temporary_ip_block(
                    redis_client,
                    ip=ip_value,
                    block_seconds=block_payload.get("block_seconds"),
                )
                cls._cache_penalty_level(
                    redis_client,
                    ip=ip_value,
                    level=block_payload.get("level"),
                )
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
                logger.warning("Suppressed exception fallback at app/services/public_bot_trap_service.py:1102", exc_info=True)
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
                logger.warning("Suppressed exception fallback at app/services/public_bot_trap_service.py:1127", exc_info=True)
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
                logger.warning("Suppressed exception fallback at app/services/public_bot_trap_service.py:1146", exc_info=True)
                pass
        return None
