"""
Utility helpers for issuing and validating server-side session tokens.
"""

from __future__ import annotations

import secrets
from typing import Optional

from flask import session


class SessionService:
    """Centralized helpers for per-user session management."""

    SESSION_TOKEN_KEY = "active_session_token"

    @staticmethod
    def rotate_user_session(user) -> str:
        """
        Generate a new session token for the given user and persist it to both
        the user record and the Flask session.
        """
        token = secrets.token_urlsafe(32)
        user.active_session_token = token
        SessionService._set_session_token(token)
        return token

    @staticmethod
    def clear_session_state() -> None:
        """Remove session tracking data from the Flask session."""
        try:
            session.pop(SessionService.SESSION_TOKEN_KEY, None)
        except RuntimeError:
            # Outside of a request context; nothing to clear.
            pass

    @staticmethod
    def get_session_token(default: Optional[str] = None) -> Optional[str]:
        """Fetch the current session token from the Flask session."""
        try:
            return session.get(SessionService.SESSION_TOKEN_KEY, default)
        except RuntimeError:
            return default

    @staticmethod
    def _set_session_token(token: str) -> None:
        try:
            session[SessionService.SESSION_TOKEN_KEY] = token
        except RuntimeError:
            # Some flows (e.g. CLI) may not have a request context.
            pass
