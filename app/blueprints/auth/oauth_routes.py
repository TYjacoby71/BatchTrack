"""OAuth-specific authentication routes."""

from __future__ import annotations

import logging

from flask import abort, current_app, flash, jsonify, redirect, request, session, url_for
from flask_login import login_user

from . import auth_bp
from ...extensions import db, limiter
from ...models import User
from ...services.oauth_service import OAuthService
from ...services.session_service import SessionService
from ...utils.timezone_utils import TimezoneUtils

logger = logging.getLogger(__name__)


def _safe_relative_path(value: str | None) -> str | None:
    """Allow only local relative redirects to prevent open redirect attacks."""
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    if value.startswith("/") and not value.startswith("//"):
        return value
    return None


def _oauth_success_or_signup_redirect(*, provider: str, email: str, oauth_id: str | None, first_name: str = "", last_name: str = ""):
    """Complete OAuth login for existing users or continue payment-gated signup."""
    oauth_next = _safe_relative_path(session.pop("oauth_next", None))
    if not email:
        flash("Email address is required for account creation.", "error")
        return redirect(url_for("auth.login"))

    user = User.query.filter_by(email=email).first()
    if user:
        if not user.oauth_provider:
            user.oauth_provider = provider
            user.oauth_provider_id = oauth_id
            user.email_verified = True
            db.session.commit()

        login_user(user)
        SessionService.rotate_user_session(user)
        session.pop("dismissed_alerts", None)

        user.last_login = TimezoneUtils.utc_now()
        db.session.commit()
        flash(f"Welcome back, {user.first_name or user.username}!", "success")

        if user.user_type == "developer":
            return redirect(url_for("developer.dashboard"))

        try:
            next_url = session.pop("login_next", None)
        except Exception:
            next_url = None
        if isinstance(next_url, str) and next_url.startswith("/") and not next_url.startswith("//"):
            return redirect(next_url)
        return redirect(url_for("organization.dashboard"))

    session["oauth_user_info"] = {
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "oauth_provider": provider,
        "oauth_provider_id": oauth_id,
        "email_verified": True,
    }
    flash("Please complete your account setup by selecting a subscription plan.", "info")
    if oauth_next and oauth_next.startswith("/auth/signup"):
        return redirect(oauth_next)
    return redirect(url_for("auth.signup", tier="free"))


@auth_bp.route("/oauth/google")
@limiter.limit("1200/minute")
def oauth_google():
    """Initiate Google OAuth flow."""
    logger.info("OAuth Google route accessed")

    config_status = OAuthService.get_configuration_status()
    logger.info("OAuth configuration status: %s", config_status)

    if not OAuthService.is_google_oauth_configured():
        logger.warning("OAuth not configured - redirecting to login with error")
        flash("OAuth is not configured. Please contact administrator.", "error")
        return redirect(url_for("auth.login"))

    logger.info("Getting OAuth authorization URL")
    authorization_url, state = OAuthService.get_authorization_url()
    if not authorization_url:
        logger.error("Failed to get authorization URL")
        flash("Unable to initiate OAuth. Please try again.", "error")
        return redirect(url_for("auth.login"))

    logger.info("OAuth authorization URL generated successfully, state: %s...", state[:10])
    session["oauth_state"] = state
    session["oauth_provider"] = "google"
    oauth_next = _safe_relative_path(request.args.get("next"))
    if oauth_next:
        session["oauth_next"] = oauth_next
    return redirect(authorization_url)


@auth_bp.route("/oauth/callback")
@limiter.limit("1200/minute")
def oauth_callback():
    """Handle OAuth callback."""
    try:
        state = request.args.get("state")
        code = request.args.get("code")
        error = request.args.get("error")
        logger.info(
            "OAuth callback received - state: %s, code: %s, error: %s",
            state[:10] if state else None,
            code[:10] if code else None,
            error,
        )

        if error:
            logger.error("OAuth callback error: %s", error)
            flash(f"OAuth authentication failed: {error}", "error")
            return redirect(url_for("auth.login"))

        if not state or not code:
            logger.error("OAuth callback missing required parameters")
            flash("OAuth callback missing required parameters.", "error")
            return redirect(url_for("auth.login"))

        session_state = session.pop("oauth_state", None)
        session_provider = session.pop("oauth_provider", None)
        if session_provider and session_provider != "google":
            logger.error("OAuth provider mismatch: expected google, got %s", session_provider)
            flash("OAuth provider validation failed. Please try again.", "error")
            return redirect(url_for("auth.login"))
        if not session_state or session_state != state:
            logger.error(
                "OAuth state mismatch: session=%s, callback=%s",
                session_state[:10] if session_state else None,
                state[:10],
            )
            flash("OAuth state validation failed. Please try again.", "error")
            return redirect(url_for("auth.login"))

        credentials = OAuthService.exchange_code_for_token(code, state)
        if not credentials:
            logger.error("Failed to exchange OAuth code for credentials")
            flash("OAuth authentication failed. Please try again.", "error")
            return redirect(url_for("auth.login"))

        user_info = OAuthService.get_user_info(credentials)
        if not user_info:
            flash("Unable to retrieve user information. Please try again.", "error")
            return redirect(url_for("auth.login"))

        email = user_info.get("email")
        first_name = user_info.get("given_name", "")
        last_name = user_info.get("family_name", "")
        oauth_id = user_info.get("sub")
        return _oauth_success_or_signup_redirect(
            provider="google",
            email=email,
            oauth_id=oauth_id,
            first_name=first_name,
            last_name=last_name,
        )
    except Exception as exc:
        logger.error("OAuth callback error: %s", str(exc))
        flash("OAuth authentication failed. Please try again.", "error")
        return redirect(url_for("auth.login"))


