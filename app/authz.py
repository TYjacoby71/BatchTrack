"""Authentication and user-loading helpers.

Synopsis:
Configure Flask-Login handlers and load users with required relationships.

Glossary:
- User loader: Function used by Flask-Login to hydrate current_user.
- Session token: Server-side value used to validate active sessions.
"""

from __future__ import annotations
import logging

from flask import jsonify, redirect, request, url_for
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db, login_manager
from .services.session_service import SessionService

logger = logging.getLogger(__name__)



# --- Configure login manager ---
# Purpose: Attach Flask-Login handlers and user loader.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
def configure_login_manager(app):
    """Attach Flask-Login handlers with API-aware responses and session validation."""
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "info"

    @login_manager.unauthorized_handler
    def _unauthorized():
        if _expects_json():
            return jsonify({"error": "Authentication required"}), 401
        return redirect(url_for("auth.login", next=request.url))

    @login_manager.user_loader
    def load_user(user_id: str):
        from .models import User

        try:
            # Avoid eager-loading heavy permission joins on every request.
            user = db.session.get(User, int(user_id))
        except (ValueError, TypeError):
            return None
        except SQLAlchemyError:
            _rollback_safely()
            return None

        if not user or not user.is_active:
            return None

        if user.active_session_token:
            session_token = SessionService.get_session_token()
            if session_token != user.active_session_token:
                SessionService.clear_session_state()
                return None

        if user.user_type != "developer":
            org = getattr(user, "organization", None)
            if not org or not org.is_active:
                return None

        return user


# --- JSON expectation ---
# Purpose: Determine whether a request expects JSON output.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
def _expects_json() -> bool:
    accepts = request.headers.get("Accept", "")
    content_type = request.headers.get("Content-Type", "")
    return (
        request.is_json
        or request.path.startswith("/api/")
        or "application/json" in accepts
        or "application/json" in content_type
    )


# --- Safe rollback ---
# Purpose: Roll back session without raising during auth handling.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
def _rollback_safely() -> None:
    try:
        db.session.rollback()
    except Exception:
        logger.warning("Suppressed exception fallback at app/authz.py:89", exc_info=True)
        pass
