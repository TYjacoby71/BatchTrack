"""Developer organization service layer.

Synopsis:
Centralizes developer-facing organization lifecycle workflows, including org
creation, tier updates, and safe hard-delete execution with tenant scoping.

Glossary:
- Tier config: Presentation-ready availability map for subscription tiers.
- Safe hard delete: Permanent removal with link detachment and legacy snapshotting.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from flask_login import current_user

from app.extensions import db
from app.models import Organization, User


class OrganizationService:
    """Business logic that powers the developer organization workflows."""

    # --- List organizations ---
    # Purpose: Return all organizations ordered for developer support views.
    # Inputs: None.
    # Outputs: List of Organization rows sorted by name.
    @staticmethod
    def list_all_organizations() -> List[Organization]:
        return Organization.query.order_by(Organization.name.asc()).all()

    # --- Get selected organization ---
    # Purpose: Resolve a specific organization by ID for contextual support views.
    # Inputs: Optional organization ID.
    # Outputs: Organization instance or None.
    @staticmethod
    def get_selected_organization(org_id: Optional[int]) -> Optional[Organization]:
        return db.session.get(Organization, org_id) if org_id else None

    # --- Build available tiers ---
    # Purpose: Build minimal tier display data for create-organization forms.
    # Inputs: None.
    # Outputs: Dict keyed by tier ID containing tier names.
    @staticmethod
    def build_available_tiers() -> Dict[str, Dict[str, str]]:
        from app.models.subscription_tier import SubscriptionTier as _ST

        tiers = {}
        for tier in _ST.query.order_by(_ST.name).all():
            tiers[str(tier.id)] = {"name": tier.name}
        return tiers

    # --- Build tier config ---
    # Purpose: Build tier metadata including integration availability for edit screens.
    # Inputs: None.
    # Outputs: Dict keyed by tier ID with display name and is_available flag.
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

    # --- Create organization with owner ---
    # Purpose: Atomically create a customer organization and initial owner account.
    # Inputs: Form payload with org + owner fields and tier choice.
    # Outputs: Tuple(success flag, organization or None, status message).
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

    # --- Update organization ---
    # Purpose: Apply editable organization fields and optional subscription tier update.
    # Inputs: Organization row and form payload.
    # Outputs: Tuple(success flag, status message).
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

    # --- Upgrade organization tier ---
    # Purpose: Force an organization to a specific tier identifier from developer tools.
    # Inputs: Organization row and tier identifier string.
    # Outputs: Tuple(success flag, status message).
    @staticmethod
    def upgrade_organization(org: Organization, tier_identifier: str) -> Tuple[bool, str]:
        from app.models.subscription_tier import SubscriptionTier

        tier_record = SubscriptionTier.find_by_identifier(tier_identifier)
        if not tier_record:
            return False, "Invalid subscription tier"

        org.subscription_tier_id = tier_record.id
        db.session.commit()
        return True, f"Organization upgraded to {tier_identifier}"

    # --- Delete organization safely ---
    # Purpose: Hard-delete an organization without cross-tenant data loss or FK breakage.
    # Inputs: Target Organization row.
    # Outputs: Tuple(success flag, status message with archive/detach summary).
    @staticmethod
    def delete_organization(org: Organization) -> Tuple[bool, str]:
        org_id = org.id
        org_name = org.name
        try:
            from sqlalchemy import or_

            from app.models import (
                Batch,
                BatchContainer,
                BatchConsumable,
                BatchIngredient,
                BatchTimer,
                ExtraBatchContainer,
                ExtraBatchConsumable,
                ExtraBatchIngredient,
                InventoryHistory,
                InventoryItem,
                Product,
                ProductSKU,
                ProductVariant,
                Recipe,
                RecipeConsumable,
                RecipeIngredient,
                Role,
                UnifiedInventoryHistory,
            )
            from app.models.freshness_snapshot import FreshnessSnapshot
            from app.models.inventory_lot import InventoryLot
            from app.models.permission import role_permission
            from app.models.recipe import RecipeLineage
            from app.models.recipe_marketplace import RecipeModerationEvent
            from app.models.reservation import Reservation
            from app.models.retention import RetentionDeletionQueue
            from app.models.statistics import BatchStats, InventoryChangeLog, InventoryEfficiencyStats
            from app.models.user_preferences import UserPreferences
            from app.models.user_role_assignment import UserRoleAssignment
            from app.models.statistics import UserStats

            from app.services.developer.deletion_utils import (
                archive_marketplace_recipes,
                clear_user_foreign_keys,
                delete_org_scoped_rows,
                detach_external_recipe_links,
            )

            org_user_ids = [int(row[0]) for row in db.session.query(User.id).filter(User.organization_id == org_id).all()]
            org_recipe_ids = [int(row[0]) for row in db.session.query(Recipe.id).filter(Recipe.organization_id == org_id).all()]
            org_batch_ids = [int(row[0]) for row in db.session.query(Batch.id).filter(Batch.organization_id == org_id).all()]
            org_inventory_ids = [
                int(row[0])
                for row in db.session.query(InventoryItem.id).filter(InventoryItem.organization_id == org_id).all()
            ]
            org_product_ids = [
                int(row[0]) for row in db.session.query(Product.id).filter(Product.organization_id == org_id).all()
            ]
            org_variant_ids = [
                int(row[0])
                for row in db.session.query(ProductVariant.id).filter(ProductVariant.organization_id == org_id).all()
            ]
            org_role_ids = [
                int(row[0])
                for row in db.session.query(Role.id).filter(
                    Role.organization_id == org_id,
                    Role.is_system_role.is_(False),
                ).all()
            ]

            org_recipes = Recipe.query.filter(Recipe.id.in_(org_recipe_ids)).all() if org_recipe_ids else []
            marketplace_recipe_count = sum(
                1
                for recipe in org_recipes
                if (
                    bool(recipe.is_public)
                    or bool(recipe.is_for_sale)
                    or recipe.marketplace_status == "listed"
                    or int(recipe.purchase_count or 0) > 0
                    or int(recipe.download_count or 0) > 0
                )
            )
            archive_path = archive_marketplace_recipes(org, org_recipes)
            detached_links = detach_external_recipe_links(
                org_id,
                org_recipe_ids,
                archive_path=archive_path,
            ) if org_recipe_ids else 0

            if org_user_ids:
                clear_user_foreign_keys(org_user_ids)
                UserRoleAssignment.query.filter(
                    UserRoleAssignment.user_id.in_(org_user_ids)
                ).delete(synchronize_session=False)
                UserPreferences.query.filter(
                    UserPreferences.user_id.in_(org_user_ids)
                ).delete(synchronize_session=False)
                UserStats.query.filter(
                    UserStats.user_id.in_(org_user_ids)
                ).delete(synchronize_session=False)

            # Child tables are not guaranteed to carry organization_id; clear by parent IDs first.
            if org_recipe_ids:
                RecipeIngredient.query.filter(
                    RecipeIngredient.recipe_id.in_(org_recipe_ids)
                ).delete(synchronize_session=False)
                RecipeConsumable.query.filter(
                    RecipeConsumable.recipe_id.in_(org_recipe_ids)
                ).delete(synchronize_session=False)
                RecipeModerationEvent.query.filter(
                    RecipeModerationEvent.recipe_id.in_(org_recipe_ids)
                ).delete(synchronize_session=False)
                RecipeLineage.query.filter(
                    RecipeLineage.recipe_id.in_(org_recipe_ids)
                ).delete(synchronize_session=False)
                RetentionDeletionQueue.query.filter(
                    RetentionDeletionQueue.recipe_id.in_(org_recipe_ids)
                ).delete(synchronize_session=False)

            if org_batch_ids:
                BatchIngredient.query.filter(
                    BatchIngredient.batch_id.in_(org_batch_ids)
                ).delete(synchronize_session=False)
                BatchContainer.query.filter(
                    BatchContainer.batch_id.in_(org_batch_ids)
                ).delete(synchronize_session=False)
                BatchConsumable.query.filter(
                    BatchConsumable.batch_id.in_(org_batch_ids)
                ).delete(synchronize_session=False)
                ExtraBatchContainer.query.filter(
                    ExtraBatchContainer.batch_id.in_(org_batch_ids)
                ).delete(synchronize_session=False)
                ExtraBatchIngredient.query.filter(
                    ExtraBatchIngredient.batch_id.in_(org_batch_ids)
                ).delete(synchronize_session=False)
                ExtraBatchConsumable.query.filter(
                    ExtraBatchConsumable.batch_id.in_(org_batch_ids)
                ).delete(synchronize_session=False)
                BatchTimer.query.filter(
                    BatchTimer.batch_id.in_(org_batch_ids)
                ).delete(synchronize_session=False)
                BatchStats.query.filter(
                    BatchStats.batch_id.in_(org_batch_ids)
                ).delete(synchronize_session=False)
                InventoryHistory.query.filter(
                    or_(
                        InventoryHistory.batch_id.in_(org_batch_ids),
                        InventoryHistory.used_for_batch_id.in_(org_batch_ids),
                    )
                ).delete(synchronize_session=False)
                UnifiedInventoryHistory.query.filter(
                    or_(
                        UnifiedInventoryHistory.batch_id.in_(org_batch_ids),
                        UnifiedInventoryHistory.used_for_batch_id.in_(org_batch_ids),
                    )
                ).delete(synchronize_session=False)
                InventoryLot.query.filter(
                    InventoryLot.batch_id.in_(org_batch_ids)
                ).delete(synchronize_session=False)
                Reservation.query.filter(
                    Reservation.source_batch_id.in_(org_batch_ids)
                ).update(
                    {Reservation.source_batch_id: None},
                    synchronize_session=False,
                )
                ProductSKU.query.filter(
                    ProductSKU.batch_id.in_(org_batch_ids)
                ).update(
                    {ProductSKU.batch_id: None},
                    synchronize_session=False,
                )

            if org_inventory_ids:
                Reservation.query.filter(
                    or_(
                        Reservation.product_item_id.in_(org_inventory_ids),
                        Reservation.reserved_item_id.in_(org_inventory_ids),
                    )
                ).delete(synchronize_session=False)
                InventoryHistory.query.filter(
                    InventoryHistory.inventory_item_id.in_(org_inventory_ids)
                ).delete(synchronize_session=False)
                UnifiedInventoryHistory.query.filter(
                    or_(
                        UnifiedInventoryHistory.inventory_item_id.in_(org_inventory_ids),
                        UnifiedInventoryHistory.container_id.in_(org_inventory_ids),
                    )
                ).delete(synchronize_session=False)
                InventoryLot.query.filter(
                    InventoryLot.inventory_item_id.in_(org_inventory_ids)
                ).delete(synchronize_session=False)
                InventoryEfficiencyStats.query.filter(
                    InventoryEfficiencyStats.inventory_item_id.in_(org_inventory_ids)
                ).delete(synchronize_session=False)
                InventoryChangeLog.query.filter(
                    InventoryChangeLog.inventory_item_id.in_(org_inventory_ids)
                ).delete(synchronize_session=False)
                FreshnessSnapshot.query.filter(
                    FreshnessSnapshot.inventory_item_id.in_(org_inventory_ids)
                ).delete(synchronize_session=False)
                ProductSKU.query.filter(
                    or_(
                        ProductSKU.inventory_item_id.in_(org_inventory_ids),
                        ProductSKU.container_id.in_(org_inventory_ids),
                    )
                ).delete(synchronize_session=False)

            if org_product_ids:
                ProductVariant.query.filter(
                    ProductVariant.product_id.in_(org_product_ids)
                ).delete(synchronize_session=False)
            if org_product_ids or org_variant_ids:
                sku_filters = []
                if org_product_ids:
                    sku_filters.append(ProductSKU.product_id.in_(org_product_ids))
                if org_variant_ids:
                    sku_filters.append(ProductSKU.variant_id.in_(org_variant_ids))
                ProductSKU.query.filter(or_(*sku_filters)).delete(synchronize_session=False)

            if org_role_ids:
                db.session.execute(
                    role_permission.delete().where(role_permission.c.role_id.in_(org_role_ids))
                )

            delete_org_scoped_rows(org_id)

            target_org = db.session.get(Organization, org_id)
            if target_org is not None:
                db.session.delete(target_org)

            db.session.commit()

            message = f'Organization "{org_name}" deleted.'
            if archive_path:
                message += (
                    f" Archived {marketplace_recipe_count} marketplace recipe snapshot(s) to {archive_path}."
                )
            if detached_links:
                message += f" Detached {detached_links} external recipe link(s)."
            return True, message
        except Exception as exc:  # pragma: no cover - defensive
            db.session.rollback()
            return False, str(exc)

    # --- Validate destructive-action confirmation ---
    # Purpose: Verify developer password and exact confirmation phrase before hard delete.
    # Inputs: Password input, typed confirmation text, expected confirmation phrase.
    # Outputs: Tuple(valid flag, error message when invalid).
    @staticmethod
    def validate_deletion(password: str, confirm_text: str, expected_confirm: str) -> Tuple[bool, str]:
        if not current_user.check_password(password or ""):
            return False, "Invalid developer password"
        if confirm_text != expected_confirm:
            return False, f'Confirmation text must match exactly: "{expected_confirm}"'
        return True, ""
