"""Whop license authentication routes."""

from __future__ import annotations

from flask import flash, redirect, request, url_for
from flask_login import login_user

from ...extensions import db
from ...models import User
from ...services.session_service import SessionService
from ...utils.timezone_utils import TimezoneUtils
from . import auth_bp
from .whop_auth import WhopAuth


@auth_bp.route("/whop-login", methods=["POST"])
def whop_login():
    """Authenticate user with Whop license key."""
    license_key = request.form.get("license_key")
    email = request.form.get("email", "")

    if not license_key:
        flash("License key is required.", "error")
        return redirect(url_for("auth.login"))

    user_data = WhopAuth.handle_whop_login(license_key, email)
    if user_data:
        user = User.query.filter_by(email=user_data.get("email")).first()
        if not user:
            username = user_data.get("username", user_data.get("email").split("@")[0])
            user = User(
                username=username,
                email=user_data.get("email"),
                first_name=user_data.get("first_name", ""),
                last_name=user_data.get("last_name", ""),
                is_active=True,
                user_type="customer",
            )
            db.session.add(user)
            db.session.flush()

        login_user(user)
        SessionService.rotate_user_session(user)
        user.last_login = TimezoneUtils.utc_now()
        db.session.commit()
        flash("Successfully logged in with Whop license.", "success")
        return redirect(url_for("app_routes.dashboard"))

    flash("Invalid license key or access denied.", "error")
    return redirect(url_for("auth.login"))
