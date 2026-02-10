"""Email verification auth routes."""

from __future__ import annotations

import logging
from datetime import timedelta

from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from . import auth_bp
from ...extensions import db, limiter
from ...models import User
from ...services.email_service import EmailService
from ...utils.timezone_utils import TimezoneUtils

logger = logging.getLogger(__name__)


def _verification_expiry_hours() -> int:
    raw = current_app.config.get("EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS", 24)
    try:
        hours = int(raw)
    except (TypeError, ValueError):
        return 24
    return max(1, hours)


def _issue_verification_token(user: User) -> str:
    token = EmailService.generate_verification_token(user.email or "")
    user.email_verification_token = token
    user.email_verification_sent_at = TimezoneUtils.utc_now()
    db.session.commit()
    return token


@auth_bp.route("/verify-email/<token>")
@limiter.limit("600/minute")
def verify_email(token):
    """Verify email address."""
    try:
        user = User.query.filter_by(email_verification_token=token).first()
        if not user:
            flash("Invalid verification link.", "error")
            return redirect(url_for("auth.login"))

        if user.email_verification_sent_at:
            expires_at = user.email_verification_sent_at + timedelta(hours=_verification_expiry_hours())
            if TimezoneUtils.utc_now() > expires_at:
                flash("Verification link has expired. Please request a new one.", "error")
                return redirect(url_for("auth.resend_verification"))

        user.email_verified = True
        user.email_verification_token = None
        user.email_verification_sent_at = None
        db.session.commit()

        flash("Email verified successfully! You can now log in.", "success")
        return redirect(url_for("auth.login"))
    except Exception as exc:
        logger.error("Email verification error: %s", str(exc))
        flash("Email verification failed. Please try again.", "error")
        return redirect(url_for("auth.login"))


@auth_bp.route("/resend-verification", methods=["GET", "POST"])
@limiter.limit("120/minute")
def resend_verification():
    """Resend email verification."""
    prefill_email = (
        (request.args.get("email") or "").strip().lower()
        or ((current_user.email if current_user.is_authenticated else "") or "").strip().lower()
    )

    if not EmailService.should_issue_verification_tokens():
        flash("Email verification is disabled for this environment.", "info")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        email = ((request.form.get("email") or prefill_email) or "").strip().lower()
        generic_message = (
            "If an account with that email exists and is unverified, a verification email has been sent."
        )

        if email and "@" in email:
            try:
                user = User.query.filter_by(email=email).first()
                if user and not user.email_verified:
                    token = _issue_verification_token(user)
                    EmailService.send_verification_email(
                        user.email,
                        token,
                        user.first_name or user.username,
                    )
            except Exception as exc:
                db.session.rollback()
                logger.warning("Resend verification failed for %s: %s", email, exc)

        flash(generic_message, "info")
        return redirect(url_for("auth.login"))

    return render_template("pages/auth/resend_verification.html", prefill_email=prefill_email)
