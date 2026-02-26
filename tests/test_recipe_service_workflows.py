"""Tests for recipe service workflows.

Synopsis:
Validates recipe CRUD and marketplace guardrails for versions.

Glossary:
- Marketplace: Public listing configuration.
- Versioning: Master/variation/test behavior.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from flask import current_app
from flask_login import login_user

from app.extensions import db
from app.models import Recipe
from app.models.batch import Batch
from app.models.global_item import GlobalItem
from app.models.inventory import InventoryItem
from app.models.models import Organization, User
from app.models.product_category import ProductCategory
from app.services.lineage_service import generate_lineage_id
from app.services.recipe_service import (
    create_recipe,
    create_test_version,
    duplicate_recipe,
    promote_test_to_current,
    update_recipe,
)
from app.utils.recipe_batch_counts import count_batches_for_recipe_lineage


def _unique_name(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _create_category(name_prefix: str = "Category") -> ProductCategory:
    category = ProductCategory(name=_unique_name(name_prefix))
    db.session.add(category)
    db.session.commit()
    return category


def _create_ingredient(org: Organization | None = None) -> InventoryItem:
    if org is None:
        org = Organization.query.first()
    ingredient = InventoryItem(
        name=_unique_name("Ingredient"),
        unit="oz",
        type="ingredient",
        quantity=10.0,
        organization_id=org.id if org else None,
    )
    db.session.add(ingredient)
    db.session.commit()
    return ingredient


def _test_recipe_payload(
    *, ingredient_id: int, category_id: int, instructions: str
) -> dict:
    return {
        "instructions": instructions,
        "yield_amount": 6,
        "yield_unit": "oz",
        "ingredients": [{"item_id": ingredient_id, "quantity": 6, "unit": "oz"}],
        "consumables": [],
        "allowed_containers": [],
        "label_prefix": "",
        "category_id": category_id,
    }


@pytest.mark.usefixtures("app_context")
def test_create_recipe_public_marketplace_listing():
    category = _create_category("Marketplace")
    ingredient = _create_ingredient()

    ok, recipe_or_err = create_recipe(
        name=_unique_name("Public Soap"),
        instructions="Blend and pour",
        yield_amount=12,
        yield_unit="oz",
        ingredients=[{"item_id": ingredient.id, "quantity": 12, "unit": "oz"}],
        allowed_containers=[],
        label_prefix="PUB",
        category_id=category.id,
        sharing_scope="public",
        is_public=True,
        is_for_sale=True,
        sale_price="19.99",
        marketplace_notes="Premium listing",
        public_description="A showcase recipe for the marketplace",
        status="published",
    )
    assert ok, f"Expected creation success, got: {recipe_or_err}"
    recipe: Recipe = recipe_or_err

    assert recipe.sharing_scope == "public"
    assert recipe.is_public is True
    assert recipe.is_for_sale is True
    assert recipe.sale_price == Decimal("19.99")
    assert recipe.marketplace_status == "listed"
    assert recipe.marketplace_notes == "Premium listing"
    assert recipe.public_description.startswith("A showcase")


@pytest.mark.usefixtures("app_context")
def test_duplicate_recipe_returns_private_template():
    category = _create_category("Clone")
    ingredient = _create_ingredient()

    ok, recipe = create_recipe(
        name=_unique_name("Clone Ready"),
        instructions="Mix ingredients",
        yield_amount=8,
        yield_unit="oz",
        ingredients=[{"item_id": ingredient.id, "quantity": 8, "unit": "oz"}],
        allowed_containers=[],
        label_prefix="CLN",
        category_id=category.id,
        sharing_scope="public",
        is_public=True,
        is_for_sale=False,
        status="published",
    )
    assert ok, f"Failed to create base recipe: {recipe}"

    user = User.query.first()
    with current_app.test_request_context():
        login_user(user)
        dup_ok, payload_or_err = duplicate_recipe(recipe.id)
    assert dup_ok, f"Duplicate failed: {payload_or_err}"
    template = payload_or_err["template"]

    assert template.sharing_scope == "private"
    assert template.is_public is False
    assert template.is_for_sale is False
    assert template.sale_price is None
    assert template.cloned_from_id == recipe.id


@pytest.mark.usefixtures("app_context")
def test_duplicate_recipe_maps_global_items_for_import():
    category = _create_category("ImportMap")

    # Seller org/user from fixtures
    seller_org = Organization.query.first()
    seller_user = User.query.filter_by(organization_id=seller_org.id).first()

    # Buyer org/user setup
    tier = seller_org.subscription_tier
    buyer_org = Organization(name=_unique_name("Buyer Org"), subscription_tier=tier)
    db.session.add(buyer_org)
    db.session.commit()

    buyer_user = User(
        email=f'{_unique_name("buyer")}@example.com',
        username=_unique_name("buyer"),
        password_hash="test_hash",
        is_verified=True,
        organization_id=buyer_org.id,
    )
    db.session.add(buyer_user)
    db.session.commit()

    # Shared global item plus org-specific inventory
    global_item = GlobalItem(
        name=_unique_name("Global Oil"), item_type="ingredient", default_unit="oz"
    )
    db.session.add(global_item)
    db.session.commit()

    seller_item = InventoryItem(
        name="Seller Oil",
        unit="oz",
        type="ingredient",
        quantity=25.0,
        organization_id=seller_org.id,
        global_item_id=global_item.id,
    )
    buyer_item = InventoryItem(
        name="Buyer Oil",
        unit="oz",
        type="ingredient",
        quantity=10.0,
        organization_id=buyer_org.id,
        global_item_id=global_item.id,
    )
    db.session.add_all([seller_item, buyer_item])
    db.session.commit()

    with current_app.test_request_context():
        login_user(seller_user)
        ok, recipe_or_err = create_recipe(
            name=_unique_name("Import Ready"),
            instructions="Mix thoroughly.",
            yield_amount=10,
            yield_unit="oz",
            ingredients=[{"item_id": seller_item.id, "quantity": 10, "unit": "oz"}],
            allowed_containers=[],
            label_prefix="IMP",
            category_id=category.id,
            sharing_scope="public",
            is_public=True,
            status="published",
        )
        assert ok, recipe_or_err
        recipe: Recipe = recipe_or_err

        login_user(buyer_user)
        dup_ok, payload_or_err = duplicate_recipe(
            recipe.id,
            allow_cross_org=True,
            target_org_id=buyer_org.id,
        )
        assert dup_ok, payload_or_err
        ingredient_payload = payload_or_err["ingredients"][0]
        assert ingredient_payload["global_item_id"] == global_item.id
        assert ingredient_payload["item_id"] == buyer_item.id


@pytest.mark.usefixtures("app_context")
def test_duplicate_recipe_creates_missing_inventory_for_import():
    category = _create_category("MissingImport")

    seller_org = Organization.query.first()
    seller_user = User.query.filter_by(organization_id=seller_org.id).first()

    tier = seller_org.subscription_tier
    buyer_org = Organization(name=_unique_name("Buyer Missing"), subscription_tier=tier)
    db.session.add(buyer_org)
    db.session.commit()

    buyer_user = User(
        email=f'{_unique_name("missing")}@example.com',
        username=_unique_name("missing"),
        password_hash="test_hash",
        is_verified=True,
        organization_id=buyer_org.id,
    )
    db.session.add(buyer_user)
    db.session.commit()

    global_item = GlobalItem(
        name=_unique_name("New Oil"), item_type="ingredient", default_unit="oz"
    )
    db.session.add(global_item)
    db.session.commit()

    seller_item = InventoryItem(
        name="Seller Only Oil",
        unit="oz",
        type="ingredient",
        quantity=12.0,
        organization_id=seller_org.id,
        global_item_id=global_item.id,
    )
    db.session.add(seller_item)
    db.session.commit()

    with current_app.test_request_context():
        login_user(seller_user)
        ok, recipe_or_err = create_recipe(
            name=_unique_name("Needs Inventory"),
            instructions="Blend oils.",
            yield_amount=6,
            yield_unit="oz",
            ingredients=[{"item_id": seller_item.id, "quantity": 6, "unit": "oz"}],
            allowed_containers=[],
            label_prefix="IMP2",
            category_id=category.id,
            sharing_scope="public",
            is_public=True,
            status="published",
        )
        assert ok, recipe_or_err
        recipe: Recipe = recipe_or_err

        login_user(buyer_user)
        dup_ok, payload_or_err = duplicate_recipe(
            recipe.id,
            allow_cross_org=True,
            target_org_id=buyer_org.id,
        )
        assert dup_ok, payload_or_err
        ingredient_payload = payload_or_err["ingredients"][0]

        buyer_created = InventoryItem.query.filter_by(
            organization_id=buyer_org.id,
            global_item_id=global_item.id,
        ).first()
        assert buyer_created is not None
        assert ingredient_payload["item_id"] == buyer_created.id


@pytest.mark.usefixtures("app_context")
def test_duplicate_recipe_creates_inventory_without_global_link():
    category = _create_category("NoGlobal")

    seller_org = Organization.query.first()
    seller_user = User.query.filter_by(organization_id=seller_org.id).first()

    tier = seller_org.subscription_tier
    buyer_org = Organization(
        name=_unique_name("Buyer NoGlobal"), subscription_tier=tier
    )
    db.session.add(buyer_org)
    db.session.commit()

    buyer_user = User(
        email=f'{_unique_name("noglobal")}@example.com',
        username=_unique_name("noglobal"),
        password_hash="test_hash",
        is_verified=True,
        organization_id=buyer_org.id,
    )
    db.session.add(buyer_user)
    db.session.commit()

    seller_item = InventoryItem(
        name="Secret Blend",
        unit="oz",
        type="ingredient",
        quantity=5.0,
        organization_id=seller_org.id,
        global_item_id=None,
    )
    db.session.add(seller_item)
    db.session.commit()

    with current_app.test_request_context():
        login_user(seller_user)
        ok, recipe_or_err = create_recipe(
            name=_unique_name("No Global Recipe"),
            instructions="Just mix.",
            yield_amount=5,
            yield_unit="oz",
            ingredients=[{"item_id": seller_item.id, "quantity": 5, "unit": "oz"}],
            allowed_containers=[],
            label_prefix="NGL",
            category_id=category.id,
            sharing_scope="public",
            is_public=True,
            status="published",
        )
        assert ok, recipe_or_err
        recipe: Recipe = recipe_or_err

        login_user(buyer_user)
        dup_ok, payload_or_err = duplicate_recipe(
            recipe.id,
            allow_cross_org=True,
            target_org_id=buyer_org.id,
        )
        assert dup_ok, payload_or_err
        ingredient_payload = payload_or_err["ingredients"][0]

        buyer_item = InventoryItem.query.filter_by(
            organization_id=buyer_org.id,
            name="Secret Blend",
        ).first()
        assert buyer_item is not None
        assert ingredient_payload["item_id"] == buyer_item.id


@pytest.mark.usefixtures("app_context")
def test_duplicate_recipe_matches_plural_names_without_global_link():
    category = _create_category("PluralMatch")

    seller_org = Organization.query.first()
    seller_user = User.query.filter_by(organization_id=seller_org.id).first()

    tier = seller_org.subscription_tier
    buyer_org = Organization(name=_unique_name("Buyer Plural"), subscription_tier=tier)
    db.session.add(buyer_org)
    db.session.commit()

    buyer_user = User(
        email=f'{_unique_name("plural")}@example.com',
        username=_unique_name("plural"),
        password_hash="test_hash",
        is_verified=True,
        organization_id=buyer_org.id,
    )
    db.session.add(buyer_user)
    db.session.commit()

    buyer_inventory = InventoryItem(
        name="Apples",
        unit="oz",
        type="ingredient",
        quantity=3.0,
        organization_id=buyer_org.id,
    )
    db.session.add(buyer_inventory)
    db.session.commit()

    seller_item = InventoryItem(
        name="Apple",
        unit="oz",
        type="ingredient",
        quantity=5.0,
        organization_id=seller_org.id,
    )
    db.session.add(seller_item)
    db.session.commit()

    with current_app.test_request_context():
        login_user(seller_user)
        ok, recipe_or_err = create_recipe(
            name=_unique_name("Plural Apples"),
            instructions="Mix apples.",
            yield_amount=5,
            yield_unit="oz",
            ingredients=[{"item_id": seller_item.id, "quantity": 5, "unit": "oz"}],
            allowed_containers=[],
            label_prefix="APL",
            category_id=category.id,
            sharing_scope="public",
            is_public=True,
            status="published",
        )
        assert ok, recipe_or_err
        recipe: Recipe = recipe_or_err

        login_user(buyer_user)
        dup_ok, payload_or_err = duplicate_recipe(
            recipe.id,
            allow_cross_org=True,
            target_org_id=buyer_org.id,
        )
        assert dup_ok, payload_or_err
        ingredient_payload = payload_or_err["ingredients"][0]
        assert ingredient_payload["item_id"] == buyer_inventory.id


@pytest.mark.usefixtures("app_context")
def test_variation_generation_derives_prefix_and_scope():
    category = _create_category("Variation")
    ingredient = _create_ingredient()

    ok, parent = create_recipe(
        name=_unique_name("Parent Base"),
        instructions="Base instructions",
        yield_amount=5,
        yield_unit="oz",
        ingredients=[{"item_id": ingredient.id, "quantity": 5, "unit": "oz"}],
        allowed_containers=[],
        label_prefix="BASE",
        category_id=category.id,
        sharing_scope="public",
        is_public=True,
        status="published",
    )
    assert ok, f"Failed to create parent recipe: {parent}"

    var_ok, variation = create_recipe(
        name=_unique_name("Parent Variation"),
        instructions="Adjusted instructions",
        yield_amount=5,
        yield_unit="oz",
        ingredients=[{"item_id": ingredient.id, "quantity": 5, "unit": "oz"}],
        allowed_containers=[],
        label_prefix="",  # force auto-derive to follow parent prefix
        category_id=category.id,
        parent_recipe_id=parent.id,
        sharing_scope="public",
        is_public=True,
        status="published",
    )
    assert var_ok, f"Failed to create variation: {variation}"
    assert variation.parent_recipe_id == parent.id
    assert variation.label_prefix.startswith("BASEV")
    assert variation.sharing_scope == "public"
    assert variation.root_recipe_id == parent.root_recipe_id == parent.id


@pytest.mark.usefixtures("app_context")
def test_update_recipe_toggles_public_private_controls():
    category = _create_category("Toggle")
    ingredient = _create_ingredient()

    ok, recipe = create_recipe(
        name=_unique_name("Toggle Recipe"),
        instructions="Initial instructions",
        yield_amount=4,
        yield_unit="oz",
        ingredients=[{"item_id": ingredient.id, "quantity": 4, "unit": "oz"}],
        allowed_containers=[],
        label_prefix="TGL",
        category_id=category.id,
        sharing_scope="public",
        is_public=True,
        is_for_sale=True,
        sale_price="8.50",
        status="published",
        is_test=True,
    )
    assert ok, f"Failed to create recipe: {recipe}"

    update_ok, updated = update_recipe(
        recipe_id=recipe.id,
        sharing_scope="private",
        is_public=False,
        is_for_sale=False,
        sale_price=None,
        marketplace_status="draft",
        ingredients=[{"item_id": ingredient.id, "quantity": 4, "unit": "oz"}],
    )
    assert update_ok, f"Update failed: {updated}"

    refreshed = db.session.get(Recipe, recipe.id)
    assert refreshed.sharing_scope == "private"
    assert refreshed.is_public is False
    assert refreshed.is_for_sale is False
    assert refreshed.sale_price is None
    assert refreshed.marketplace_status == "draft"


@pytest.mark.usefixtures("app_context")
def test_promote_test_to_current_restores_master_name():
    category = _create_category("MasterPromotion")
    ingredient = _create_ingredient()
    master_name = _unique_name("Royal Whipped Tallow")

    create_ok, master = create_recipe(
        name=master_name,
        instructions="Base blend",
        yield_amount=6,
        yield_unit="oz",
        ingredients=[{"item_id": ingredient.id, "quantity": 6, "unit": "oz"}],
        allowed_containers=[],
        label_prefix="RWT",
        category_id=category.id,
        status="published",
    )
    assert create_ok, master

    test_ok, test_recipe = create_test_version(
        base=master,
        payload=_test_recipe_payload(
            ingredient_id=ingredient.id,
            category_id=category.id,
            instructions="Master test update",
        ),
        target_status="published",
    )
    assert test_ok, test_recipe
    assert "test" in (test_recipe.name or "").lower()

    promote_ok, promoted = promote_test_to_current(test_recipe.id)
    assert promote_ok, promoted
    assert promoted.test_sequence is None
    assert promoted.is_current is True
    assert promoted.name == master.recipe_group.name
    assert "test" not in promoted.name.lower()


@pytest.mark.usefixtures("app_context")
def test_update_recipe_allows_unchanged_name_with_historical_duplicate_versions():
    category = _create_category("EditNameCollision")
    ingredient = _create_ingredient()
    container = InventoryItem(
        name=_unique_name("Allowed Container"),
        unit="count",
        type="container",
        quantity=0.0,
        organization_id=ingredient.organization_id,
    )
    db.session.add(container)
    db.session.commit()
    master_name = _unique_name("Edit Collision Master")

    create_ok, master = create_recipe(
        name=master_name,
        instructions="Base instructions",
        yield_amount=6,
        yield_unit="oz",
        ingredients=[{"item_id": ingredient.id, "quantity": 6, "unit": "oz"}],
        allowed_containers=[],
        label_prefix="ECM",
        category_id=category.id,
        status="published",
    )
    assert create_ok, master

    test_ok, test_recipe = create_test_version(
        base=master,
        payload=_test_recipe_payload(
            ingredient_id=ingredient.id,
            category_id=category.id,
            instructions="Promotion prep edits",
        ),
        target_status="published",
    )
    assert test_ok, test_recipe

    promote_ok, promoted = promote_test_to_current(test_recipe.id)
    assert promote_ok, promoted
    assert promoted.name == master_name

    update_ok, updated = update_recipe(
        recipe_id=promoted.id,
        name=promoted.name,
        ingredients=[{"item_id": ingredient.id, "quantity": 6, "unit": "oz"}],
        allowed_containers=[container.id],
        instructions="Edited instructions after promotion",
        allow_published_edit=True,
    )
    assert update_ok, updated

    refreshed = db.session.get(Recipe, promoted.id)
    assert refreshed is not None
    assert refreshed.name == master_name
    assert refreshed.allowed_containers == [container.id]
    assert "Edited instructions after promotion" in (refreshed.instructions or "")


@pytest.mark.usefixtures("app_context")
def test_batch_counts_are_lineage_scoped_per_version_and_test():
    category = _create_category("LineageBatchCounts")
    ingredient = _create_ingredient()
    master_name = _unique_name("Batch Scope Master")

    create_ok, master = create_recipe(
        name=master_name,
        instructions="Base instructions",
        yield_amount=6,
        yield_unit="oz",
        ingredients=[{"item_id": ingredient.id, "quantity": 6, "unit": "oz"}],
        allowed_containers=[],
        label_prefix="BSC",
        category_id=category.id,
        status="published",
    )
    assert create_ok, master

    test_ok, test_recipe = create_test_version(
        base=master,
        payload=_test_recipe_payload(
            ingredient_id=ingredient.id,
            category_id=category.id,
            instructions="Master test",
        ),
        target_status="published",
    )
    assert test_ok, test_recipe

    master_lineage = generate_lineage_id(master)
    test_lineage = generate_lineage_id(test_recipe)
    assert master_lineage != test_lineage

    # Master batch (explicit target version + lineage).
    master_batch = Batch(
        recipe_id=master.id,
        target_version_id=master.id,
        lineage_id=master_lineage,
        label_code=_unique_name("MASTER-BATCH"),
        batch_type="ingredient",
        organization_id=master.organization_id,
        status="completed",
    )

    # Test batch emulating legacy rows that reused master recipe_id while still
    # carrying the test lineage/target version snapshot.
    test_batch = Batch(
        recipe_id=master.id,
        target_version_id=test_recipe.id,
        lineage_id=test_lineage,
        label_code=_unique_name("TEST-BATCH"),
        batch_type="ingredient",
        organization_id=master.organization_id,
        status="completed",
    )
    db.session.add_all([master_batch, test_batch])
    db.session.commit()

    assert (
        count_batches_for_recipe_lineage(master, organization_id=master.organization_id)
        == 1
    )
    assert (
        count_batches_for_recipe_lineage(
            test_recipe, organization_id=test_recipe.organization_id
        )
        == 1
    )


@pytest.mark.usefixtures("app_context")
def test_promoting_test_to_current_preserves_batch_history_links():
    category = _create_category("PromotionBatchHistory")
    ingredient = _create_ingredient()
    master_name = _unique_name("Promotion History Master")

    create_ok, master = create_recipe(
        name=master_name,
        instructions="Base instructions",
        yield_amount=6,
        yield_unit="oz",
        ingredients=[{"item_id": ingredient.id, "quantity": 6, "unit": "oz"}],
        allowed_containers=[],
        label_prefix="PHM",
        category_id=category.id,
        status="published",
    )
    assert create_ok, master

    test_ok, test_recipe = create_test_version(
        base=master,
        payload=_test_recipe_payload(
            ingredient_id=ingredient.id,
            category_id=category.id,
            instructions="Promotable test instructions",
        ),
        target_status="published",
    )
    assert test_ok, test_recipe
    assert test_recipe.test_sequence == 1

    original_test_lineage = generate_lineage_id(test_recipe)

    # Persist a batch against the test before promotion.
    pre_promotion_batch = Batch(
        recipe_id=test_recipe.id,
        target_version_id=test_recipe.id,
        lineage_id=original_test_lineage,
        label_code=_unique_name("PROMO-TEST-BATCH"),
        batch_type="ingredient",
        organization_id=test_recipe.organization_id,
        status="completed",
    )
    db.session.add(pre_promotion_batch)
    db.session.commit()

    # Sanity check before promotion.
    assert (
        count_batches_for_recipe_lineage(
            test_recipe, organization_id=test_recipe.organization_id
        )
        == 1
    )

    promote_ok, promoted = promote_test_to_current(test_recipe.id)
    assert promote_ok, promoted
    assert promoted.id == test_recipe.id
    assert promoted.test_sequence is None

    # History row remains attached to the same promoted recipe row.
    refreshed_batch = db.session.get(Batch, pre_promotion_batch.id)
    assert refreshed_batch is not None
    assert refreshed_batch.target_version_id == promoted.id
    assert refreshed_batch.lineage_id == original_test_lineage

    # Count remains intact after promotion.
    assert (
        count_batches_for_recipe_lineage(promoted, organization_id=promoted.organization_id)
        == 1
    )


def test_recipe_list_keeps_group_variations_after_master_test_promotion(app, client):
    with app.app_context():
        user_id = User.query.first().id
        category = _create_category("ListGrouping")
        ingredient = _create_ingredient()

        create_ok, master = create_recipe(
            name=_unique_name("Grouped Master"),
            instructions="Master instructions",
            yield_amount=6,
            yield_unit="oz",
            ingredients=[{"item_id": ingredient.id, "quantity": 6, "unit": "oz"}],
            allowed_containers=[],
            label_prefix="GRP",
            category_id=category.id,
            status="published",
        )
        assert create_ok, master

        variation_ok, variation = create_recipe(
            name=_unique_name("Grouped Variation"),
            instructions="Variation instructions",
            yield_amount=6,
            yield_unit="oz",
            ingredients=[{"item_id": ingredient.id, "quantity": 6, "unit": "oz"}],
            allowed_containers=[],
            label_prefix="",
            category_id=category.id,
            parent_recipe_id=master.id,
            status="published",
        )
        assert variation_ok, variation
        variation_label = variation.variation_name or variation.name

        test_ok, master_test = create_test_version(
            base=master,
            payload=_test_recipe_payload(
                ingredient_id=ingredient.id,
                category_id=category.id,
                instructions="Master revision that should retain group variations",
            ),
            target_status="published",
        )
        assert test_ok, master_test

        promote_ok, promoted_master = promote_test_to_current(master_test.id)
        assert promote_ok, promoted_master
        promoted_master_id = promoted_master.id

    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True

    response = client.get("/recipes/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert variation_label in body
    assert f"/recipes/{promoted_master_id}/view" in body


@pytest.mark.usefixtures("app_context")
def test_master_test_sequences_reset_per_master_version():
    category = _create_category("MasterSequence")
    ingredient = _create_ingredient()
    master_name = _unique_name("Sequence Master")

    create_ok, master = create_recipe(
        name=master_name,
        instructions="Base mix",
        yield_amount=6,
        yield_unit="oz",
        ingredients=[{"item_id": ingredient.id, "quantity": 6, "unit": "oz"}],
        allowed_containers=[],
        label_prefix="SEQ",
        category_id=category.id,
        status="published",
    )
    assert create_ok, master

    first_test_ok, first_test = create_test_version(
        base=master,
        payload=_test_recipe_payload(
            ingredient_id=ingredient.id,
            category_id=category.id,
            instructions="First test",
        ),
        target_status="published",
    )
    assert first_test_ok, first_test
    assert first_test.test_sequence == 1

    promote_ok, promoted_master = promote_test_to_current(first_test.id)
    assert promote_ok, promoted_master
    assert promoted_master.version_number == 2

    second_test_ok, second_test = create_test_version(
        base=promoted_master,
        payload=_test_recipe_payload(
            ingredient_id=ingredient.id,
            category_id=category.id,
            instructions="Second version first test",
        ),
        target_status="published",
    )
    assert second_test_ok, second_test
    assert second_test.version_number == promoted_master.version_number
    assert second_test.test_sequence == 1
    assert second_test.name.endswith(" - Test 1")


@pytest.mark.usefixtures("app_context")
def test_create_test_from_test_is_blocked():
    category = _create_category("NestedTests")
    ingredient = _create_ingredient()
    master_name = _unique_name("Nested Master")

    create_ok, master = create_recipe(
        name=master_name,
        instructions="Base mix",
        yield_amount=6,
        yield_unit="oz",
        ingredients=[{"item_id": ingredient.id, "quantity": 6, "unit": "oz"}],
        allowed_containers=[],
        label_prefix="NST",
        category_id=category.id,
        status="published",
    )
    assert create_ok, master

    first_test_ok, first_test = create_test_version(
        base=master,
        payload=_test_recipe_payload(
            ingredient_id=ingredient.id,
            category_id=category.id,
            instructions="First nested test",
        ),
        target_status="published",
    )
    assert first_test_ok, first_test
    assert first_test.test_sequence == 1

    second_test_ok, second_test = create_test_version(
        base=first_test,
        payload=_test_recipe_payload(
            ingredient_id=ingredient.id,
            category_id=category.id,
            instructions="Second nested test",
        ),
        target_status="published",
    )
    assert not second_test_ok
    assert second_test == "Tests cannot be created from test recipes."


@pytest.mark.usefixtures("app_context")
def test_build_version_branches_groups_tests_under_master_version():
    from app.blueprints.recipes.lineage_utils import build_version_branches

    category = _create_category("BranchGrouping")
    ingredient = _create_ingredient()
    master_name = _unique_name("Branch Master")

    create_ok, master = create_recipe(
        name=master_name,
        instructions="Base mix",
        yield_amount=6,
        yield_unit="oz",
        ingredients=[{"item_id": ingredient.id, "quantity": 6, "unit": "oz"}],
        allowed_containers=[],
        label_prefix="BRN",
        category_id=category.id,
        status="published",
    )
    assert create_ok, master

    first_test_ok, first_test = create_test_version(
        base=master,
        payload=_test_recipe_payload(
            ingredient_id=ingredient.id,
            category_id=category.id,
            instructions="First grouped test",
        ),
        target_status="published",
    )
    assert first_test_ok, first_test

    second_test_ok, second_test = create_test_version(
        base=master,
        payload=_test_recipe_payload(
            ingredient_id=ingredient.id,
            category_id=category.id,
            instructions="Second grouped test",
        ),
        target_status="published",
    )
    assert second_test_ok, second_test

    group_versions = Recipe.query.filter(
        Recipe.recipe_group_id == master.recipe_group_id
    ).all()
    master_branches, _ = build_version_branches(group_versions)
    master_branch = next(
        branch for branch in master_branches if branch["version"].id == master.id
    )
    assert [test.test_sequence for test in master_branch["tests"]] == [1, 2]


@pytest.mark.usefixtures("app_context")
def test_variation_tests_are_scoped_per_variation_version():
    from app.blueprints.recipes.lineage_utils import build_version_branches

    category = _create_category("VariationVersionScope")
    ingredient = _create_ingredient()
    master_name = _unique_name("Variation Scope Master")

    create_ok, master = create_recipe(
        name=master_name,
        instructions="Base mix",
        yield_amount=6,
        yield_unit="oz",
        ingredients=[{"item_id": ingredient.id, "quantity": 6, "unit": "oz"}],
        allowed_containers=[],
        label_prefix="VVS",
        category_id=category.id,
        status="published",
    )
    assert create_ok, master

    variation_v1_ok, variation_v1 = create_recipe(
        name=f"{master_name} Lavender",
        instructions="Lavender v1",
        yield_amount=6,
        yield_unit="oz",
        ingredients=[{"item_id": ingredient.id, "quantity": 6, "unit": "oz"}],
        allowed_containers=[],
        label_prefix="",
        category_id=category.id,
        parent_recipe_id=master.id,
        status="published",
    )
    assert variation_v1_ok, variation_v1
    variation_name = variation_v1.variation_name

    variation_v2_ok, variation_v2 = create_recipe(
        name=variation_v1.name,
        instructions="Lavender v2",
        yield_amount=6,
        yield_unit="oz",
        ingredients=[{"item_id": ingredient.id, "quantity": 6, "unit": "oz"}],
        allowed_containers=[],
        label_prefix="",
        category_id=category.id,
        parent_recipe_id=variation_v1.id,
        variation_name=variation_name,
        status="published",
    )
    assert variation_v2_ok, variation_v2

    v1_test_1_ok, v1_test_1 = create_test_version(
        base=variation_v1,
        payload=_test_recipe_payload(
            ingredient_id=ingredient.id,
            category_id=category.id,
            instructions="Variation v1 test one",
        ),
        target_status="published",
    )
    assert v1_test_1_ok, v1_test_1
    v2_test_1_ok, v2_test_1 = create_test_version(
        base=variation_v2,
        payload=_test_recipe_payload(
            ingredient_id=ingredient.id,
            category_id=category.id,
            instructions="Variation v2 test one",
        ),
        target_status="published",
    )
    assert v2_test_1_ok, v2_test_1
    v1_test_2_ok, v1_test_2 = create_test_version(
        base=variation_v1,
        payload=_test_recipe_payload(
            ingredient_id=ingredient.id,
            category_id=category.id,
            instructions="Variation v1 test two",
        ),
        target_status="published",
    )
    assert v1_test_2_ok, v1_test_2
    v2_test_2_ok, v2_test_2 = create_test_version(
        base=variation_v2,
        payload=_test_recipe_payload(
            ingredient_id=ingredient.id,
            category_id=category.id,
            instructions="Variation v2 test two",
        ),
        target_status="published",
    )
    assert v2_test_2_ok, v2_test_2

    assert [v1_test_1.test_sequence, v1_test_2.test_sequence] == [1, 2]
    assert [v2_test_1.test_sequence, v2_test_2.test_sequence] == [1, 2]
    assert v1_test_1.version_number == variation_v1.version_number
    assert v2_test_1.version_number == variation_v2.version_number

    group_versions = Recipe.query.filter(
        Recipe.recipe_group_id == master.recipe_group_id
    ).all()
    _, variation_branches = build_version_branches(group_versions)
    lavender_branch = next(
        branch
        for branch in variation_branches
        if branch["name"].strip().lower() == (variation_name or "").strip().lower()
    )
    version_tests = {
        entry["version"].version_number: [test.test_sequence for test in entry["tests"]]
        for entry in lavender_branch["versions"]
    }
    assert version_tests[variation_v1.version_number] == [1, 2]
    assert version_tests[variation_v2.version_number] == [1, 2]


@pytest.mark.usefixtures("app_context")
def test_repair_test_sequences_fixes_interleaved_variation_tests():
    from app.services.recipe_service._maintenance import repair_test_sequences

    category = _create_category("VariationRepair")
    ingredient = _create_ingredient()
    master_name = _unique_name("Repair Scope Master")

    create_ok, master = create_recipe(
        name=master_name,
        instructions="Base mix",
        yield_amount=6,
        yield_unit="oz",
        ingredients=[{"item_id": ingredient.id, "quantity": 6, "unit": "oz"}],
        allowed_containers=[],
        label_prefix="RPR",
        category_id=category.id,
        status="published",
    )
    assert create_ok, master

    variation_v1_ok, variation_v1 = create_recipe(
        name=f"{master_name} Lavender",
        instructions="Lavender v1",
        yield_amount=6,
        yield_unit="oz",
        ingredients=[{"item_id": ingredient.id, "quantity": 6, "unit": "oz"}],
        allowed_containers=[],
        label_prefix="",
        category_id=category.id,
        parent_recipe_id=master.id,
        status="published",
    )
    assert variation_v1_ok, variation_v1
    variation_name = variation_v1.variation_name

    variation_v2_ok, variation_v2 = create_recipe(
        name=variation_v1.name,
        instructions="Lavender v2",
        yield_amount=6,
        yield_unit="oz",
        ingredients=[{"item_id": ingredient.id, "quantity": 6, "unit": "oz"}],
        allowed_containers=[],
        label_prefix="",
        category_id=category.id,
        parent_recipe_id=variation_v1.id,
        variation_name=variation_name,
        status="published",
    )
    assert variation_v2_ok, variation_v2

    v1_t1_ok, v1_t1 = create_test_version(
        base=variation_v1,
        payload=_test_recipe_payload(
            ingredient_id=ingredient.id,
            category_id=category.id,
            instructions="Variation v1 test one",
        ),
        target_status="published",
    )
    assert v1_t1_ok, v1_t1
    v2_t1_ok, v2_t1 = create_test_version(
        base=variation_v2,
        payload=_test_recipe_payload(
            ingredient_id=ingredient.id,
            category_id=category.id,
            instructions="Variation v2 test one",
        ),
        target_status="published",
    )
    assert v2_t1_ok, v2_t1
    v1_t2_ok, v1_t2 = create_test_version(
        base=variation_v1,
        payload=_test_recipe_payload(
            ingredient_id=ingredient.id,
            category_id=category.id,
            instructions="Variation v1 test two",
        ),
        target_status="published",
    )
    assert v1_t2_ok, v1_t2
    v2_t2_ok, v2_t2 = create_test_version(
        base=variation_v2,
        payload=_test_recipe_payload(
            ingredient_id=ingredient.id,
            category_id=category.id,
            instructions="Variation v2 test two",
        ),
        target_status="published",
    )
    assert v2_t2_ok, v2_t2

    # Simulate legacy interleaving data (v1: 1,3 and v2: 2,4).
    v1_t2.test_sequence = 3
    v1_t2.name = f"{variation_name} - Test 3"
    v2_t1.test_sequence = 2
    v2_t1.name = f"{variation_name} - Test 2"
    v2_t2.test_sequence = 4
    v2_t2.name = f"{variation_name} - Test 4"
    db.session.commit()

    dry_run = repair_test_sequences(
        recipe_group_id=master.recipe_group_id,
        apply_changes=False,
    )
    assert dry_run["sequence_updates"] >= 3

    # Dry-run must not persist changes.
    db.session.expire_all()
    stale_v1_t2 = db.session.get(Recipe, v1_t2.id)
    stale_v2_t1 = db.session.get(Recipe, v2_t1.id)
    assert stale_v1_t2.test_sequence == 3
    assert stale_v2_t1.test_sequence == 2

    applied = repair_test_sequences(
        recipe_group_id=master.recipe_group_id,
        apply_changes=True,
    )
    assert applied["total_changes"] >= 3

    db.session.expire_all()
    repaired_group_versions = Recipe.query.filter(
        Recipe.recipe_group_id == master.recipe_group_id
    ).all()
    version_tests: dict[int, list[int]] = {}
    for row in repaired_group_versions:
        if row.test_sequence is None or row.is_master:
            continue
        version_tests.setdefault(int(row.version_number), []).append(int(row.test_sequence))
    for seqs in version_tests.values():
        assert sorted(seqs) == [1, 2]


def test_view_recipe_shows_lineage_display_names(app, client):
    with app.app_context():
        user_id = User.query.first().id
        category = _create_category("LineageDisplay")
        ingredient = _create_ingredient()
        master_name = _unique_name("Display Master")

        create_ok, master = create_recipe(
            name=master_name,
            instructions="Display base",
            yield_amount=6,
            yield_unit="oz",
            ingredients=[{"item_id": ingredient.id, "quantity": 6, "unit": "oz"}],
            allowed_containers=[],
            label_prefix="DSP",
            category_id=category.id,
            status="published",
        )
        assert create_ok, master

        variation_ok, variation = create_recipe(
            name=f"{master_name} Lavender",
            instructions="Display variation",
            yield_amount=6,
            yield_unit="oz",
            ingredients=[{"item_id": ingredient.id, "quantity": 6, "unit": "oz"}],
            allowed_containers=[],
            label_prefix="",
            category_id=category.id,
            parent_recipe_id=master.id,
            status="published",
        )
        assert variation_ok, variation

        test_ok, test_recipe = create_test_version(
            base=master,
            payload=_test_recipe_payload(
                ingredient_id=ingredient.id,
                category_id=category.id,
                instructions="Display test",
            ),
            target_status="published",
        )
        assert test_ok, test_recipe

        master_id = master.id
        variation_id = variation.id
        variation_name = variation.variation_name
        test_id = test_recipe.id
        test_sequence = test_recipe.test_sequence
        group_name = master.recipe_group.name

    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True

    variation_response = client.get(f"/recipes/{variation_id}/view")
    assert variation_response.status_code == 200
    variation_body = variation_response.get_data(as_text=True)
    assert f"{group_name} - {variation_name}" in variation_body
    assert f"/recipes/{variation_id}/test" in variation_body

    master_response = client.get(f"/recipes/{master_id}/view")
    assert master_response.status_code == 200
    master_body = master_response.get_data(as_text=True)
    assert f"/recipes/{master_id}/test" in master_body

    test_response = client.get(f"/recipes/{test_id}/view")
    assert test_response.status_code == 200
    test_body = test_response.get_data(as_text=True)
    expected_test_name = f"{group_name} - Test {test_sequence}"
    assert expected_test_name in test_body
    assert f"{expected_test_name} - Test {test_sequence}" not in test_body
    assert f"/recipes/{test_id}/test" not in test_body


@pytest.mark.usefixtures("app")
def test_view_recipe_cost_card_shows_total_when_item_cost_exists(app, client):
    with app.app_context():
        user = User.query.first()
        assert user is not None
        category = _create_category("CostCard")
        ingredient = _create_ingredient()
        ingredient.cost_per_unit = 0.01
        db.session.commit()

        create_ok, recipe_or_err = create_recipe(
            name=_unique_name("Costed Recipe"),
            instructions="Costed recipe instructions",
            yield_amount=6,
            yield_unit="oz",
            ingredients=[{"item_id": ingredient.id, "quantity": 6, "unit": "oz"}],
            allowed_containers=[],
            label_prefix="CST",
            category_id=category.id,
            status="published",
        )
        assert create_ok, recipe_or_err
        recipe_id = recipe_or_err.id
        user_id = user.id

    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True

    response = client.get(f"/recipes/{recipe_id}/view")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Total Recipe Cost:" in body
    assert '<h5 class="text-success mb-0">$0.06</h5>' in body
    assert (
        "Total Recipe Cost:</strong>\n          <span class=\"text-muted\">Not available</span>"
        not in body
    )


def test_create_test_route_allows_all_published_variations_and_blocks_tests(app, client):
    with app.app_context():
        user_id = User.query.first().id
        category = _create_category("TestRouteGuard")
        ingredient = _create_ingredient()
        master_name = _unique_name("Guard Master")

        create_ok, master = create_recipe(
            name=master_name,
            instructions="Guard base",
            yield_amount=6,
            yield_unit="oz",
            ingredients=[{"item_id": ingredient.id, "quantity": 6, "unit": "oz"}],
            allowed_containers=[],
            label_prefix="GRD",
            category_id=category.id,
            status="published",
        )
        assert create_ok, master

        variation_ok, variation = create_recipe(
            name=f"{master_name} Citrus",
            instructions="Guard variation",
            yield_amount=6,
            yield_unit="oz",
            ingredients=[{"item_id": ingredient.id, "quantity": 6, "unit": "oz"}],
            allowed_containers=[],
            label_prefix="",
            category_id=category.id,
            parent_recipe_id=master.id,
            status="published",
        )
        assert variation_ok, variation

        variation_test_ok, variation_test = create_test_version(
            base=variation,
            payload=_test_recipe_payload(
                ingredient_id=ingredient.id,
                category_id=category.id,
                instructions="Guard variation test",
            ),
            target_status="published",
        )
        assert variation_test_ok, variation_test
        promote_variation_ok, promoted_variation = promote_test_to_current(variation_test.id)
        assert promote_variation_ok, promoted_variation

        test_ok, test_recipe = create_test_version(
            base=master,
            payload=_test_recipe_payload(
                ingredient_id=ingredient.id,
                category_id=category.id,
                instructions="Guard master test",
            ),
            target_status="published",
        )
        assert test_ok, test_recipe
        current_variation_id = promoted_variation.id
        older_variation_id = variation.id
        test_id = test_recipe.id

    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True

    current_variation_resp = client.get(f"/recipes/{current_variation_id}/test")
    assert current_variation_resp.status_code == 200
    current_variation_body = current_variation_resp.get_data(as_text=True)
    assert "Tests cannot be created from test recipes." not in current_variation_body
    assert f"/recipes/{current_variation_id}/test" in current_variation_body

    older_variation_resp = client.get(f"/recipes/{older_variation_id}/test")
    assert older_variation_resp.status_code == 200
    older_variation_body = older_variation_resp.get_data(as_text=True)
    assert "Tests cannot be created from test recipes." not in older_variation_body
    assert f"/recipes/{older_variation_id}/test" in older_variation_body

    test_resp = client.get(
        f"/recipes/{test_id}/test",
        follow_redirects=True,
    )
    assert test_resp.status_code == 200
    test_body = test_resp.get_data(as_text=True)
    assert "Tests cannot be created from test recipes." in test_body
