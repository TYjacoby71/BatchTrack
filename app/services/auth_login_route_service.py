"""Auth login route service boundary.

Synopsis:
Encapsulates auth login-route data/session access so
`auth/login_routes.py` stays transport-focused.
"""

from __future__ import annotations

from sqlalchemy import func, or_

from app.extensions import db
from app.models import GlobalItem, Organization, Role, User
from app.models.subscription_tier import SubscriptionTier
from app.services.email_service import EmailService
from app.utils.timezone_utils import TimezoneUtils


class AuthLoginRouteService:
    """Data/session helpers for auth login and quick-signup routes."""

    @staticmethod
    def issue_email_verification_token(user: User) -> None:
        AuthLoginRouteService.issue_verification_token_for_user(user=user)

    @staticmethod
    def issue_verification_token_for_user(*, user: User) -> None:
        user.email_verification_token = EmailService.generate_verification_token(
            user.email or ""
        )
        user.email_verification_sent_at = TimezoneUtils.utc_now()
        db.session.commit()

    @staticmethod
    def clear_verification_token_for_user(*, user: User) -> None:
        user.email_verification_token = None
        user.email_verification_sent_at = None
        db.session.commit()

    @staticmethod
    def find_login_user(*, normalized_identifier: str) -> User | None:
        return (
            User.query.filter(
                or_(
                    func.lower(User.username) == normalized_identifier,
                    func.lower(User.email) == normalized_identifier,
                )
            )
            .order_by(User.id.asc())
            .first()
        )

    @staticmethod
    def find_user_by_login_identifier(*, normalized_identifier: str) -> User | None:
        return AuthLoginRouteService.find_login_user(
            normalized_identifier=normalized_identifier
        )

    @staticmethod
    def commit_session() -> None:
        db.session.commit()

    @staticmethod
    def persist_login_success(*, user: User) -> None:
        user.last_login = TimezoneUtils.utc_now()
        db.session.commit()

    @staticmethod
    def resolve_free_tools_tier() -> SubscriptionTier | None:
        free_tools_tier = (
            SubscriptionTier.query.filter(
                func.lower(SubscriptionTier.name) == "free tools"
            )
            .order_by(SubscriptionTier.id.asc())
            .first()
        )
        if free_tools_tier:
            return free_tools_tier
        free_tools_tier = SubscriptionTier.find_by_identifier("free tools")
        if free_tools_tier:
            return free_tools_tier
        free_tools_tier = SubscriptionTier.find_by_identifier("free")
        if free_tools_tier:
            return free_tools_tier
        return SubscriptionTier.find_by_identifier("exempt")

    @staticmethod
    def create_quick_signup_account(
        *,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
        signup_source: str,
        username: str,
    ) -> tuple[Organization, User, SubscriptionTier | None]:
        tier = AuthLoginRouteService.resolve_free_tools_tier()
        verification_enabled = EmailService.should_issue_verification_tokens()

        org_name = f"{first_name or 'New'}'s Workspace"
        org = Organization(
            name=org_name,
            contact_email=email,
            is_active=True,
            signup_source=signup_source,
            subscription_status="active",
            billing_status="active",
        )
        if tier:
            org.subscription_tier_id = tier.id
        db.session.add(org)
        db.session.flush()

        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            organization_id=org.id,
            user_type="customer",
            is_organization_owner=True,
            is_active=True,
            email_verified=not verification_enabled,
            email_verification_token=(
                EmailService.generate_verification_token(email)
                if verification_enabled
                else None
            ),
            email_verification_sent_at=(
                TimezoneUtils.utc_now() if verification_enabled else None
            ),
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        org_owner_role = Role.query.filter_by(
            name="organization_owner",
            is_system_role=True,
        ).first()
        if org_owner_role:
            user.assign_role(org_owner_role)

        db.session.commit()
        return user, org, tier

    @staticmethod
    def create_quick_signup_user_and_org(
        *,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
        signup_source: str,
        tier: SubscriptionTier | None = None,
        verification_enabled: bool | None = None,
    ) -> tuple[User, Organization]:
        username = AuthLoginRouteService.generate_username_from_email(email=email)

        resolved_tier = tier or AuthLoginRouteService.resolve_free_tools_tier()
        if verification_enabled is None:
            verification_enabled = EmailService.should_issue_verification_tokens()

        org_name = f"{first_name or 'New'}'s Workspace"
        org = Organization(
            name=org_name,
            contact_email=email,
            is_active=True,
            signup_source=signup_source,
            subscription_status="active",
            billing_status="active",
        )
        if resolved_tier:
            org.subscription_tier_id = resolved_tier.id
        db.session.add(org)
        db.session.flush()

        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            organization_id=org.id,
            user_type="customer",
            is_organization_owner=True,
            is_active=True,
            email_verified=not verification_enabled,
            email_verification_token=(
                EmailService.generate_verification_token(email)
                if verification_enabled
                else None
            ),
            email_verification_sent_at=(
                TimezoneUtils.utc_now() if verification_enabled else None
            ),
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        org_owner_role = Role.query.filter_by(
            name="organization_owner",
            is_system_role=True,
        ).first()
        if org_owner_role:
            user.assign_role(org_owner_role)

        db.session.commit()
        return user, org

    @staticmethod
    def get_global_item_by_id(*, global_item_id: int) -> GlobalItem | None:
        return db.session.get(GlobalItem, int(global_item_id))

    @staticmethod
    def get_global_item_name_by_id(*, global_item_id: str) -> str:
        if not global_item_id or not global_item_id.isdigit():
            return ""
        global_item = db.session.get(GlobalItem, int(global_item_id))
        return getattr(global_item, "name", "") if global_item else ""

    @staticmethod
    def clear_active_session_token(*, user: User) -> None:
        user.active_session_token = None
        db.session.commit()

    @staticmethod
    def generate_username_from_email(*, email: str) -> str:
        base = (email or "user").split("@")[0]
        base = __import__("re").sub(r"[^a-zA-Z0-9]+", "", base) or "user"
        candidate = base
        counter = 1
        while User.username_exists(candidate):
            candidate = f"{base}{counter}"
            counter += 1
        return candidate

    @staticmethod
    def rollback_session() -> None:
        db.session.rollback()
