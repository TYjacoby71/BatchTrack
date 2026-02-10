"""Password reset routes backed by one-time email tokens."""

from __future__ import annotations

import logging
from datetime import timedelta

from flask import current_app, flash, redirect, render_template, request, url_for

from . import auth_bp
from ...extensions import db, limiter
from ...models import User
from ...services.email_service import EmailService
from ...utils.timezone_utils import TimezoneUtils

logger = logging.getLogger(__name__)


def _password_reset_expiry_hours() -> int:
    raw = current_app.config.get("PASSWORD_RESET_TOKEN_EXPIRY_HOURS", 24)
    try:
        hours = int(raw)
    except (TypeError, ValueError):
        return 24
    return max(1, hours)


def _is_reset_token_expired(user: User) -> bool:
    sent_at = getattr(user, "password_reset_sent_at", None)
    if not sent_at:
        return True
    expires_at = sent_at + timedelta(hours=_password_reset_expiry_hours())
    return TimezoneUtils.utc_now() > expires_at


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("120/minute")
def forgot_password():
    """Request a password reset link. Response is intentionally generic."""
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        generic_message = (
            "If an account with that email exists, we sent a password reset link."
        )

        if email and "@" in email:
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
                db.session.rollback()
                logger.warning("Forgot-password request failed for %s: %s", email, exc)

        flash(generic_message, "info")
        return redirect(url_for("auth.login"))

    return render_template("pages/auth/forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit("120/minute")
def reset_password(token):
    """Reset password using a one-time token delivered via email."""
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
            return render_template("pages/auth/reset_password.html", token=token)
        if new_password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("pages/auth/reset_password.html", token=token)
        if len(new_password) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return render_template("pages/auth/reset_password.html", token=token)

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
            db.session.rollback()
            logger.error("Password reset failed for user %s: %s", getattr(user, "id", None), exc)
            flash("Unable to reset password right now. Please try again.", "error")
            return render_template("pages/auth/reset_password.html", token=token)

        flash("Password updated successfully. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("pages/auth/reset_password.html", token=token)
