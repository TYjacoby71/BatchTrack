"""Developer subscription-tier route service.

Synopsis:
Owns subscription-tier route persistence and query operations so
`app/blueprints/developer/subscription_tiers.py` remains transport-focused.

Glossary:
- Module boundary: Defines the ownership scope and responsibilities for this module.
"""

from __future__ import annotations

from app.extensions import db
from app.models import Organization, Permission, SubscriptionTier
from app.models.addon import Addon


class SubscriptionTierRouteService:
    """Data/session helpers for developer subscription-tier routes."""

    @staticmethod
    def list_all_tiers_ordered():
        return SubscriptionTier.query.order_by(SubscriptionTier.name).all()

    @staticmethod
    def list_active_permissions_ordered():
        return (
            Permission.query.filter_by(is_active=True).order_by(Permission.name).all()
        )

    @staticmethod
    def list_active_permissions_for_names(*, names: list[str]):
        if not names:
            return []
        return Permission.query.filter(
            Permission.is_active.is_(True),
            Permission.name.in_(names),
        ).all()

    @staticmethod
    def list_base_permissions_excluding_names(*, excluded_names: list[str]):
        query = Permission.query.filter(Permission.is_active.is_(True))
        if excluded_names:
            query = query.filter(Permission.name.not_in(excluded_names))
        return query.order_by(Permission.name).all()

    @staticmethod
    def list_signup_customer_facing_paid_tiers():
        return (
            SubscriptionTier.query.filter_by(is_customer_facing=True)
            .filter(SubscriptionTier.billing_provider != "exempt")
            .order_by(SubscriptionTier.user_limit.asc(), SubscriptionTier.id.asc())
            .all()
        )

    @staticmethod
    def tier_name_exists(*, name: str) -> bool:
        return SubscriptionTier.query.filter_by(name=name).first() is not None

    @staticmethod
    def create_tier_with_relationships(
        *,
        tier: SubscriptionTier,
        permission_ids: set[int],
        addon_ids: list[int] | None,
        included_ids: list[int] | None,
    ) -> SubscriptionTier:
        db.session.add(tier)
        db.session.flush()

        selected_addon_ids = set(addon_ids or []) | set(included_ids or [])
        if selected_addon_ids:
            selected_addons = Addon.query.filter(Addon.id.in_(selected_addon_ids)).all()
            addon_perm_names = [
                a.permission_name for a in selected_addons if a.permission_name
            ]
            if addon_perm_names:
                addon_perms = (
                    SubscriptionTierRouteService.list_active_permissions_for_names(
                        names=addon_perm_names
                    )
                )
                permission_ids.update({p.id for p in addon_perms})

        if permission_ids:
            tier.permissions = Permission.query.filter(
                Permission.id.in_(permission_ids)
            ).all()
        if addon_ids is not None:
            tier.allowed_addons = (
                Addon.query.filter(Addon.id.in_(addon_ids)).all() if addon_ids else []
            )
        if included_ids is not None:
            tier.included_addons = (
                Addon.query.filter(Addon.id.in_(included_ids)).all()
                if included_ids
                else []
            )

        db.session.commit()
        return tier

    @staticmethod
    def list_active_addons_ordered():
        return Addon.query.filter_by(is_active=True).order_by(Addon.name).all()

    @staticmethod
    def get_tier(*, tier_id: int):
        return db.session.get(SubscriptionTier, tier_id)

    @staticmethod
    def update_tier_relationships(
        *,
        tier: SubscriptionTier,
        permission_ids: set[int],
        addon_ids: list[int] | None,
        included_ids: list[int] | None,
    ) -> None:
        tier.allowed_addons = (
            Addon.query.filter(Addon.id.in_(addon_ids)).all() if addon_ids else []
        )
        tier.included_addons = (
            Addon.query.filter(Addon.id.in_(included_ids)).all() if included_ids else []
        )

        selected_addon_ids = set(addon_ids or []) | set(included_ids or [])
        if selected_addon_ids:
            selected_addons = Addon.query.filter(Addon.id.in_(selected_addon_ids)).all()
            addon_perm_names = [
                a.permission_name for a in selected_addons if a.permission_name
            ]
            if addon_perm_names:
                addon_perms = (
                    SubscriptionTierRouteService.list_active_permissions_for_names(
                        names=addon_perm_names
                    )
                )
                permission_ids.update({p.id for p in addon_perms})

        tier.permissions = Permission.query.filter(
            Permission.id.in_(permission_ids)
        ).all()
        db.session.commit()

    @staticmethod
    def count_organizations_on_tier(*, tier_id: int) -> int:
        return Organization.query.filter_by(subscription_tier_id=tier_id).count()

    @staticmethod
    def delete_tier(*, tier: SubscriptionTier) -> None:
        db.session.delete(tier)
        db.session.commit()

    @staticmethod
    def list_customer_facing_tiers():
        return SubscriptionTier.query.filter_by(is_customer_facing=True).all()

    @staticmethod
    def rollback_session() -> None:
        db.session.rollback()
