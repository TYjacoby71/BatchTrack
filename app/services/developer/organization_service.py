from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from flask_login import current_user

from app.extensions import db
from app.models import Organization, User


class OrganizationService:
    """Business logic that powers the developer organization workflows."""

    @staticmethod
    def list_all_organizations() -> List[Organization]:
        return Organization.query.order_by(Organization.name.asc()).all()

    @staticmethod
    def get_selected_organization(org_id: Optional[int]) -> Optional[Organization]:
        return db.session.get(Organization, org_id) if org_id else None

    @staticmethod
    def build_available_tiers() -> Dict[str, Dict[str, str]]:
        from app.models.subscription_tier import SubscriptionTier as _ST

        tiers = {}
        for tier in _ST.query.order_by(_ST.name).all():
            tiers[str(tier.id)] = {"name": tier.name}
        return tiers

    @staticmethod
    def build_tier_config() -> Dict[str, Dict[str, str]]:
        from app.models.subscription_tier import SubscriptionTier as _ST

        tiers = {}
        for tier in _ST.query.order_by(_ST.name).all():
            tiers[str(tier.id)] = {
                "name": tier.name,
                "is_available": tier.has_valid_integration or tier.is_billing_exempt,
            }
        return tiers

    @staticmethod
    def create_organization_with_owner(form_data: Dict[str, str]) -> Tuple[bool, Optional[Organization], str]:
        name = form_data.get("name")
        username = form_data.get("username")
        email = form_data.get("email")
        password = form_data.get("password")
        subscription_tier = form_data.get("subscription_tier", "free")

        if not all([name, username, email, password]):
            return False, None, "Missing required fields"

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return False, None, "Username already exists"

        try:
            org = Organization(name=name, contact_email=email, is_active=True)
            db.session.add(org)
            db.session.flush()

            from app.models.subscription_tier import SubscriptionTier

            tier_record = SubscriptionTier.find_by_identifier(subscription_tier)
            if tier_record:
                org.subscription_tier_id = tier_record.id
            else:
                exempt_tier = SubscriptionTier.find_by_identifier("exempt")
                if exempt_tier:
                    org.subscription_tier_id = exempt_tier.id

            owner_user = User(
                username=username,
                email=email,
                first_name=form_data.get("first_name"),
                last_name=form_data.get("last_name"),
                phone=form_data.get("phone"),
                organization_id=org.id,
                user_type="customer",
                is_organization_owner=True,
                is_active=True,
            )
            owner_user.set_password(password)
            db.session.add(owner_user)
            db.session.flush()

            from app.models.role import Role

            org_owner_role = Role.query.filter_by(
                name="organization_owner", is_system_role=True
            ).first()
            if org_owner_role:
                owner_user.assign_role(org_owner_role)

            db.session.commit()
            return True, org, "Organization created"
        except Exception as exc:
            db.session.rollback()
            return False, None, str(exc)

    @staticmethod
    def update_organization(org: Organization, form_data: Dict[str, str]) -> Tuple[bool, str]:
        org.name = form_data.get("name", org.name)
        org.is_active = form_data.get("is_active") == "true"

        new_tier = form_data.get("subscription_tier")
        if new_tier:
            from app.models.subscription_tier import SubscriptionTier

            tier_record = SubscriptionTier.find_by_identifier(new_tier)
            if tier_record:
                org.subscription_tier_id = tier_record.id

        try:
            db.session.commit()
            return True, "Organization updated successfully"
        except Exception as exc:  # pragma: no cover - defensive
            db.session.rollback()
            return False, str(exc)

    @staticmethod
    def upgrade_organization(org: Organization, tier_identifier: str) -> Tuple[bool, str]:
        from app.models.subscription_tier import SubscriptionTier

        tier_record = SubscriptionTier.find_by_identifier(tier_identifier)
        if not tier_record:
            return False, "Invalid subscription tier"

        org.subscription_tier_id = tier_record.id
        db.session.commit()
        return True, f"Organization upgraded to {tier_identifier}"

    @staticmethod
    def delete_organization(org: Organization) -> Tuple[bool, str]:
        org_id = org.id
        try:
            from app.models import (
                Batch,
                BatchContainer,
                BatchIngredient,
                BatchTimer,
                Category,
                ExtraBatchContainer,
                ExtraBatchIngredient,
                InventoryItem,
                Permission,
                Product,
                ProductSKU,
                Recipe,
                RecipeIngredient,
                Role,
            )
            from app.models.reservation import Reservation
            from app.models.subscription_tier import Subscription
            from app.models.user_role_assignment import UserRoleAssignment

            ExtraBatchContainer.query.filter_by(organization_id=org_id).delete()
            ExtraBatchIngredient.query.filter_by(organization_id=org_id).delete()
            BatchContainer.query.filter_by(organization_id=org_id).delete()
            BatchIngredient.query.filter_by(organization_id=org_id).delete()
            BatchTimer.query.filter_by(organization_id=org_id).delete()
            Batch.query.filter_by(organization_id=org_id).delete()

            recipe_ids = [r.id for r in Recipe.query.filter_by(organization_id=org_id).all()]
            if recipe_ids:
                RecipeIngredient.query.filter(RecipeIngredient.recipe_id.in_(recipe_ids)).delete()
            Recipe.query.filter_by(organization_id=org_id).delete()

            Reservation.query.filter_by(organization_id=org_id).delete()
            ProductSKU.query.filter_by(organization_id=org_id).delete()
            Product.query.filter_by(organization_id=org_id).delete()
            InventoryItem.query.filter_by(organization_id=org_id).delete()
            Category.query.filter_by(organization_id=org_id).delete()

            org_user_ids = [u.id for u in User.query.filter_by(organization_id=org_id).all()]
            if org_user_ids:
                UserRoleAssignment.query.filter(
                    UserRoleAssignment.user_id.in_(org_user_ids)
                ).delete()

            Role.query.filter_by(organization_id=org_id, is_system_role=False).delete()

            subscription = Subscription.query.filter_by(organization_id=org_id).first()
            if subscription:
                db.session.delete(subscription)

            User.query.filter_by(organization_id=org_id).delete()
            db.session.delete(org)
            db.session.commit()
            return True, "Organization deleted"
        except Exception as exc:  # pragma: no cover - defensive
            db.session.rollback()
            return False, str(exc)

    @staticmethod
    def validate_deletion(password: str, confirm_text: str, expected_confirm: str) -> Tuple[bool, str]:
        if not current_user.check_password(password or ""):
            return False, "Invalid developer password"
        if confirm_text != expected_confirm:
            return False, f'Confirmation text must match exactly: "{expected_confirm}"'
        return True, ""
