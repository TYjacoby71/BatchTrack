"""Organization route service boundary.

Synopsis:
Provides query/session helpers for organization blueprint routes so route
handlers avoid direct ORM/session ownership.

Glossary:
- Module boundary: Defines the ownership scope and responsibilities for this module.
"""

from __future__ import annotations

from app.extensions import db
from app.models import Permission, Role, User
from app.models.subscription_tier import SubscriptionTier


class OrganizationRouteService:
    """Data/session helpers for organization routes."""

    @staticmethod
    def list_customer_facing_tiers():
        return SubscriptionTier.query.filter_by(is_customer_facing=True).all()

    @staticmethod
    def count_pending_invites(org_id: int) -> int:
        return User.query.filter_by(
            organization_id=org_id, is_active=False, user_type="customer"
        ).count()

    @staticmethod
    def list_active_permissions():
        return Permission.query.filter_by(is_active=True).all()

    @staticmethod
    def list_org_users(org_id: int):
        return (
            User.query.filter(
                User.organization_id == org_id, User.user_type != "developer"
            )
            .order_by(User.created_at.desc())
            .all()
        )

    @staticmethod
    def list_export_users(org_id: int):
        return User.query.filter(
            User.organization_id == org_id,
            User.user_type != "developer",
        ).all()

    @staticmethod
    def list_permissions_by_ids(permission_ids: list[int]):
        if not permission_ids:
            return []
        return Permission.query.filter(Permission.id.in_(permission_ids)).all()

    @staticmethod
    def get_scoped_role(role_id: int):
        return Role.scoped().filter_by(id=role_id).first()

    @staticmethod
    def get_user_in_org(user_id: int, organization_id: int):
        return User.query.filter_by(id=user_id, organization_id=organization_id).first()

    @staticmethod
    def list_other_org_owners(org_id: int, exclude_user_id: int):
        return User.query.filter(
            User.organization_id == org_id,
            User.id != exclude_user_id,
            User._is_organization_owner,
        ).all()

    @staticmethod
    def get_org_owner_role():
        return (
            Role.scoped()
            .filter_by(name="organization_owner", is_system_role=True)
            .first()
        )

    @staticmethod
    def get_subscription_tier(tier_id: int):
        return db.session.get(SubscriptionTier, tier_id)

    @staticmethod
    def add_entity(entity) -> None:
        db.session.add(entity)

    @staticmethod
    def commit_session() -> None:
        db.session.commit()

    @staticmethod
    def rollback_session() -> None:
        db.session.rollback()

    @staticmethod
    def create_org_role(
        *,
        org_id: int,
        created_by: int,
        name: str,
        description: str | None,
        permission_ids: list[int],
    ):
        role = Role(
            name=name,
            description=description,
            organization_id=org_id,
            created_by=created_by,
            is_system_role=False,
        )
        role.permissions = OrganizationRouteService.list_permissions_by_ids(
            permission_ids
        )
        db.session.add(role)
        db.session.commit()
        return role

    @staticmethod
    def update_org_settings(
        *,
        organization,
        data: dict,
        current_user_obj,
    ) -> None:
        if "name" in data and data["name"].strip():
            organization.name = data["name"].strip()

        if "contact_email" in data:
            contact_email = (
                data["contact_email"].strip()
                if data["contact_email"]
                else current_user_obj.email
            )
            organization.contact_email = contact_email

        if "timezone" in data:
            organization.timezone = data["timezone"]

        method = data.get("inventory_cost_method")
        if method in ["fifo", "average"]:
            if getattr(organization, "inventory_cost_method", None) != method:
                organization.inventory_cost_method = method
                from app.utils.timezone_utils import TimezoneUtils as _TZ

                organization.inventory_cost_method_changed_at = _TZ.utc_now()
        db.session.commit()

    @staticmethod
    def update_subscription_tier(
        *,
        organization,
        tier_key: str,
    ) -> bool:
        from app.models.subscription import Subscription

        try:
            tier_id = int(tier_key)
        except (TypeError, ValueError):
            return False
        if not db.session.get(SubscriptionTier, tier_id):
            return False

        subscription = organization.subscription
        if not subscription:
            subscription = Subscription(
                organization_id=organization.id, tier=tier_key, status="active"
            )
            db.session.add(subscription)
        else:
            subscription.tier = tier_key
            subscription.status = "active"
        db.session.commit()
        return True

    @staticmethod
    def create_team_member_user(
        *,
        username: str,
        email: str,
        password: str,
        role_id: int,
        organization_id: int,
    ):
        new_user = User(
            username=username,
            email=email,
            role_id=role_id,
            organization_id=organization_id,
            is_active=True,
            user_type="customer",
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        return new_user

    @staticmethod
    def update_team_member_user(*, user, data: dict, current_user_obj):
        if "first_name" in data:
            user.first_name = data["first_name"]
        if "last_name" in data:
            user.last_name = data["last_name"]
        if "email" in data:
            user.email = data["email"]
        if "phone" in data:
            user.phone = data["phone"]
        if "role_id" in data:
            role = OrganizationRouteService.get_scoped_role(data["role_id"])
            if role and not role.is_system_role:
                user.role_id = data["role_id"]

        if "is_organization_owner" in data:
            new_owner_status = data["is_organization_owner"]
            org_owner_role = OrganizationRouteService.get_org_owner_role()

            if new_owner_status and not user.is_organization_owner:
                other_owners = OrganizationRouteService.list_other_org_owners(
                    user.organization_id, user.id
                )
                for other_owner in other_owners:
                    other_owner.is_organization_owner = False
                    if org_owner_role:
                        other_owner.remove_role(org_owner_role)
                user.is_organization_owner = True
                if org_owner_role:
                    user.assign_role(org_owner_role, assigned_by=current_user_obj)
            elif not new_owner_status and user.is_organization_owner:
                user.is_organization_owner = False
                if org_owner_role:
                    user.remove_role(org_owner_role)

        if "is_active" in data:
            user.is_active = data["is_active"]
        db.session.commit()

    @staticmethod
    def toggle_user_active(*, user):
        user.is_active = not user.is_active
        db.session.commit()
        return user.is_active
