"""Whop license authentication routes.

Synopsis:
Expose login endpoint that authenticates users through Whop license validation,
creates missing local users when needed, and establishes authenticated sessions.

Glossary:
- Whop login route: Endpoint that processes Whop license login form submits.
- Session rotation: Issuing a new active session token after login.
- WhopAuth helper: Utility class handling Whop license verification workflows.
"""

from __future__ import annotations

from flask import flash, redirect, request, url_for
from flask_login import login_user

from ...extensions import db
from ...services.session_service import SessionService
from ...utils.timezone_utils import TimezoneUtils
from . import auth_bp
from .whop_auth import WhopAuth


# --- Whop login route ---
# Purpose: Authenticate user via Whop credentials and start local session.
# Inputs: Form payload containing license_key and email.
# Outputs: Redirect response with success/error flash messaging.
@auth_bp.route("/whop-login", methods=["POST"])
def whop_login():
    """Authenticate user with Whop license key."""
    license_key = request.form.get("license_key")
    email = request.form.get("email", "")

    if not license_key:
        flash("License key is required.", "error")
        return redirect(url_for("auth.login"))

    user = WhopAuth.handle_whop_login(license_key, email)
    if user:
        login_user(user)
        SessionService.rotate_user_session(user)
        user.last_login = TimezoneUtils.utc_now()
        db.session.commit()
        flash("Successfully logged in with Whop license.", "success")
        return redirect(url_for("app_routes.dashboard"))

    flash("Invalid license key or access denied.", "error")
    return redirect(url_for("auth.login"))
