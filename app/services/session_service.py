"""
Utility helpers for issuing and validating server-side session tokens.
"""

from __future__ import annotations

import secrets
import os
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
        
        In non-production environments, skip single session enforcement
        to allow multiple concurrent sessions for load testing.
        """
        token = secrets.token_urlsafe(32)
        
        # Skip single session enforcement in non-production environments
        flask_env = os.environ.get('FLASK_ENV', 'development')
        if flask_env != 'production':
            # Generate unique token but don't store it in user record
            # This allows multiple concurrent sessions for the same user
            SessionService._set_session_token(token)
            return token
        
        # Production behavior: enforce single session
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
