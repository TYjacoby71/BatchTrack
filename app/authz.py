from __future__ import annotations

from flask import jsonify, redirect, request, url_for
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db, login_manager
from .services.session_service import SessionService


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

        if user.user_type == "developer":
            return user

        if getattr(user, "organization", None) and user.organization.is_active:
            return user

        return None


def _expects_json() -> bool:
    accepts = request.headers.get("Accept", "")
    content_type = request.headers.get("Content-Type", "")
    return (
        request.is_json
        or request.path.startswith("/api/")
        or "application/json" in accepts
        or "application/json" in content_type
    )


def _rollback_safely() -> None:
    try:
        db.session.rollback()
    except Exception:
        pass
