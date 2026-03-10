"""Login lockout tracking for repeated failed authentication attempts.

Synopsis:
Tracks failed login attempts by identifier and IP, enforces temporary lockouts,
and clears counters after successful authentication.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

from flask import current_app

from app.utils.cache_manager import app_cache


@dataclass
class LoginLockoutState:
    """Resolved lockout state for a login attempt."""

    locked: bool
    remaining_seconds: int = 0

    @property
    def remaining_minutes(self) -> int:
        if self.remaining_seconds <= 0:
            return 0
        return max(1, (self.remaining_seconds + 59) // 60)


class LoginLockoutService:
    """Manage failed-login counters and temporary lockouts."""

    _KEY_PREFIX = "login_lockout:v1"

    @staticmethod
    def _enabled() -> bool:
        return bool(current_app.config.get("AUTH_LOGIN_LOCKOUT_ENABLED", True))

    @staticmethod
    def _threshold() -> int:
        raw = current_app.config.get("AUTH_LOGIN_LOCKOUT_THRESHOLD", 5)
        try:
            return max(1, int(raw))
        except (TypeError, ValueError):
            return 5

    @staticmethod
    def _window_seconds() -> int:
        raw = current_app.config.get("AUTH_LOGIN_LOCKOUT_WINDOW_SECONDS", 900)
        try:
            return max(60, int(raw))
        except (TypeError, ValueError):
            return 900

    @staticmethod
    def _lockout_seconds() -> int:
        raw = current_app.config.get("AUTH_LOGIN_LOCKOUT_DURATION_SECONDS", 1800)
        try:
            return max(60, int(raw))
        except (TypeError, ValueError):
            return 1800

    @staticmethod
    def _normalize_identifier(value: str | None) -> str | None:
        normalized = (value or "").strip().lower()
        return normalized or None

    @classmethod
    def _hashed_key(cls, kind: str, value: str) -> str:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return f"{cls._KEY_PREFIX}:{kind}:{digest}"

    @classmethod
    def _build_targets(
        cls, *, identifier: str | None, ip_address: str | None
    ) -> list[str]:
        targets: list[str] = []
        normalized_identifier = cls._normalize_identifier(identifier)
        if normalized_identifier:
            targets.append(cls._hashed_key("identifier", normalized_identifier))
        normalized_ip = (ip_address or "").strip()
        if normalized_ip:
            targets.append(cls._hashed_key("ip", normalized_ip))
        return targets

    @staticmethod
    def _now_ts() -> int:
        return int(time.time())

    @classmethod
    def _state_for_key(cls, key: str) -> dict:
        state = app_cache.get(key)
        if not isinstance(state, dict):
            return {"count": 0, "window_started_at": cls._now_ts(), "locked_until": 0}
        return {
            "count": int(state.get("count") or 0),
            "window_started_at": int(state.get("window_started_at") or cls._now_ts()),
            "locked_until": int(state.get("locked_until") or 0),
        }

    @classmethod
    def _save_state(cls, key: str, state: dict) -> None:
        now = cls._now_ts()
        remaining_lock = max(0, int(state.get("locked_until", 0)) - now)
        ttl = max(cls._window_seconds(), remaining_lock, 60)
        app_cache.set(key, state, ttl=ttl)

    @classmethod
    def is_locked(
        cls, *, identifier: str | None, ip_address: str | None
    ) -> LoginLockoutState:
        if not cls._enabled():
            return LoginLockoutState(locked=False)
        now = cls._now_ts()
        remaining = 0
        for key in cls._build_targets(identifier=identifier, ip_address=ip_address):
            state = cls._state_for_key(key)
            locked_until = int(state.get("locked_until") or 0)
            if locked_until > now:
                remaining = max(remaining, locked_until - now)
        return LoginLockoutState(locked=remaining > 0, remaining_seconds=remaining)

    @classmethod
    def record_failure(
        cls, *, identifier: str | None, ip_address: str | None
    ) -> LoginLockoutState:
        if not cls._enabled():
            return LoginLockoutState(locked=False)
        now = cls._now_ts()
        threshold = cls._threshold()
        window_seconds = cls._window_seconds()
        lockout_seconds = cls._lockout_seconds()
        max_remaining = 0

        for key in cls._build_targets(identifier=identifier, ip_address=ip_address):
            state = cls._state_for_key(key)
            window_started_at = int(state.get("window_started_at") or now)
            locked_until = int(state.get("locked_until") or 0)
            count = int(state.get("count") or 0)

            if locked_until <= now and now - window_started_at >= window_seconds:
                count = 0
                window_started_at = now

            count += 1
            if count >= threshold:
                locked_until = now + lockout_seconds
                max_remaining = max(max_remaining, lockout_seconds)

            state.update(
                {
                    "count": count,
                    "window_started_at": window_started_at,
                    "locked_until": locked_until,
                }
            )
            cls._save_state(key, state)

            if locked_until > now:
                max_remaining = max(max_remaining, locked_until - now)

        return LoginLockoutState(locked=max_remaining > 0, remaining_seconds=max_remaining)

    @classmethod
    def clear_failures(cls, *, identifier: str | None, ip_address: str | None) -> None:
        if not cls._enabled():
            return
        for key in cls._build_targets(identifier=identifier, ip_address=ip_address):
            app_cache.delete(key)
