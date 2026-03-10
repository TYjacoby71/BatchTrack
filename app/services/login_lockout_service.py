"""Login lockout tracking for repeated failed authentication attempts.

Synopsis:
Tracks failed login attempts per user identifier and enforces a password-reset
unlock path after threshold breaches.
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
    requires_password_reset: bool = False


class LoginLockoutService:
    """Manage failed-login counters and password-reset lockouts."""

    _KEY_PREFIX = "login_lockout:v1"

    @staticmethod
    def _enabled() -> bool:
        return bool(current_app.config.get("AUTH_LOGIN_LOCKOUT_ENABLED", True))

    @staticmethod
    def _threshold() -> int:
        raw = current_app.config.get("AUTH_LOGIN_LOCKOUT_THRESHOLD", 10)
        try:
            return max(1, int(raw))
        except (TypeError, ValueError):
            return 10

    @staticmethod
    def _window_seconds() -> int:
        raw = current_app.config.get("AUTH_LOGIN_LOCKOUT_WINDOW_SECONDS", 900)
        try:
            return max(60, int(raw))
        except (TypeError, ValueError):
            return 900

    @classmethod
    def _subject_key(
        cls, *, user_id: int | None = None, identifier: str | None = None
    ) -> str | None:
        if user_id is not None:
            return f"{cls._KEY_PREFIX}:user:{int(user_id)}"
        normalized_identifier = (identifier or "").strip().lower()
        if not normalized_identifier:
            return None
        digest = hashlib.sha256(normalized_identifier.encode("utf-8")).hexdigest()
        return f"{cls._KEY_PREFIX}:identifier:{digest}"

    @staticmethod
    def _now_ts() -> int:
        return int(time.time())

    @classmethod
    def _state_for_key(cls, key: str) -> dict:
        state = app_cache.get(key)
        if not isinstance(state, dict):
            return {
                "count": 0,
                "window_started_at": cls._now_ts(),
                "requires_password_reset": False,
            }
        return {
            "count": int(state.get("count") or 0),
            "window_started_at": int(state.get("window_started_at") or cls._now_ts()),
            "requires_password_reset": bool(state.get("requires_password_reset")),
        }

    @classmethod
    def _save_state(cls, key: str, state: dict) -> None:
        ttl = max(cls._window_seconds(), 60)
        if state.get("requires_password_reset"):
            # Persistent lock state until password reset flow clears it.
            ttl = max(ttl, 60 * 60 * 24 * 30)
        app_cache.set(key, state, ttl=ttl)

    @classmethod
    def is_locked(
        cls, *, user_id: int | None = None, identifier: str | None = None
    ) -> LoginLockoutState:
        if not cls._enabled():
            return LoginLockoutState(locked=False)
        key = cls._subject_key(user_id=user_id, identifier=identifier)
        if not key:
            return LoginLockoutState(locked=False)
        state = cls._state_for_key(key)
        locked = bool(state.get("requires_password_reset"))
        return LoginLockoutState(
            locked=locked,
            requires_password_reset=locked,
        )

    @classmethod
    def record_failure(
        cls, *, user_id: int | None = None, identifier: str | None = None
    ) -> LoginLockoutState:
        if not cls._enabled():
            return LoginLockoutState(locked=False)
        key = cls._subject_key(user_id=user_id, identifier=identifier)
        if not key:
            return LoginLockoutState(locked=False)

        now = cls._now_ts()
        threshold = cls._threshold()
        window_seconds = cls._window_seconds()
        state = cls._state_for_key(key)
        if bool(state.get("requires_password_reset")):
            return LoginLockoutState(locked=True, requires_password_reset=True)

        window_started_at = int(state.get("window_started_at") or now)
        count = int(state.get("count") or 0)
        if now - window_started_at >= window_seconds:
            count = 0
            window_started_at = now

        count += 1
        locked = count >= threshold
        state.update(
            {
                "count": count,
                "window_started_at": window_started_at,
                "requires_password_reset": locked,
            }
        )
        cls._save_state(key, state)
        return LoginLockoutState(locked=locked, requires_password_reset=locked)

    @classmethod
    def clear_failures(
        cls,
        *,
        user_id: int | None = None,
        identifiers: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        if not cls._enabled():
            return
        keys: set[str] = set()
        primary = cls._subject_key(user_id=user_id, identifier=None)
        if primary:
            keys.add(primary)
        for identifier in identifiers or ():
            alias_key = cls._subject_key(user_id=None, identifier=identifier)
            if alias_key:
                keys.add(alias_key)
        for key in keys:
            app_cache.delete(key)
