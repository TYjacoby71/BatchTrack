"""Auth account persistence service boundary.

Synopsis:
Encapsulates auth/account lookup and token persistence flows so route handlers
avoid direct query/session usage for verification, reset, and onboarding paths.

Glossary:
- Module boundary: Defines the ownership scope and responsibilities for this module.
"""

from __future__ import annotations

from app.extensions import db
from app.models import Organization, User
from app.services.email_service import EmailService
from app.utils.timezone_utils import TimezoneUtils


class AuthAccountService:
    """Service helpers for auth account lookup and token persistence."""

    @staticmethod
    def find_user_by_verification_token(token: str) -> User | None:
        return User.query.filter_by(email_verification_token=token).first()

    @staticmethod
    def find_user_by_password_reset_token(token: str) -> User | None:
        return User.query.filter_by(password_reset_token=token).first()

    @staticmethod
    def find_user_by_email(email: str) -> User | None:
        return User.find_by_email(email)

    @staticmethod
    def username_exists(
        *, username: str | None, exclude_user_id: int | None = None
    ) -> bool:
        return User.username_exists(username, exclude_user_id=exclude_user_id)

    @staticmethod
    def issue_email_verification_token(user: User) -> str:
        token = EmailService.generate_verification_token(user.email or "")
        user.email_verification_token = token
        user.email_verification_sent_at = TimezoneUtils.utc_now()
        db.session.commit()
        return token

    @staticmethod
    def clear_email_verification_token(user: User) -> None:
        user.email_verification_token = None
        user.email_verification_sent_at = None
        db.session.commit()

    @staticmethod
    def mark_email_verified(user: User) -> None:
        user.email_verified = True
        user.email_verification_token = None
        user.email_verification_sent_at = None
        db.session.commit()

    @staticmethod
    def clear_password_reset_token(user: User) -> None:
        user.password_reset_token = None
        user.password_reset_sent_at = None
        db.session.commit()

    @staticmethod
    def set_password_reset_token(user: User, token: str) -> None:
        user.password_reset_token = token
        user.password_reset_sent_at = TimezoneUtils.utc_now()
        db.session.commit()

    @staticmethod
    def issue_password_reset_token(user: User) -> str:
        token = EmailService.generate_reset_token(user.id)
        AuthAccountService.set_password_reset_token(user, token)
        return token

    @staticmethod
    def set_password_from_reset_token(user: User, *, password: str) -> None:
        user.set_password(password)
        user.password_reset_token = None
        user.password_reset_sent_at = None
        if user.email and not user.email_verified:
            user.email_verified = True
            user.email_verification_token = None
            user.email_verification_sent_at = None
        user.active_session_token = None
        db.session.commit()

    @staticmethod
    def complete_invite_setup(
        user: User,
        *,
        first_name: str,
        last_name: str,
        phone: str,
        username: str,
        password: str,
    ) -> None:
        user.first_name = first_name
        user.last_name = last_name
        user.phone = phone or None
        user.username = username
        user.set_password(password)
        user.password_reset_token = None
        user.password_reset_sent_at = None
        db.session.commit()

    @staticmethod
    def set_onboarding_password(user: User, *, password: str) -> None:
        user.set_password(password)
        user.password_reset_token = None
        user.password_reset_sent_at = None
        db.session.commit()

    @staticmethod
    def save_onboarding_profile(
        user: User,
        organization: Organization,
        *,
        org_name: str,
        org_contact_email: str,
        first_name: str,
        last_name: str,
        phone: str,
        desired_username: str | None = None,
    ) -> None:
        organization.name = org_name or organization.name
        organization.contact_email = (
            org_contact_email or organization.contact_email or user.email
        )
        user.first_name = first_name
        user.last_name = last_name
        user.phone = phone or None
        if desired_username:
            user.username = desired_username
        user.last_login = user.last_login or TimezoneUtils.utc_now()
        db.session.commit()
