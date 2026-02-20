from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from flask import current_app, has_app_context

from app.extensions import db
from app.utils.json_store import read_json_file, write_json_file

logger = logging.getLogger(__name__)


class PublicBotTrapService:
    BOT_TRAP_FILE = "data/bot_traps.json"
    STRIKE_THRESHOLD_CONFIG_KEY = "BOT_TRAP_STRIKE_THRESHOLD"
    STRIKE_WINDOW_SECONDS_CONFIG_KEY = "BOT_TRAP_STRIKE_WINDOW_SECONDS"
    BLOCK_SECONDS_CONFIG_KEY = "BOT_TRAP_IP_BLOCK_SECONDS"
    BLOCK_MAX_SECONDS_CONFIG_KEY = "BOT_TRAP_IP_BLOCK_MAX_SECONDS"
    PENALTY_RESET_SECONDS_CONFIG_KEY = "BOT_TRAP_PENALTY_RESET_SECONDS"
    ENABLE_PERMANENT_IP_BLOCKS_CONFIG_KEY = "BOT_TRAP_ENABLE_PERMANENT_IP_BLOCKS"

    @classmethod
    def _default_state(cls) -> Dict[str, Any]:
        return {
            "hits": [],
            "blocked_ips": [],
            "blocked_emails": [],
            "blocked_users": [],
            "ip_temporary_blocks": {},
            "ip_strikes": {},
            "ip_penalties": {},
        }

    @classmethod
    def _load_state(cls) -> Dict[str, Any]:
        state = read_json_file(cls.BOT_TRAP_FILE, default={})
        if not isinstance(state, dict):
            state = {}
        defaults = cls._default_state()
        for key, default_value in defaults.items():
            value = state.get(key)
            if isinstance(default_value, list):
                if not isinstance(value, list):
                    state[key] = []
            elif isinstance(default_value, dict):
                if not isinstance(value, dict):
                    state[key] = {}
            elif key not in state:
                state[key] = default_value
        return state

    @staticmethod
    def _append_unique(values: list, value: Any) -> None:
        if value is None:
            return
        if value not in values:
            values.append(value)

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
    def _parse_iso_utc(value: Any) -> Optional[datetime]:
        if not value or not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

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
    def _coerce_int(cls, value: Any, *, default: int = 0, min_value: int = 0) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        if parsed < min_value:
            return min_value
        return parsed

    @classmethod
    def _cleanup_state(cls, state: Dict[str, Any], *, now: datetime) -> bool:
        changed = False

        ip_blocks = state.get("ip_temporary_blocks")
        if not isinstance(ip_blocks, dict):
            state["ip_temporary_blocks"] = {}
            ip_blocks = state["ip_temporary_blocks"]
            changed = True
        for ip, payload in list(ip_blocks.items()):
            if not isinstance(ip, str):
                ip_blocks.pop(ip, None)
                changed = True
                continue
            block_payload = payload if isinstance(payload, dict) else {}
            blocked_until = cls._parse_iso_utc(block_payload.get("blocked_until"))
            if blocked_until is None or blocked_until <= now:
                ip_blocks.pop(ip, None)
                changed = True

        ip_strikes = state.get("ip_strikes")
        if not isinstance(ip_strikes, dict):
            state["ip_strikes"] = {}
            ip_strikes = state["ip_strikes"]
            changed = True
        strike_window = cls._strike_window_seconds()
        for ip, payload in list(ip_strikes.items()):
            if not isinstance(ip, str):
                ip_strikes.pop(ip, None)
                changed = True
                continue
            strike_payload = payload if isinstance(payload, dict) else {}
            window_start = cls._parse_iso_utc(strike_payload.get("window_started_at"))
            if window_start is None:
                ip_strikes.pop(ip, None)
                changed = True
                continue
            age_seconds = (now - window_start).total_seconds()
            if age_seconds > strike_window:
                ip_strikes.pop(ip, None)
                changed = True

        ip_penalties = state.get("ip_penalties")
        if not isinstance(ip_penalties, dict):
            state["ip_penalties"] = {}
            ip_penalties = state["ip_penalties"]
            changed = True
        penalty_reset = cls._penalty_reset_seconds()
        for ip, payload in list(ip_penalties.items()):
            if not isinstance(ip, str):
                ip_penalties.pop(ip, None)
                changed = True
                continue
            penalty_payload = payload if isinstance(payload, dict) else {}
            last_blocked_at = cls._parse_iso_utc(penalty_payload.get("last_blocked_at"))
            if last_blocked_at is None:
                ip_penalties.pop(ip, None)
                changed = True
                continue
            age_seconds = (now - last_blocked_at).total_seconds()
            if age_seconds > penalty_reset:
                ip_penalties.pop(ip, None)
                changed = True

        return changed

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
    def _append_hit(cls, state: Dict[str, Any], entry: Dict[str, Any]) -> None:
        hits = state.get("hits")
        if isinstance(hits, list):
            hits.append(entry)
            return
        state["hits"] = [entry]

    @classmethod
    def _apply_temporary_ip_block(
        cls,
        state: Dict[str, Any],
        *,
        ip: Optional[str],
        now: datetime,
        reason: str,
        source: str,
        fixed_seconds: Optional[int] = None,
    ) -> Dict[str, Any] | None:
        ip_value = cls._normalize_ip(ip)
        if not ip_value:
            return None

        ip_penalties = state.setdefault("ip_penalties", {})
        if not isinstance(ip_penalties, dict):
            ip_penalties = {}
            state["ip_penalties"] = ip_penalties

        penalty_payload = (
            ip_penalties.get(ip_value)
            if isinstance(ip_penalties.get(ip_value), dict)
            else {}
        )
        last_blocked_at = cls._parse_iso_utc(penalty_payload.get("last_blocked_at"))
        level = cls._coerce_int(penalty_payload.get("level"), default=0, min_value=0)
        if (
            last_blocked_at is None
            or (now - last_blocked_at).total_seconds() > cls._penalty_reset_seconds()
        ):
            level = 0
        level += 1

        block_seconds: int
        if fixed_seconds is None:
            block_seconds = cls._block_base_seconds() * (2 ** (level - 1))
        else:
            block_seconds = cls._coerce_int(fixed_seconds, default=0, min_value=1)
        block_seconds = min(block_seconds, cls._block_max_seconds())

        blocked_until = now + timedelta(seconds=block_seconds)
        ip_blocks = state.setdefault("ip_temporary_blocks", {})
        if not isinstance(ip_blocks, dict):
            ip_blocks = {}
            state["ip_temporary_blocks"] = ip_blocks
        ip_blocks[ip_value] = {
            "blocked_at": now.isoformat(),
            "blocked_until": blocked_until.isoformat(),
            "block_seconds": block_seconds,
            "level": level,
            "reason": cls._safe_value(reason, max_len=80) or "unknown",
            "source": cls._safe_value(source, max_len=80) or "unknown",
        }
        ip_penalties[ip_value] = {
            "level": level,
            "last_blocked_at": now.isoformat(),
        }
        return {
            "ip": ip_value,
            "block_seconds": block_seconds,
            "level": level,
            "blocked_until": blocked_until.isoformat(),
        }

    @classmethod
    def _register_ip_strike(
        cls,
        state: Dict[str, Any],
        *,
        ip: Optional[str],
        now: datetime,
        source: str,
        reason: str,
    ) -> int:
        ip_value = cls._normalize_ip(ip)
        if not ip_value:
            return 0
        ip_strikes = state.setdefault("ip_strikes", {})
        if not isinstance(ip_strikes, dict):
            ip_strikes = {}
            state["ip_strikes"] = ip_strikes

        strike_payload = (
            ip_strikes.get(ip_value)
            if isinstance(ip_strikes.get(ip_value), dict)
            else {}
        )
        window_start = cls._parse_iso_utc(strike_payload.get("window_started_at"))
        strike_count = cls._coerce_int(strike_payload.get("count"), default=0, min_value=0)

        if (
            window_start is None
            or (now - window_start).total_seconds() > cls._strike_window_seconds()
        ):
            strike_count = 0
            window_start = now

        strike_count += 1
        ip_strikes[ip_value] = {
            "count": strike_count,
            "window_started_at": window_start.isoformat(),
            "last_hit_at": now.isoformat(),
            "source": cls._safe_value(source, max_len=80) or "unknown",
            "reason": cls._safe_value(reason, max_len=80) or "unknown",
        }
        return strike_count

    @classmethod
    def _is_temporarily_blocked(
        cls, state: Dict[str, Any], *, ip: Optional[str], now: datetime
    ) -> bool:
        ip_value = cls._normalize_ip(ip)
        if not ip_value:
            return False
        ip_blocks = state.get("ip_temporary_blocks")
        if not isinstance(ip_blocks, dict):
            return False
        block_payload = (
            ip_blocks.get(ip_value) if isinstance(ip_blocks.get(ip_value), dict) else {}
        )
        blocked_until = cls._parse_iso_utc(block_payload.get("blocked_until"))
        if blocked_until is None:
            return False
        return blocked_until > now

    @classmethod
    def is_blocked(
        cls,
        *,
        ip: Optional[str] = None,
        email: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> bool:
        state = cls._load_state()
        now = cls._utcnow()
        changed = cls._cleanup_state(state, now=now)
        ip_value = cls._normalize_ip(ip)
        email_value = cls._normalize_email(email)
        user_value = cls._normalize_user_id(user_id)

        if changed:
            write_json_file(cls.BOT_TRAP_FILE, state)

        if cls._is_temporarily_blocked(state, ip=ip_value, now=now):
            return True
        if (
            cls._permanent_ip_blocks_enabled()
            and ip_value
            and ip_value in state.get("blocked_ips", [])
        ):
            return True
        if email_value and email_value in state.get("blocked_emails", []):
            return True
        if user_value and user_value in state.get("blocked_users", []):
            return True
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
        state = cls._load_state()
        now = cls._utcnow()
        cls._cleanup_state(state, now=now)
        ip_value = cls._normalize_ip(ip)
        if permanent_ip:
            cls._append_unique(state.setdefault("blocked_ips", []), ip_value)
        elif ip_value:
            cls._apply_temporary_ip_block(
                state,
                ip=ip_value,
                now=now,
                reason=reason,
                source=source,
                fixed_seconds=ip_block_seconds,
            )
        cls._append_unique(
            state.setdefault("blocked_emails", []), cls._normalize_email(email)
        )
        cls._append_unique(
            state.setdefault("blocked_users", []), cls._normalize_user_id(user_id)
        )
        write_json_file(cls.BOT_TRAP_FILE, state)

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
        state = cls._load_state()
        now = cls._utcnow()
        cls._cleanup_state(state, now=now)

        entry = cls._build_entry(
            now=now,
            request=request,
            source=source,
            reason=reason,
            email=email,
            user_id=user_id,
            extra=extra,
        )
        cls._append_hit(state, entry)

        if block:
            cls._apply_temporary_ip_block(
                state,
                ip=entry.get("ip"),
                now=now,
                reason=reason,
                source=source,
            )
            cls._append_unique(state.setdefault("blocked_emails", []), entry.get("email"))
            cls._append_unique(state.setdefault("blocked_users", []), entry.get("user_id"))

        write_json_file(cls.BOT_TRAP_FILE, state)
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
        state = cls._load_state()
        now = cls._utcnow()
        cls._cleanup_state(state, now=now)

        entry = cls._build_entry(
            now=now,
            request=request,
            source=source,
            reason=reason,
            email=None,
            user_id=None,
            extra=extra,
        )
        cls._append_hit(state, entry)

        ip_value = entry.get("ip")
        strike_count = cls._register_ip_strike(
            state,
            ip=ip_value,
            now=now,
            source=source,
            reason=reason,
        )
        threshold = cls._strike_threshold()

        block_payload = None
        blocked = False
        if ip_value and strike_count >= threshold:
            ip_strikes = state.get("ip_strikes")
            if isinstance(ip_strikes, dict):
                ip_strikes.pop(ip_value, None)
            block_payload = cls._apply_temporary_ip_block(
                state,
                ip=ip_value,
                now=now,
                reason=reason,
                source=source,
            )
            blocked = block_payload is not None

        write_json_file(cls.BOT_TRAP_FILE, state)
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
