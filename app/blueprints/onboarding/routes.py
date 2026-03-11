"""Onboarding routes.

Synopsis:
Serves the guided post-signup onboarding checklist and profile setup flow.
Handles password setup, workspace profile updates, and checklist completion handoff.

Glossary:
- Checklist completion: Final onboarding action that sends users to dashboard.
"""

import re
from datetime import timedelta

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.utils.permissions import require_permission

from ...extensions import db
from ...models import User
from ...services.analytics_tracking_service import AnalyticsTrackingService
from ...utils.analytics_timing import seconds_since_first_landing
from ...utils.timezone_utils import TimezoneUtils

onboarding_bp = Blueprint("onboarding", __name__, url_prefix="/onboarding")


def _invite_setup_token_expired(user: User) -> bool:
    """Return True when invite setup token timestamp is absent or expired."""
    from flask import current_app

    expiry_hours_raw = current_app.config.get("PASSWORD_RESET_TOKEN_EXPIRY_HOURS", 24)
    try:
        expiry_hours = max(1, int(expiry_hours_raw))
    except (TypeError, ValueError):
        expiry_hours = 24

    sent_at = TimezoneUtils.ensure_timezone_aware(
        getattr(user, "password_reset_sent_at", None)
    )
    if not sent_at:
        return True
    expires_at = sent_at + timedelta(hours=expiry_hours)
    return TimezoneUtils.utc_now() > expires_at


@onboarding_bp.route("/invite-setup/<token>", methods=["GET", "POST"])
def invite_setup(token: str):
    """Complete invited-user profile + password setup after email verification."""
    user = User.query.filter_by(password_reset_token=token).first()
    if not user or _invite_setup_token_expired(user):
        if user and user.password_reset_token == token:
            user.password_reset_token = None
            user.password_reset_sent_at = None
            db.session.commit()
        flash("This invite setup link is invalid or has expired.", "error")
        return redirect(url_for("auth.login"))

    if not user.email_verified:
        flash("Please verify your email before completing profile setup.", "warning")
        return redirect(
            url_for(
                "auth.resend_verification",
                email=user.email,
                next=url_for("onboarding.invite_setup", token=token),
            )
        )

    errors: list[str] = []
    if request.method == "POST":
        first_name = (request.form.get("first_name") or "").strip()
        last_name = (request.form.get("last_name") or "").strip()
        phone = (request.form.get("user_phone") or "").strip()
        desired_username = (request.form.get("username") or user.username or "").strip()
        new_password = (request.form.get("new_password") or "").strip()
        confirm_password = (request.form.get("confirm_password") or "").strip()

        if not desired_username:
            errors.append("Username is required.")
        elif len(desired_username) < 3:
            errors.append("Username must be at least 3 characters.")
        elif not re.fullmatch(r"[A-Za-z0-9_]+", desired_username):
            errors.append(
                "Username can only contain letters, numbers, and underscores."
            )
        elif User.username_exists(desired_username, exclude_user_id=user.id):
            errors.append("That username is already taken.")

        if not new_password or not confirm_password:
            errors.append("Please enter and confirm your password.")
        elif new_password != confirm_password:
            errors.append("Passwords do not match.")
        elif len(new_password) < 8:
            errors.append("Password must be at least 8 characters long.")

        if not errors:
            user.first_name = first_name
            user.last_name = last_name
            user.phone = phone or None
            user.username = desired_username
            user.set_password(new_password)
            user.password_reset_token = None
            user.password_reset_sent_at = None
            db.session.commit()
            flash("Profile setup complete. Please log in to continue.", "success")
            return redirect(url_for("auth.login"))

        for error in errors:
            flash(error, "error")

    checklist = [
        {
            "key": "verify",
            "label": "Verify your email",
            "description": "Your email address has been confirmed.",
            "complete": True,
        },
        {
            "key": "password",
            "label": "Create your password",
            "description": "Set a secure password to finish account access.",
            "complete": False,
        },
        {
            "key": "profile",
            "label": "Complete your profile",
            "description": "Add your name, username, and optional phone.",
            "complete": False,
        },
    ]
    return render_template(
        "onboarding/invite_setup.html",
        invited_user=user,
        organization=getattr(user, "organization", None),
        checklist=checklist,
        errors=errors,
    )


