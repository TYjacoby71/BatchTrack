"""Global resilience and error-handler registration.

Synopsis:
Registers teardown and error handlers for database rollback safety, maintenance
fallbacks, and CSRF failure handling.

Glossary:
- Resilience handler: Global request teardown/error behavior for known failures.
- CSRF failure: Cross-site request forgery token/session validation error.
"""

from __future__ import annotations

from urllib.parse import urlparse

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFError
from sqlalchemy.exc import DBAPIError, OperationalError

from .extensions import db


def register_resilience_handlers(app) -> None:
    """Install global DB rollback and friendly maintenance/CSRF handlers."""

    def _csrf_wants_json_response() -> bool:
        try:
            from .utils.http import wants_json

            return (
                wants_json(request)
                or request.is_json
                or request.headers.get("X-Requested-With") == "XMLHttpRequest"
            )
        except Exception:
            return bool(request.is_json)

    def _csrf_login_target(next_path: str | None = None) -> str:
        if (
            isinstance(next_path, str)
            and next_path.startswith("/")
            and not next_path.startswith("//")
            and not next_path.startswith("/auth/")
        ):
            return url_for("auth.login", next=next_path)
        return url_for("auth.login")

    def _csrf_redirect_target() -> str:
        from flask_login import current_user

        default_next = request.path if request.path.startswith("/") else None
        default_target = (
            url_for("app_routes.dashboard")
            if current_user.is_authenticated
            else _csrf_login_target(default_next)
        )
        referrer = request.referrer
        if not referrer:
            return default_target

        try:
            parsed_referrer = urlparse(referrer)
            parsed_host = urlparse(request.host_url or "")
            # Avoid open redirects by requiring same host when netloc is provided.
            if parsed_referrer.netloc and parsed_referrer.netloc != parsed_host.netloc:
                return default_target
            path = parsed_referrer.path or "/"
            target = f"{path}?{parsed_referrer.query}" if parsed_referrer.query else path
            if not current_user.is_authenticated:
                return target if not target.startswith("/auth/") else _csrf_login_target(target)
            return target
        except Exception:
            return default_target

    @app.teardown_request
    def _rollback_on_error(exc):
        try:
            if exc is not None:
                db.session.rollback()
        except Exception:
            pass
        finally:
            try:
                db.session.remove()
            except Exception:
                pass

    @app.errorhandler(OperationalError)
    @app.errorhandler(DBAPIError)
    def _db_error_handler(_error):
        try:
            db.session.rollback()
        except Exception:
            pass
        # Return lightweight 503 page; avoid cascading errors if template missing.
        try:
            return render_template("errors/maintenance.html"), 503
        except Exception:
            return ("Service temporarily unavailable. Please try again shortly.", 503)

    @app.errorhandler(CSRFError)
    def _csrf_error_handler(err: CSRFError):
        """Log diagnostics and keep users on a navigable page."""
        details = {
            "path": request.path,
            "endpoint": request.endpoint,
            "remote_addr": request.headers.get("X-Forwarded-For", request.remote_addr),
            "user_agent": (
                (request.user_agent.string if request.user_agent else None)
                or request.headers.get("User-Agent")
            ),
            "reason": err.description,
        }
        app.logger.warning("CSRF validation failed: %s", details)
        if _csrf_wants_json_response():
            return (
                jsonify(
                    {
                        "error": "csrf_validation_failed",
                        "message": "Your session expired or this form is out of date. Refresh and try again.",
                        "reason": err.description,
                    }
                ),
                400,
            )
        flash("Your session expired or this form is out of date. Please try again.", "warning")
        return redirect(_csrf_redirect_target(), code=303)
