"""Tests for recipe service workflows.

Synopsis:
Validates recipe CRUD and marketplace guardrails for versions.

Glossary:
- Marketplace: Public listing configuration.
- Versioning: Master/variation/test behavior.
"""

import pytest
from decimal import Decimal
from uuid import uuid4

from flask import current_app
from flask_login import login_user

from app.extensions import db
from app.models import Recipe
from app.models.inventory import InventoryItem
from app.models.models import Organization, User
from app.models.product_category import ProductCategory
from app.models.global_item import GlobalItem
from app.services.recipe_service import (
    create_recipe,
    create_test_version,
    duplicate_recipe,
    promote_test_to_current,
    update_recipe,
)


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
        unit='oz',
        type='ingredient',
        quantity=10.0,
        organization_id=org.id if org else None,
    )
    db.session.add(ingredient)
    db.session.commit()
    return ingredient


def _test_recipe_payload(*, ingredient_id: int, category_id: int, instructions: str) -> dict:
    return {
        'instructions': instructions,
        'yield_amount': 6,
        'yield_unit': 'oz',
        'ingredients': [{'item_id': ingredient_id, 'quantity': 6, 'unit': 'oz'}],
        'consumables': [],
        'allowed_containers': [],
        'label_prefix': '',
        'category_id': category_id,
    }


@pytest.mark.usefixtures('app_context')
def test_create_recipe_public_marketplace_listing():
    category = _create_category("Marketplace")
    ingredient = _create_ingredient()

    ok, recipe_or_err = create_recipe(
        name=_unique_name("Public Soap"),
        instructions='Blend and pour',
        yield_amount=12,
        yield_unit='oz',
        ingredients=[{'item_id': ingredient.id, 'quantity': 12, 'unit': 'oz'}],
        allowed_containers=[],
        label_prefix='PUB',
        category_id=category.id,
        sharing_scope='public',
        is_public=True,
        is_for_sale=True,
        sale_price='19.99',
        marketplace_notes='Premium listing',
        public_description='A showcase recipe for the marketplace',
        status='published',
    )
    assert ok, f"Expected creation success, got: {recipe_or_err}"
    recipe: Recipe = recipe_or_err

    assert recipe.sharing_scope == 'public'
    assert recipe.is_public is True
    assert recipe.is_for_sale is True
    assert recipe.sale_price == Decimal('19.99')
    assert recipe.marketplace_status == 'listed'
    assert recipe.marketplace_notes == 'Premium listing'
    assert recipe.public_description.startswith('A showcase')


@pytest.mark.usefixtures('app_context')
def test_duplicate_recipe_returns_private_template():
    category = _create_category("Clone")
    ingredient = _create_ingredient()

    ok, recipe = create_recipe(
        name=_unique_name("Clone Ready"),
        instructions='Mix ingredients',
        yield_amount=8,
        yield_unit='oz',
        ingredients=[{'item_id': ingredient.id, 'quantity': 8, 'unit': 'oz'}],
        allowed_containers=[],
        label_prefix='CLN',
        category_id=category.id,
        sharing_scope='public',
        is_public=True,
        is_for_sale=False,
        status='published',
    )
    assert ok, f"Failed to create base recipe: {recipe}"

    user = User.query.first()
    with current_app.test_request_context():
        login_user(user)
        dup_ok, payload_or_err = duplicate_recipe(recipe.id)
    assert dup_ok, f"Duplicate failed: {payload_or_err}"
    template = payload_or_err['template']

    assert template.sharing_scope == 'private'
    assert template.is_public is False
    assert template.is_for_sale is False
    assert template.sale_price is None
    assert template.cloned_from_id == recipe.id