# --- Welcome checklist route ---
# Purpose: Render/process first-login onboarding checklist and setup details.
# Inputs: Authenticated user/org context and optional POSTed profile/password fields.
# Outputs: Rendered onboarding page or redirect to dashboard when setup completes.
@onboarding_bp.route("/welcome", methods=["GET", "POST"])
@login_required
@require_permission("dashboard.view")
def welcome():
    """Guided landing checklist right after signup."""
    user = current_user
    organization = getattr(user, "organization", None)
    ga4_checkout_conversion = None

    if not organization:
        flash("No organization found for your account.", "error")
        return redirect(url_for("app_routes.dashboard"))

    if request.method == "GET":
        candidate = session.pop("ga4_checkout_conversion", None)
        if isinstance(candidate, dict):
            ga4_checkout_conversion = candidate

    requires_password_setup = bool(getattr(user, "password_reset_token", None))
    password_errors = []

    if request.method == "POST":
        form_name = request.form.get("form_name") or "details"

        if form_name == "password":
            new_password = (request.form.get("new_password") or "").strip()
            confirm_password = (request.form.get("confirm_password") or "").strip()

            if not new_password or not confirm_password:
                password_errors.append("Please enter and confirm your new password.")
            elif new_password != confirm_password:
                password_errors.append("Passwords do not match.")
            elif len(new_password) < 8:
                password_errors.append("Password must be at least 8 characters long.")

            if not password_errors:
                user.set_password(new_password)
                user.password_reset_token = None
                user.password_reset_sent_at = None
                db.session.commit()
                requires_password_setup = False
                flash("Your password has been updated.", "success")
                return redirect(url_for("onboarding.welcome"))

        else:
            org_name = (request.form.get("org_name") or organization.name or "").strip()
            org_contact_email = (
                request.form.get("org_contact_email")
                or organization.contact_email
                or user.email
                or ""
            ).strip()
            user_first = (
                request.form.get("first_name") or user.first_name or ""
            ).strip()
            user_last = (request.form.get("last_name") or user.last_name or "").strip()
            user_phone = (request.form.get("user_phone") or user.phone or "").strip()
            desired_username = (
                request.form.get("username") or user.username or ""
            ).strip()

            organization.name = org_name or organization.name
            organization.contact_email = (
                org_contact_email or organization.contact_email or user.email
            )
            user.first_name = user_first
            user.last_name = user_last
            user.phone = user_phone or None

            username_errors = []
            profile_errors = []
            if not user_first:
                profile_errors.append("Please add your first name before continuing.")
            if not user_last:
                profile_errors.append("Please add your last name before continuing.")
            if desired_username and desired_username != user.username:
                existing = User.query.filter(
                    User.username == desired_username, User.id != user.id
                ).first()
                if existing:
                    username_errors.append("That username is already taken.")
                elif len(desired_username) < 3:
                    username_errors.append("Username must be at least 3 characters.")
                elif not re.fullmatch(r"[A-Za-z0-9_]+", desired_username):
                    username_errors.append(
                        "Username can only contain letters, numbers, and underscores."
                    )
                else:
                    user.username = desired_username

            completion_errors = []
            if request.form.get("complete_checklist") == "true":
                if not (organization.contact_email or "").strip():
                    completion_errors.append(
                        "Please add your billing/contact email before continuing."
                    )
                if not (
                    (user.first_name or "").strip() and (user.last_name or "").strip()
                ):
                    completion_errors.append(
                        "Please add your first and last name before continuing."
                    )

            user.last_login = user.last_login or TimezoneUtils.utc_now()

            validation_errors = username_errors + profile_errors + completion_errors
            if validation_errors:
                for err in validation_errors:
                    flash(err, "error")
            else:
                db.session.commit()
                flash("Setup details saved.", "success")

                if request.form.get("complete_checklist") == "true":
                    if requires_password_setup:
                        flash(
                            "Please create your password before continuing to the dashboard.",
                            "warning",
                        )
                    else:
                        active_team_size = len(
                            [
                                member
                                for member in organization.users
                                if member.is_active and member.user_type != "developer"
                            ]
                        )
                        AnalyticsTrackingService.track_onboarding_completed(
                            organization_id=getattr(user, "organization_id", None),
                            user_id=getattr(user, "id", None),
                            team_size=active_team_size,
                            requires_password_setup=False,
                            checklist_completed=True,
                            seconds_since_first_landing=seconds_since_first_landing(
                                request
                            ),
                        )
                        session.pop("onboarding_welcome", None)
                        session.pop("onboarding_welcome_flash_shown", None)
                        session.pop("onboarding_completion_required_notice", None)
                        return redirect(url_for("app_routes.dashboard"))
    else:
        if session.get("onboarding_welcome") and not session.get(
            "onboarding_welcome_flash_shown"
        ):
            flash(
                "Thanks for joining BatchTrack! Let’s finish setting up your workspace.",
                "success",
            )
            session["onboarding_welcome_flash_shown"] = True

    team_size = len(
        [
            member
            for member in organization.users
            if member.is_active and member.user_type != "developer"
        ]
    )
    show_team_step = bool(
        organization.subscription_tier_obj
        and organization.subscription_tier_obj.user_limit not in (None, 1)
    )

    checklist = [
        {
            "key": "password",
            "label": "Create your password",
            "description": "Secure your account with a password before inviting anyone else.",
            "complete": not requires_password_setup,
        },
        {
            "key": "org_name",
            "label": "Name your workspace",
            "description": "Give your organization a friendly name so teammates know they are in the right place.",
            "complete": bool(organization.name and organization.name.strip()),
        },
        {
            "key": "contact_info",
            "label": "Confirm your contact info",
            "description": "Make sure we have the best email so invoices and alerts reach you.",
            "complete": bool(organization.contact_email),
        },
        {
            "key": "profile",
            "label": "Tell us about you",
            "description": "Add your name and phone number so support can reach you quickly.",
            "complete": bool(user.first_name and user.last_name),
        },
    ]

    if show_team_step:
        checklist.append(
            {
                "key": "team",
                "label": "Plan your team seats",
                "description": "Invite a teammate or confirm how many users you need on this tier.",
                "complete": team_size > 1,
            }
        )

    return render_template(
        "onboarding/welcome.html",
        organization=organization,
        checklist=checklist,
        show_team_step=show_team_step,
        team_size=team_size,
        requires_password_setup=requires_password_setup,
        password_errors=password_errors,
        ga4_checkout_conversion=ga4_checkout_conversion,
    )
