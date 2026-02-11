from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from app.extensions import db
from app.models import InventoryItem, Organization, ProductCategory, Recipe, User
from app.models.recipe import RecipeLineage
from app.services.billing_service import BillingService
from app.services.developer.organization_service import OrganizationService
from app.services.developer.user_service import UserService


def _uniq(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


def test_delete_organization_archives_marketplace_recipes_and_detaches_links(app, tmp_path):
    with app.app_context():
        app.config["DELETION_ARCHIVE_DIR"] = str(tmp_path)
        category = ProductCategory.query.filter_by(name="Uncategorized").first()
        assert category is not None

        seller_org = Organization(name=_uniq("seller_org"))
        buyer_org = Organization(name=_uniq("buyer_org"))
        db.session.add_all([seller_org, buyer_org])
        db.session.flush()

        seller_user = User(
            username=_uniq("seller_user"),
            email=f"{_uniq('seller')}@example.com",
            organization_id=seller_org.id,
            user_type="customer",
            is_active=True,
        )
        buyer_user = User(
            username=_uniq("buyer_user"),
            email=f"{_uniq('buyer')}@example.com",
            organization_id=buyer_org.id,
            user_type="customer",
            is_active=True,
        )
        db.session.add_all([seller_user, buyer_user])
        db.session.flush()

        seller_recipe = Recipe(
            name=_uniq("seller_recipe"),
            organization_id=seller_org.id,
            category_id=category.id,
            status="published",
            is_current=True,
            is_public=True,
            is_for_sale=True,
            marketplace_status="listed",
            purchase_count=3,
            download_count=7,
            created_by=seller_user.id,
        )
        db.session.add(seller_recipe)
        db.session.flush()
        seller_recipe_id = seller_recipe.id

        imported_recipe = Recipe(
            name=_uniq("imported_recipe"),
            organization_id=buyer_org.id,
            category_id=category.id,
            status="published",
            is_current=True,
            created_by=buyer_user.id,
            org_origin_purchased=True,
            org_origin_source_org_id=seller_org.id,
            org_origin_source_recipe_id=seller_recipe_id,
            cloned_from_id=seller_recipe_id,
            root_recipe_id=seller_recipe_id,
        )
        db.session.add(imported_recipe)
        db.session.flush()

        lineage_event = RecipeLineage(
            organization_id=buyer_org.id,
            recipe_id=imported_recipe.id,
            source_recipe_id=seller_recipe_id,
            event_type="IMPORT",
            user_id=buyer_user.id,
        )
        db.session.add(lineage_event)
        db.session.commit()

        success, message = OrganizationService.delete_organization(seller_org)
        assert success, message
        assert "Archived" in message

        assert db.session.get(Organization, seller_org.id) is None

        external_recipe = db.session.get(Recipe, imported_recipe.id)
        assert external_recipe is not None
        assert external_recipe.org_origin_source_org_id is None
        assert external_recipe.org_origin_source_recipe_id is None
        assert external_recipe.cloned_from_id is None
        assert external_recipe.root_recipe_id == external_recipe.id

        external_lineage = db.session.get(RecipeLineage, lineage_event.id)
        assert external_lineage is not None
        assert external_lineage.source_recipe_id is None

        archive_files = list(Path(tmp_path).glob("org_*_marketplace_recipes_*.json"))
        assert len(archive_files) == 1
        payload = json.loads(archive_files[0].read_text(encoding="utf-8"))
        assert payload["organization"]["id"] == seller_org.id
        assert payload["recipe_count"] == 1
        assert payload["recipes"][0]["id"] == seller_recipe_id


def test_hard_delete_user_preserves_org_records_and_nulls_user_links(app):
    with app.app_context():
        category = ProductCategory.query.filter_by(name="Uncategorized").first()
        assert category is not None

        org = Organization(name=_uniq("hard_delete_org"))
        db.session.add(org)
        db.session.flush()

        target_user = User(
            username=_uniq("target_user"),
            email=f"{_uniq('target')}@example.com",
            organization_id=org.id,
            user_type="customer",
            is_active=True,
        )
        remaining_user = User(
            username=_uniq("remaining_user"),
            email=f"{_uniq('remaining')}@example.com",
            organization_id=org.id,
            user_type="customer",
            is_active=True,
        )
        db.session.add_all([target_user, remaining_user])
        db.session.flush()

        recipe = Recipe(
            name=_uniq("target_recipe"),
            organization_id=org.id,
            category_id=category.id,
            status="published",
            is_current=True,
            created_by=target_user.id,
        )
        inventory_item = InventoryItem(
            name=_uniq("target_inventory"),
            organization_id=org.id,
            type="ingredient",
            unit="gram",
            quantity=1.0,
            cost_per_unit=1.0,
            created_by=target_user.id,
        )
        db.session.add_all([recipe, inventory_item])
        db.session.commit()

        success, message = UserService.hard_delete_user(target_user)
        assert success, message

        assert db.session.get(User, target_user.id) is None
        assert db.session.get(User, remaining_user.id) is not None

        persisted_recipe = db.session.get(Recipe, recipe.id)
        assert persisted_recipe is not None
        assert persisted_recipe.created_by is None

        persisted_item = db.session.get(InventoryItem, inventory_item.id)
        assert persisted_item is not None
        assert persisted_item.created_by is None


def test_hard_delete_user_rejects_developer_accounts(app):
    with app.app_context():
        developer = User(
            username=_uniq("dev"),
            email=f"{_uniq('dev')}@example.com",
            user_type="developer",
            is_active=True,
        )
        db.session.add(developer)
        db.session.commit()

        success, message = UserService.hard_delete_user(developer)
        assert success is False
        assert "developer" in message.lower()


def test_delete_organization_cancels_stripe_subscription(app, monkeypatch):
    cancelled_customer_ids: list[str] = []

    def _fake_cancel_subscription(stripe_customer_id: str) -> bool:
        cancelled_customer_ids.append(stripe_customer_id)
        return True

    monkeypatch.setattr(
        BillingService,
        "cancel_subscription",
        staticmethod(_fake_cancel_subscription),
    )

    with app.app_context():
        org = Organization(name=_uniq("org_with_stripe"), stripe_customer_id="cus_test_delete_org")
        db.session.add(org)
        db.session.commit()

        success, message = OrganizationService.delete_organization(org)
        assert success, message
        assert "Stripe subscription canceled" in message
        assert cancelled_customer_ids == ["cus_test_delete_org"]
        assert db.session.get(Organization, org.id) is None


def test_delete_organization_aborts_when_stripe_cancel_fails(app, monkeypatch):
    def _fake_cancel_subscription(_stripe_customer_id: str) -> bool:
        return False

    monkeypatch.setattr(
        BillingService,
        "cancel_subscription",
        staticmethod(_fake_cancel_subscription),
    )

    with app.app_context():
        org = Organization(name=_uniq("org_stripe_fail"), stripe_customer_id="cus_fail_delete_org")
        db.session.add(org)
        db.session.commit()

        success, message = OrganizationService.delete_organization(org)
        assert success is False
        assert "Failed to cancel Stripe subscription" in message
        assert db.session.get(Organization, org.id) is not None


def test_hard_delete_user_cancels_subscription_for_final_customer(app, monkeypatch):
    cancelled_customer_ids: list[str] = []

    def _fake_cancel_subscription(stripe_customer_id: str) -> bool:
        cancelled_customer_ids.append(stripe_customer_id)
        return True

    monkeypatch.setattr(
        BillingService,
        "cancel_subscription",
        staticmethod(_fake_cancel_subscription),
    )

    with app.app_context():
        org = Organization(
            name=_uniq("org_user_cancel"),
            stripe_customer_id="cus_final_customer",
        )
        db.session.add(org)
        db.session.flush()

        user = User(
            username=_uniq("last_customer"),
            email=f"{_uniq('last')}@example.com",
            organization_id=org.id,
            user_type="customer",
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()

        success, message = UserService.hard_delete_user(user)
        assert success, message
        assert "Stripe subscription canceled" in message
        assert cancelled_customer_ids == ["cus_final_customer"]
        assert db.session.get(User, user.id) is None


def test_hard_delete_user_aborts_when_final_customer_cancel_fails(app, monkeypatch):
    def _fake_cancel_subscription(_stripe_customer_id: str) -> bool:
        return False

    monkeypatch.setattr(
        BillingService,
        "cancel_subscription",
        staticmethod(_fake_cancel_subscription),
    )

    with app.app_context():
        org = Organization(
            name=_uniq("org_user_cancel_fail"),
            stripe_customer_id="cus_cancel_fail",
        )
        db.session.add(org)
        db.session.flush()

        user = User(
            username=_uniq("last_customer_fail"),
            email=f"{_uniq('last_fail')}@example.com",
            organization_id=org.id,
            user_type="customer",
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()

        success, message = UserService.hard_delete_user(user)
        assert success is False
        assert "Failed to cancel Stripe subscription" in message
        assert db.session.get(User, user.id) is not None
