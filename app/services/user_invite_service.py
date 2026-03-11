"""Organization user invitation orchestration.

Synopsis:
Creates invited users, assigns roles, and prepares verification-first setup.
Persists verification/setup token metadata so invite links map to real accounts.

Glossary:
- Invite flow: Create-account path initiated by organization owners/admins.
- Setup token: One-time token used by invited users to choose a password.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from flask import url_for
from flask_login import current_user

from app.extensions import db
from app.models import Organization, Role, User
from app.services.email_service import EmailService
from app.utils.timezone_utils import TimezoneUtils


# --- Invite result DTO ---
# Purpose: Return standardized invite outcomes to calling routes/services.
@dataclass
class InviteResult:
    success: bool
    message: str
    user: Optional[User] = None


# --- User invite service ---
# Purpose: Manage org-scoped invite lifecycle including verification/setup token initialization.
class UserInviteService:
    """Orchestrates organization user invitations (creation, role assignment, email)."""

    @staticmethod
    # --- Invite user ---
    # Purpose: Create invited user records with role assignment and setup email metadata.
    def invite_user(
        *,
        organization: Organization,
        email: str,
        role_id: int,
        first_name: str = "",
        last_name: str = "",
        phone: str = "",
        force_inactive: bool = False,
    ) -> InviteResult:
        normalized_email = User.normalize_email(email)
        if not normalized_email:
            return InviteResult(False, "Email is required")
        if User.email_exists(normalized_email):
            return InviteResult(False, "An account with that email already exists")

        # Validate role
        role: Optional[Role] = Role.query.filter_by(id=role_id).first()
        if not role:
            return InviteResult(False, "Invalid role selected")
        if role.name in ["developer", "organization_owner"]:
            return InviteResult(
                False,
                "Cannot assign system or organization owner roles to invited users",
            )

        # Enforce subscription user limits
        will_be_inactive = force_inactive or not organization.can_add_users()
        if not organization.can_add_users() and not force_inactive:
            return InviteResult(
                False,
                f"Organization has reached user limit ({organization.active_users_count}/{organization.get_max_users()}) for {organization.subscription_tier} subscription",
            )

        # Generate a unique username from email
        base_username = (normalized_email.split("@")[0] or "user").strip()
        username = base_username
        counter = 1
        while User.username_exists(username):
            username = f"{base_username}{counter}"
            counter += 1

        # Create the user (inactive if org limit reached)
        new_user = User(
            username=username,
            email=normalized_email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            organization_id=organization.id,
            is_active=not will_be_inactive,
            user_type="team_member",
        )
        # Temporary random password; user sets a permanent password during setup.
        temp_password = EmailService.generate_reset_token(username)
        new_user.set_password(temp_password)

        db.session.add(new_user)
        db.session.flush()

        # Assign role
        new_user.assign_role(role, assigned_by=current_user)

        verification_token = EmailService.generate_verification_token(normalized_email)
        new_user.email_verified = False
        new_user.email_verification_token = verification_token
        new_user.email_verification_sent_at = TimezoneUtils.utc_now()

        setup_token = EmailService.generate_reset_token(new_user.id)
        new_user.password_reset_token = setup_token
        new_user.password_reset_sent_at = TimezoneUtils.utc_now()

        db.session.commit()

        # Send verification email that continues directly into invite setup.
        invite_setup_path = url_for("onboarding.invite_setup", token=setup_token)
        if EmailService.is_configured():
            sent = EmailService.send_verification_email(
                normalized_email,
                verification_token,
                first_name or username,
                next_path=invite_setup_path,
            )
            if sent:
                msg = "User invited successfully! Verification email sent."
            else:
                msg = (
                    "User invited, but verification email could not be delivered. "
                    "Check email provider settings and retry."
                )
        else:
            msg = (
                "User invited, but email is not configured. Configure email delivery "
                "to send verification and setup links."
            )

        if will_be_inactive:
            msg += " User added as inactive due to subscription limits."

        return InviteResult(True, msg, user=new_user)
