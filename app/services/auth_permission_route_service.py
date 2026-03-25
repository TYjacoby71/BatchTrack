"""Auth-permission route service boundary.

Synopsis:
Encapsulates auth permission-management route data/session access so
`auth/permissions.py` stays transport-focused.
"""

from __future__ import annotations

from app.extensions import db
from app.models import DeveloperPermission, Permission, Role
from app.models.developer_role import DeveloperRole
from app.models.subscription_tier import SubscriptionTier


class AuthPermissionRouteService:
    """Data/session helpers for auth permission/role route workflows."""

    @staticmethod
    def get_subscription_tier_by_key(*, tier_key: str | None) -> SubscriptionTier | None:
        try:
            tier_id = int(tier_key)
        except (TypeError, ValueError):
            return None
        return db.session.get(SubscriptionTier, tier_id)

    @staticmethod
    def list_permissions_for_names(*, names: list[str]) -> list[Permission]:
        if not names:
            return []
        return Permission.query.filter(
            Permission.name.in_(names),
            Permission.is_active,
        ).all()

    @staticmethod
    def list_all_developer_permissions() -> list[DeveloperPermission]:
        return DeveloperPermission.query.all()

    @staticmethod
    def list_all_permissions() -> list[Permission]:
        return Permission.query.all()

    @staticmethod
    def find_developer_permission_by_name(*, name: str) -> DeveloperPermission | None:
        return DeveloperPermission.query.filter_by(name=name).first()

    @staticmethod
    def find_permission_by_name(*, name: str) -> Permission | None:
        return Permission.query.filter_by(name=name).first()

    @staticmethod
    def upsert_permission_matrix_entry(
        *,
        name: str,
        dev_enabled: bool,
        customer_enabled: bool,
        is_active: bool,
        dev_description: str,
        dev_category: str,
        org_description: str,
        org_category: str,
    ) -> None:
        dev_perm = AuthPermissionRouteService.find_developer_permission_by_name(name=name)
        org_perm = AuthPermissionRouteService.find_permission_by_name(name=name)

        if dev_enabled:
            if not dev_perm:
                dev_perm = DeveloperPermission(
                    name=name,
                    description=dev_description,
                    category=dev_category,
                    is_active=is_active,
                )
                db.session.add(dev_perm)
            else:
                dev_perm.description = dev_description
                dev_perm.category = dev_category
                dev_perm.is_active = is_active
        elif dev_perm:
            dev_perm.developer_roles = []
            db.session.delete(dev_perm)

        if customer_enabled:
            if not org_perm:
                org_perm = Permission(
                    name=name,
                    description=org_description,
                    category=org_category,
                    is_active=is_active,
                )
                db.session.add(org_perm)
            else:
                org_perm.description = org_description
                org_perm.category = org_category
                org_perm.is_active = is_active
        elif org_perm:
            org_perm.roles = []
            try:
                for tier in org_perm.tiers.all():
                    org_perm.tiers.remove(tier)
            except Exception:
                pass
            db.session.delete(org_perm)

        system_admin_role = DeveloperRole.query.filter_by(name="system_admin").first()
        if system_admin_role:
            system_admin_role.permissions = DeveloperPermission.query.filter_by(
                is_active=True
            ).all()

        org_owner_role = Role.query.filter_by(
            name="organization_owner",
            is_system_role=True,
        ).first()
        if org_owner_role:
            org_owner_role.permissions = Permission.query.filter_by(is_active=True).all()

        db.session.commit()

    @staticmethod
    def get_developer_permission_or_404(*, permission_id: int) -> DeveloperPermission:
        return db.get_or_404(DeveloperPermission, permission_id)

    @staticmethod
    def get_permission_or_404(*, permission_id: int) -> Permission:
        return db.get_or_404(Permission, permission_id)

    @staticmethod
    def set_permission_active_status(*, permission: DeveloperPermission | Permission, is_active: bool) -> None:
        permission.is_active = is_active
        db.session.commit()

    @staticmethod
    def list_all_roles() -> list[Role]:
        return Role.query.all()

    @staticmethod
    def list_organization_roles(*, organization_id: int | None) -> list[Role]:
        return Role.get_organization_roles(organization_id)

    @staticmethod
    def list_active_permissions() -> list[Permission]:
        return Permission.query.filter_by(is_active=True).all()

    @staticmethod
    def list_permissions_by_ids(*, permission_ids: list[int]) -> list[Permission]:
        if not permission_ids:
            return []
        return Permission.query.filter(Permission.id.in_(permission_ids)).all()

    @staticmethod
    def create_role_with_permissions(
        *,
        name: str,
        description: str | None,
        organization_id: int | None,
        created_by: int | None,
        permissions: list[Permission],
    ) -> Role:
        role = Role(
            name=name,
            description=description,
            organization_id=organization_id,
            created_by=created_by,
        )
        role.permissions = permissions
        db.session.add(role)
        db.session.commit()
        return role

    @staticmethod
    def get_role_or_404(*, role_id: int) -> Role:
        return db.get_or_404(Role, role_id)

    @staticmethod
    def update_role_with_permissions(
        *,
        role: Role,
        name: str | None,
        description: str | None,
        permissions: list[Permission] | None = None,
    ) -> None:
        role.name = name or role.name
        role.description = description if description is not None else role.description
        if permissions is not None:
            role.permissions = permissions
        db.session.commit()

    @staticmethod
    def rollback_session() -> None:
        db.session.rollback()
