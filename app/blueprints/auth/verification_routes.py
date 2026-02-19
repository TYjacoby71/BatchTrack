"""Email verification auth routes.

Synopsis:
Handles email token verification and resend flows.
Resend behavior is controlled by env-driven verification mode and provider readiness.

Glossary:
- Verification token: One-time token proving mailbox ownership.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from urllib.parse import urlparse

from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ...extensions import db, limiter
from ...models import User
from ...services.email_service import EmailService
from ...utils.timezone_utils import TimezoneUtils
from . import auth_bp

logger = logging.getLogger(__name__)


# --- Resolve verification expiry hours ---
# Purpose: Normalize verification token expiry configuration to a safe integer.
# Inputs: App config value `EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS`.
# Outputs: Positive integer expiry window in hours.
def _verification_expiry_hours() -> int:
    """Resolve verification token expiry window from config."""
    raw = current_app.config.get("EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS", 24)
    try:
        hours = int(raw)
    except (TypeError, ValueError):
        return 24
    return max(1, hours)


# --- Issue verification token ---
# Purpose: Generate and persist a fresh verification token timestamp pair.
# Inputs: User model instance requiring verification.
# Outputs: Newly generated token string.
def _issue_verification_token(user: User) -> str:
    """Generate, persist, and return a fresh verification token."""
    token = EmailService.generate_verification_token(user.email or "")
    user.email_verification_token = token
    user.email_verification_sent_at = TimezoneUtils.utc_now()
    db.session.commit()
    return token


# --- Safe local path helper ---
# Purpose: Prevent open redirects by accepting only same-origin relative paths.
# Inputs: Candidate path/url string.
# Outputs: Sanitized relative path string or None.
def _safe_local_path(candidate: str | None) -> str | None:
    if not candidate or not isinstance(candidate, str):
        return None

    candidate = candidate.strip()
    if not candidate:
        return None

    if candidate.startswith("/") and not candidate.startswith("//"):
        return candidate

    try:
        parsed = urlparse(candidate)
    except Exception:
        return None

    if not parsed.path.startswith("/") or parsed.path.startswith("//"):
        return None
    if parsed.netloc and parsed.netloc != request.host:
        return None

    resolved = parsed.path
    if parsed.query:
        resolved = f"{resolved}?{parsed.query}"
    return resolved


# --- Resolve resend redirect target ---
# Purpose: Choose safe post-action redirect target for resend-verification requests.
# Inputs: Form/query `next` candidate and current auth context.
# Outputs: Relative redirect path string.
def _resolve_resend_redirect_target() -> str:
    next_candidate = _safe_local_path(request.form.get("next") or request.args.get("next"))
    if next_candidate:
        return next_candidate

    referrer_candidate = _safe_local_path(request.referrer)
    if referrer_candidate:
        return referrer_candidate

    if current_user.is_authenticated:
        return url_for("settings.index")
    return url_for("auth.login")


# --- Verify email route ---
# Purpose: Mark mailbox ownership as verified when token is valid and unexpired.
# Inputs: Verification token path parameter from email link.
# Outputs: Redirect response with success/error flash messaging.
@auth_bp.route("/verify-email/<token>")
@limiter.limit("600/minute")
def verify_email(token):
    """Verify email address."""
    try:
        user = User.query.filter_by(email_verification_token=token).first()
        if not user:
            flash("Invalid verification link.", "error")
            return redirect(url_for("auth.login"))

        sent_at = TimezoneUtils.ensure_timezone_aware(user.email_verification_sent_at)
        if sent_at:
            expires_at = sent_at + timedelta(hours=_verification_expiry_hours())
            if TimezoneUtils.utc_now() > expires_at:
                flash(
                    "Verification link has expired. Please request a new one.", "error"
                )
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


# --- Resend verification route ---
# Purpose: Re-issue verification links in prompt/required environments.
# Inputs: Optional email address (GET/POST), auth context, and optional next path.
# Outputs: Verification resend side effects plus redirect or template render.
@auth_bp.route("/resend-verification", methods=["GET", "POST"])
@limiter.limit("120/minute")
def resend_verification():
    """Resend email verification."""
    prefill_email = (request.args.get("email") or "").strip().lower() or (
        (current_user.email if current_user.is_authenticated else "") or ""
    ).strip().lower()

    if not EmailService.should_issue_verification_tokens():
        flash("Email verification is disabled for this environment.", "info")
        return redirect(_resolve_resend_redirect_target())

    if request.method == "POST":
        email = (
            (current_user.email if current_user.is_authenticated else "")
            or request.form.get("email")
            or prefill_email
            or ""
        ).strip().lower()
        generic_message = "If an account with that email exists and is unverified, a verification email has been sent."
        sent = False

        if email and "@" in email:
            try:
                user = User.query.filter_by(email=email).first()
                if user and not user.email_verified:
                    token = _issue_verification_token(user)
                    sent = EmailService.send_verification_email(
                        user.email,
                        token,
                        user.first_name or user.username,
                    )
                    if not sent:
                        # Failed sends should not leave token timestamps in cooldown state.
                        user.email_verification_token = None
                        user.email_verification_sent_at = None
                        db.session.commit()
            except Exception as exc:
                db.session.rollback()
                logger.warning("Resend verification failed for %s: %s", email, exc)

        if current_user.is_authenticated:
            if current_user.email_verified:
                flash("Your email is already verified.", "success")
            elif sent:
                flash(f"Verification email sent to {email}.", "success")
            else:
                flash(
                    "We could not send a verification email right now; check email provider settings and try again.",
                    "warning",
                )
        else:
            flash(generic_message, "info")
        return redirect(_resolve_resend_redirect_target())

    return render_template(
        "pages/auth/resend_verification.html", prefill_email=prefill_email
    )