@pytest.mark.usefixtures('app_context')
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
        password_hash='test_hash',
        is_verified=True,
        organization_id=buyer_org.id,
    )
    db.session.add(buyer_user)
    db.session.commit()

    # Shared global item plus org-specific inventory
    global_item = GlobalItem(name=_unique_name("Global Oil"), item_type='ingredient', default_unit='oz')
    db.session.add(global_item)
    db.session.commit()

    seller_item = InventoryItem(
        name="Seller Oil",
        unit='oz',
        type='ingredient',
        quantity=25.0,
        organization_id=seller_org.id,
        global_item_id=global_item.id,
    )
    buyer_item = InventoryItem(
        name="Buyer Oil",
        unit='oz',
        type='ingredient',
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
            instructions='Mix thoroughly.',
            yield_amount=10,
            yield_unit='oz',
            ingredients=[{'item_id': seller_item.id, 'quantity': 10, 'unit': 'oz'}],
            allowed_containers=[],
            label_prefix='IMP',
            category_id=category.id,
            sharing_scope='public',
            is_public=True,
            status='published',
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
        ingredient_payload = payload_or_err['ingredients'][0]
        assert ingredient_payload['global_item_id'] == global_item.id
        assert ingredient_payload['item_id'] == buyer_item.id


@pytest.mark.usefixtures('app_context')
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
        password_hash='test_hash',
        is_verified=True,
        organization_id=buyer_org.id,
    )
    db.session.add(buyer_user)
    db.session.commit()

    global_item = GlobalItem(name=_unique_name("New Oil"), item_type='ingredient', default_unit='oz')
    db.session.add(global_item)
    db.session.commit()

    seller_item = InventoryItem(
        name="Seller Only Oil",
        unit='oz',
        type='ingredient',
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
            instructions='Blend oils.',
            yield_amount=6,
            yield_unit='oz',
            ingredients=[{'item_id': seller_item.id, 'quantity': 6, 'unit': 'oz'}],
            allowed_containers=[],
            label_prefix='IMP2',
            category_id=category.id,
            sharing_scope='public',
            is_public=True,
            status='published',
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
        ingredient_payload = payload_or_err['ingredients'][0]

        buyer_created = InventoryItem.query.filter_by(
            organization_id=buyer_org.id,
            global_item_id=global_item.id,
        ).first()
        assert buyer_created is not None
        assert ingredient_payload['item_id'] == buyer_created.id


@pytest.mark.usefixtures('app_context')
def test_duplicate_recipe_creates_inventory_without_global_link():
    category = _create_category("NoGlobal")

    seller_org = Organization.query.first()
    seller_user = User.query.filter_by(organization_id=seller_org.id).first()

    tier = seller_org.subscription_tier
    buyer_org = Organization(name=_unique_name("Buyer NoGlobal"), subscription_tier=tier)
    db.session.add(buyer_org)
    db.session.commit()

    buyer_user = User(
        email=f'{_unique_name("noglobal")}@example.com',
        username=_unique_name("noglobal"),
        password_hash='test_hash',
        is_verified=True,
        organization_id=buyer_org.id,
    )
    db.session.add(buyer_user)
    db.session.commit()

    seller_item = InventoryItem(
        name="Secret Blend",
        unit='oz',
        type='ingredient',
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
            instructions='Just mix.',
            yield_amount=5,
            yield_unit='oz',
            ingredients=[{'item_id': seller_item.id, 'quantity': 5, 'unit': 'oz'}],
            allowed_containers=[],
            label_prefix='NGL',
            category_id=category.id,
            sharing_scope='public',
            is_public=True,
            status='published',
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
        ingredient_payload = payload_or_err['ingredients'][0]

        buyer_item = InventoryItem.query.filter_by(
            organization_id=buyer_org.id,
            name="Secret Blend",
        ).first()
        assert buyer_item is not None
        assert ingredient_payload['item_id'] == buyer_item.id


@pytest.mark.usefixtures('app_context')
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
        password_hash='test_hash',
        is_verified=True,
        organization_id=buyer_org.id,
    )
    db.session.add(buyer_user)
    db.session.commit()

    buyer_inventory = InventoryItem(
        name="Apples",
        unit='oz',
        type='ingredient',
        quantity=3.0,
        organization_id=buyer_org.id,
    )
    db.session.add(buyer_inventory)
    db.session.commit()

    seller_item = InventoryItem(
        name="Apple",
        unit='oz',
        type='ingredient',
        quantity=5.0,
        organization_id=seller_org.id,
    )
    db.session.add(seller_item)
    db.session.commit()

    with current_app.test_request_context():
        login_user(seller_user)
        ok, recipe_or_err = create_recipe(
            name=_unique_name("Plural Apples"),
            instructions='Mix apples.',
            yield_amount=5,
            yield_unit='oz',
            ingredients=[{'item_id': seller_item.id, 'quantity': 5, 'unit': 'oz'}],
            allowed_containers=[],
            label_prefix='APL',
            category_id=category.id,
            sharing_scope='public',
            is_public=True,
            status='published',
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
        ingredient_payload = payload_or_err['ingredients'][0]
        assert ingredient_payload['item_id'] == buyer_inventory.id


@pytest.mark.usefixtures('app_context')
def test_variation_generation_derives_prefix_and_scope():
    category = _create_category("Variation")
    ingredient = _create_ingredient()

    ok, parent = create_recipe(
        name=_unique_name("Parent Base"),
        instructions='Base instructions',
        yield_amount=5,
        yield_unit='oz',
        ingredients=[{'item_id': ingredient.id, 'quantity': 5, 'unit': 'oz'}],
        allowed_containers=[],
        label_prefix='BASE',
        category_id=category.id,
        sharing_scope='public',
        is_public=True,
        status='published',
    )
    assert ok, f"Failed to create parent recipe: {parent}"

    var_ok, variation = create_recipe(
        name=_unique_name("Parent Variation"),
        instructions='Adjusted instructions',
        yield_amount=5,
        yield_unit='oz',
        ingredients=[{'item_id': ingredient.id, 'quantity': 5, 'unit': 'oz'}],
        allowed_containers=[],
        label_prefix='',  # force auto-derive to follow parent prefix
        category_id=category.id,
        parent_recipe_id=parent.id,
        sharing_scope='public',
        is_public=True,
        status='published',
    )
    assert var_ok, f"Failed to create variation: {variation}"
    assert variation.parent_recipe_id == parent.id
    assert variation.label_prefix.startswith('BASEV')
    assert variation.sharing_scope == 'public'
    assert variation.root_recipe_id == parent.root_recipe_id == parent.id


@pytest.mark.usefixtures('app_context')
def test_update_recipe_toggles_public_private_controls():
    category = _create_category("Toggle")
    ingredient = _create_ingredient()

    ok, recipe = create_recipe(
        name=_unique_name("Toggle Recipe"),
        instructions='Initial instructions',
        yield_amount=4,
        yield_unit='oz',
        ingredients=[{'item_id': ingredient.id, 'quantity': 4, 'unit': 'oz'}],
        allowed_containers=[],
        label_prefix='TGL',
        category_id=category.id,
        sharing_scope='public',
        is_public=True,
        is_for_sale=True,
        sale_price='8.50',
        status='published',
        is_test=True,
    )
    assert ok, f"Failed to create recipe: {recipe}"

    update_ok, updated = update_recipe(
        recipe_id=recipe.id,
        sharing_scope='private',
        is_public=False,
        is_for_sale=False,
        sale_price=None,
        marketplace_status='draft',
        ingredients=[{'item_id': ingredient.id, 'quantity': 4, 'unit': 'oz'}],
    )
    assert update_ok, f"Update failed: {updated}"

    refreshed = db.session.get(Recipe, recipe.id)
    assert refreshed.sharing_scope == 'private'
    assert refreshed.is_public is False
    assert refreshed.is_for_sale is False
    assert refreshed.sale_price is None
    assert refreshed.marketplace_status == 'draft'


@pytest.mark.usefixtures('app_context')
def test_promote_test_to_current_restores_master_name():
    category = _create_category("MasterPromotion")
    ingredient = _create_ingredient()
    master_name = _unique_name("Royal Whipped Tallow")

    create_ok, master = create_recipe(
        name=master_name,
        instructions='Base blend',
        yield_amount=6,
        yield_unit='oz',
        ingredients=[{'item_id': ingredient.id, 'quantity': 6, 'unit': 'oz'}],
        allowed_containers=[],
        label_prefix='RWT',
        category_id=category.id,
        status='published',
    )
    assert create_ok, master

    test_ok, test_recipe = create_test_version(
        base=master,
        payload=_test_recipe_payload(
            ingredient_id=ingredient.id,
            category_id=category.id,
            instructions='Master test update',
        ),
        target_status='published',
    )
    assert test_ok, test_recipe
    assert "test" in (test_recipe.name or "").lower()

    promote_ok, promoted = promote_test_to_current(test_recipe.id)
    assert promote_ok, promoted
    assert promoted.test_sequence is None
    assert promoted.is_current is True
    assert promoted.name == master.recipe_group.name
    assert "test" not in promoted.name.lower()


def test_recipe_list_keeps_group_variations_after_master_test_promotion(app, client):
    with app.app_context():
        user_id = User.query.first().id
        category = _create_category("ListGrouping")
        ingredient = _create_ingredient()

        create_ok, master = create_recipe(
            name=_unique_name("Grouped Master"),
            instructions='Master instructions',
            yield_amount=6,
            yield_unit='oz',
            ingredients=[{'item_id': ingredient.id, 'quantity': 6, 'unit': 'oz'}],
            allowed_containers=[],
            label_prefix='GRP',
            category_id=category.id,
            status='published',
        )
        assert create_ok, master

        variation_ok, variation = create_recipe(
            name=_unique_name("Grouped Variation"),
            instructions='Variation instructions',
            yield_amount=6,
            yield_unit='oz',
            ingredients=[{'item_id': ingredient.id, 'quantity': 6, 'unit': 'oz'}],
            allowed_containers=[],
            label_prefix='',
            category_id=category.id,
            parent_recipe_id=master.id,
            status='published',
        )
        assert variation_ok, variation
        variation_label = variation.variation_name or variation.name

        test_ok, master_test = create_test_version(
            base=master,
            payload=_test_recipe_payload(
                ingredient_id=ingredient.id,
                category_id=category.id,
                instructions='Master revision that should retain group variations',
            ),
            target_status='published',
        )
        assert test_ok, master_test

        promote_ok, promoted_master = promote_test_to_current(master_test.id)
        assert promote_ok, promoted_master
        promoted_master_id = promoted_master.id

    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True

    response = client.get('/recipes/')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert variation_label in body
    assert f"/recipes/{promoted_master_id}/view" in body
