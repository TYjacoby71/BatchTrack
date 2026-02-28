"""Password reset routes backed by one-time email tokens.

Synopsis:
Implements forgot-password and token-backed reset flows.
Routes are provider-aware and gracefully no-op when reset email is disabled.

Glossary:
- Reset token: One-time password-change token sent to account email.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from flask import current_app, flash, redirect, render_template, request, url_for

from ...extensions import db, limiter
from ...models import User
from ...services.email_service import EmailService
from ...utils.timezone_utils import TimezoneUtils
from . import auth_bp

logger = logging.getLogger(__name__)


# --- Resolve reset expiry hours ---
# Purpose: Normalize reset token expiry configuration to a safe integer window.
# Inputs: App config value `PASSWORD_RESET_TOKEN_EXPIRY_HOURS`.
# Outputs: Positive integer expiry duration in hours.
def _password_reset_expiry_hours() -> int:
    """Resolve reset token expiry window from config."""
    raw = current_app.config.get("PASSWORD_RESET_TOKEN_EXPIRY_HOURS", 24)
    try:
        hours = int(raw)
    except (TypeError, ValueError):
        return 24
    return max(1, hours)


# --- Check reset-token expiry ---
# Purpose: Determine whether password-reset token timestamp has expired safely.
# Inputs: User model with `password_reset_sent_at` timestamp.
# Outputs: Boolean indicating whether token is expired/invalid.
def _is_reset_token_expired(user: User) -> bool:
    """Return True when token timestamp is absent or expired."""
    sent_at = TimezoneUtils.ensure_timezone_aware(
        getattr(user, "password_reset_sent_at", None)
    )
    if not sent_at:
        return True
    expires_at = sent_at + timedelta(hours=_password_reset_expiry_hours())
    return TimezoneUtils.utc_now() > expires_at


# --- Forgot password route ---
# Purpose: Issue password reset tokens while keeping responses account-enumeration safe.
# Inputs: Optional account email payload from public forgot-password form.
# Outputs: Generic redirect response plus optional token issuance side effects.
@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("120/minute")
def forgot_password():
    """Request a password reset link. Response is intentionally generic."""
    forgot_page_context = {
        "page_title": "Forgot Password | BatchTrack",
        "page_description": "Request a secure password reset link for your BatchTrack account.",
        "canonical_url": url_for("auth.forgot_password", _external=True),
        "show_public_header": True,
        "lightweight_public_shell": True,
        "load_analytics": False,
        "load_fontawesome": False,
        "load_feedback_widget": False,
    }
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        generic_message = (
            "If an account with that email exists, we sent a password reset link."
        )
        reset_enabled = EmailService.password_reset_enabled()

        if reset_enabled and email and "@" in email:
            try:
                user = User.query.filter_by(email=email).first()
                if user and user.is_active:
                    reset_token = EmailService.generate_reset_token(user.id)
                    user.password_reset_token = reset_token
                    user.password_reset_sent_at = TimezoneUtils.utc_now()
                    db.session.commit()

                    EmailService.send_password_reset_email(
                        user.email,
                        reset_token,
                        user.first_name or user.username,
                    )
            except Exception as exc:
                logger.warning("Suppressed exception fallback at app/blueprints/auth/password_routes.py:95", exc_info=True)
                db.session.rollback()
                logger.warning("Forgot-password request failed for %s: %s", email, exc)

        flash(generic_message, "info")
        return redirect(url_for("auth.login"))

    return render_template("pages/auth/forgot_password.html", **forgot_page_context)


# --- Reset password route ---
# Purpose: Validate one-time tokens and finalize password changes securely.
# Inputs: Password reset token route parameter and optional form submission.
# Outputs: Rendered reset form or redirect response after reset completion/failure.
@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit("120/minute")
def reset_password(token):
    """Reset password using a one-time token delivered via email."""
    reset_page_context = {
        "page_title": "Set New Password | BatchTrack",
        "page_description": "Set a new password to regain secure access to your BatchTrack account.",
        "canonical_url": url_for("auth.reset_password", token=token, _external=True),
        "show_public_header": True,
        "lightweight_public_shell": True,
        "load_analytics": False,
        "load_fontawesome": False,
        "load_feedback_widget": False,
    }

    def _render_reset_password_form():
        return render_template(
            "pages/auth/reset_password.html",
            token=token,
            **reset_page_context,
        )

    user = User.query.filter_by(password_reset_token=token).first()
    if not user or _is_reset_token_expired(user):
        if user and user.password_reset_token == token:
            user.password_reset_token = None
            user.password_reset_sent_at = None
            db.session.commit()
        flash("This password reset link is invalid or has expired.", "error")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        new_password = (request.form.get("password") or "").strip()
        confirm_password = (request.form.get("confirm_password") or "").strip()

        if not new_password or not confirm_password:
            flash("Please enter and confirm your new password.", "error")
            return _render_reset_password_form()
        if new_password != confirm_password:
            flash("Passwords do not match.", "error")
            return _render_reset_password_form()
        if len(new_password) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return _render_reset_password_form()

        try:
            user.set_password(new_password)
            user.password_reset_token = None
            user.password_reset_sent_at = None

            # Reset-link proof is equivalent to mailbox ownership.
            if user.email and not user.email_verified:
                user.email_verified = True
                user.email_verification_token = None
                user.email_verification_sent_at = None

            # Invalidate existing sessions for safety after credential changes.
            user.active_session_token = None
            db.session.commit()
        except Exception as exc:
            logger.warning("Suppressed exception fallback at app/blueprints/auth/password_routes.py:168", exc_info=True)
            db.session.rollback()
            logger.error(
                "Password reset failed for user %s: %s", getattr(user, "id", None), exc
            )
            flash("Unable to reset password right now. Please try again.", "error")
            return _render_reset_password_form()

        flash("Password updated successfully. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return _render_reset_password_form()