@auth_bp.route("/oauth/facebook")
@limiter.limit("1200/minute")
def oauth_facebook():
    """Initiate Facebook OAuth flow."""
    if not OAuthService.is_facebook_oauth_configured():
        flash("Facebook OAuth is not configured. Please contact administrator.", "error")
        return redirect(url_for("auth.login"))

    state = OAuthService.generate_state()
    authorization_url = OAuthService.get_facebook_authorization_url(state)
    if not authorization_url:
        flash("Unable to initiate Facebook OAuth. Please try again.", "error")
        return redirect(url_for("auth.login"))

    session["oauth_state"] = state
    session["oauth_provider"] = "facebook"
    oauth_next = _safe_relative_path(request.args.get("next"))
    if oauth_next:
        session["oauth_next"] = oauth_next
    return redirect(authorization_url)


@auth_bp.route("/oauth/facebook/callback")
@limiter.limit("1200/minute")
def oauth_facebook_callback():
    """Handle Facebook OAuth callback."""
    try:
        state = request.args.get("state")
        code = request.args.get("code")
        error = request.args.get("error")
        error_reason = request.args.get("error_reason")
        error_description = request.args.get("error_description")

        if error:
            logger.error(
                "Facebook OAuth callback error: %s (%s) %s",
                error,
                error_reason,
                error_description,
            )
            flash("Facebook authentication was canceled or failed. Please try again.", "error")
            return redirect(url_for("auth.login"))

        if not state or not code:
            flash("Facebook callback missing required parameters.", "error")
            return redirect(url_for("auth.login"))

        session_state = session.pop("oauth_state", None)
        session_provider = session.pop("oauth_provider", None)
        if session_provider and session_provider != "facebook":
            flash("OAuth provider validation failed. Please try again.", "error")
            return redirect(url_for("auth.login"))
        if not session_state or session_state != state:
            flash("OAuth state validation failed. Please try again.", "error")
            return redirect(url_for("auth.login"))

        access_token = OAuthService.exchange_facebook_code_for_token(code)
        if not access_token:
            flash("Facebook authentication failed. Please try again.", "error")
            return redirect(url_for("auth.login"))

        user_info = OAuthService.get_facebook_user_info(access_token)
        if not user_info:
            flash("Unable to retrieve Facebook profile information.", "error")
            return redirect(url_for("auth.login"))

        email = user_info.get("email")
        oauth_id = user_info.get("id")
        first_name = user_info.get("first_name") or ""
        last_name = user_info.get("last_name") or ""
        if not first_name and not last_name:
            full_name = user_info.get("name") or ""
            name_parts = full_name.strip().split()
            if name_parts:
                first_name = name_parts[0]
                last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        return _oauth_success_or_signup_redirect(
            provider="facebook",
            email=email,
            oauth_id=oauth_id,
            first_name=first_name,
            last_name=last_name,
        )
    except Exception as exc:
        logger.error("Facebook OAuth callback error: %s", str(exc))
        flash("Facebook authentication failed. Please try again.", "error")
        return redirect(url_for("auth.login"))


@auth_bp.route("/callback")
@limiter.limit("1200/minute")
def oauth_callback_compat():
    """Compatibility alias for tests expecting /auth/callback."""
    return oauth_callback()


@auth_bp.route("/debug/oauth-config")
def debug_oauth_config():
    """Debug OAuth configuration - only in debug mode."""
    if not current_app.config.get("DEBUG"):
        abort(404)

    config_status = OAuthService.get_configuration_status()
    return jsonify(
        {
            "oauth_configuration": config_status,
            "environment_vars": {
                "GOOGLE_OAUTH_CLIENT_ID_present": bool(current_app.config.get("GOOGLE_OAUTH_CLIENT_ID")),
                "GOOGLE_OAUTH_CLIENT_SECRET_present": bool(current_app.config.get("GOOGLE_OAUTH_CLIENT_SECRET")),
                "FACEBOOK_OAUTH_APP_ID_present": bool(current_app.config.get("FACEBOOK_OAUTH_APP_ID")),
                "FACEBOOK_OAUTH_APP_SECRET_present": bool(current_app.config.get("FACEBOOK_OAUTH_APP_SECRET")),
            },
            "template_oauth_available": OAuthService.is_oauth_configured(),
            "template_oauth_providers": OAuthService.get_enabled_providers(),
        }
    )
