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
from app.services.recipe_service import (
    create_recipe,
    duplicate_recipe,
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
