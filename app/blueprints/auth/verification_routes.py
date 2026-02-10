"""Email verification auth routes."""

from __future__ import annotations

import logging
from datetime import timedelta

from flask import flash, redirect, render_template, request, url_for

from . import auth_bp
from ...extensions import db
from ...models import User
from ...services.email_service import EmailService
from ...utils.timezone_utils import TimezoneUtils

logger = logging.getLogger(__name__)


@auth_bp.route("/verify-email/<token>")
def verify_email(token):
    """Verify email address."""
    try:
        user = User.query.filter_by(email_verification_token=token).first()
        if not user:
            flash("Invalid verification link.", "error")
            return redirect(url_for("auth.login"))

        if user.email_verification_sent_at:
            expires_at = user.email_verification_sent_at + timedelta(hours=24)
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
def resend_verification():
    """Resend email verification."""
    if request.method == "POST":
        email = request.form.get("email")

        user = User.query.filter_by(email=email).first()
        if user and not user.email_verified:
            user.email_verification_token = EmailService.generate_verification_token(email)
            user.email_verification_sent_at = TimezoneUtils.utc_now()
            db.session.commit()

            EmailService.send_verification_email(
                email,
                user.email_verification_token,
                user.first_name,
            )
            flash("Verification email sent! Please check your inbox.", "success")
        else:
            flash(
                "If an account with that email exists and is unverified, a verification email has been sent.",
                "info",
            )

        return redirect(url_for("auth.login"))

    return render_template("pages/auth/resend_verification.html")
