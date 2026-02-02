from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.extensions import db
from app.utils.json_store import read_json_file, write_json_file

logger = logging.getLogger(__name__)


class PublicBotTrapService:
    BOT_TRAP_FILE = "data/bot_traps.json"

    @classmethod
    def _default_state(cls) -> Dict[str, Any]:
        return {
            "hits": [],
            "blocked_ips": [],
            "blocked_emails": [],
            "blocked_users": [],
        }

    @classmethod
    def _load_state(cls) -> Dict[str, Any]:
        state = read_json_file(cls.BOT_TRAP_FILE, default={})
        if not isinstance(state, dict):
            state = {}
        state.setdefault("hits", [])
        state.setdefault("blocked_ips", [])
        state.setdefault("blocked_emails", [])
        state.setdefault("blocked_users", [])
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

    @classmethod
    def is_blocked(
        cls,
        *,
        ip: Optional[str] = None,
        email: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> bool:
        state = cls._load_state()
        ip_value = cls._normalize_ip(ip)
        email_value = cls._normalize_email(email)
        user_value = cls._normalize_user_id(user_id)

        if ip_value and ip_value in state.get("blocked_ips", []):
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
    ) -> None:
        state = cls._load_state()
        cls._append_unique(state.setdefault("blocked_ips", []), cls._normalize_ip(ip))
        cls._append_unique(state.setdefault("blocked_emails", []), cls._normalize_email(email))
        cls._append_unique(state.setdefault("blocked_users", []), cls._normalize_user_id(user_id))
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
        ip_value = cls.resolve_request_ip(request)
        email_value = cls._normalize_email(email)
        user_value = cls._normalize_user_id(user_id)

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": cls._safe_value(source, max_len=80) or "unknown",
            "reason": cls._safe_value(reason, max_len=80) or "unknown",
            "ip": ip_value,
            "user_agent": cls._safe_value(request.headers.get("User-Agent")),
            "referer": cls._safe_value(request.headers.get("Referer")),
            "path": request.path,
            "method": request.method,
            "email": email_value,
            "user_id": user_value,
        }
        if extra:
            entry["extra"] = extra

        hits = state.get("hits")
        if isinstance(hits, list):
            hits.append(entry)
        else:
            state["hits"] = [entry]

        if block:
            cls._append_unique(state.setdefault("blocked_ips", []), ip_value)
            cls._append_unique(state.setdefault("blocked_emails", []), email_value)
            cls._append_unique(state.setdefault("blocked_users", []), user_value)

        write_json_file(cls.BOT_TRAP_FILE, state)
        return entry

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
