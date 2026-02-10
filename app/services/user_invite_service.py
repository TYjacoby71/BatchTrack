from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from flask_login import current_user
from app.extensions import db
from app.models import User, Role, Organization
from app.services.email_service import EmailService
from app.utils.timezone_utils import TimezoneUtils


@dataclass
class InviteResult:
    success: bool
    message: str
    user: Optional[User] = None


class UserInviteService:
    """Orchestrates organization user invitations (creation, role assignment, email)."""

    @staticmethod
    def invite_user(*, organization: Organization, email: str, role_id: int,
                    first_name: str = "", last_name: str = "", phone: str = "",
                    force_inactive: bool = False) -> InviteResult:
        # Validate role
        role: Optional[Role] = Role.query.filter_by(id=role_id).first()
        if not role:
            return InviteResult(False, 'Invalid role selected')
        if role.name in ['developer', 'organization_owner']:
            return InviteResult(False, 'Cannot assign system or organization owner roles to invited users')

        # Enforce subscription user limits
        will_be_inactive = force_inactive or not organization.can_add_users()
        if not organization.can_add_users() and not force_inactive:
            return InviteResult(False, f'Organization has reached user limit ({organization.active_users_count}/{organization.get_max_users()}) for {organization.subscription_tier} subscription')

        # Generate a unique username from email
        base_username = (email.split('@')[0] or 'user').strip()
        username = base_username
        counter = 1
        while User.query.filter_by(username=username).first():
            username = f"{base_username}{counter}"
            counter += 1

        # Create the user (inactive if org limit reached)
        new_user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            organization_id=organization.id,
            is_active=not will_be_inactive,
            user_type='team_member'
        )
        # Temporary random password; user will set via setup link
        temp_password = EmailService.generate_reset_token(username)
        new_user.set_password(temp_password)

        db.session.add(new_user)
        db.session.flush()

        # Assign role
        new_user.assign_role(role, assigned_by=current_user)

        setup_token = EmailService.generate_reset_token(new_user.id)
        new_user.password_reset_token = setup_token
        new_user.password_reset_sent_at = TimezoneUtils.utc_now()

        # Send password-setup email if configured
        if EmailService.is_configured():
            EmailService.send_password_setup_email(email, setup_token, first_name or username)
            msg = 'User invited successfully! Password setup email sent.'
        else:
            msg = 'User invited. Email not configured; set a password manually or configure email to send setup links.'

        db.session.commit()

        if will_be_inactive:
            msg += ' User added as inactive due to subscription limits.'

        return InviteResult(True, msg, user=new_user)

