import pytest
from uuid import uuid4

from flask_login import login_user, logout_user

from app.extensions import db
from app.models.models import Organization, User
from app.models.product_category import ProductCategory
from app.services.recipe_service._core import create_recipe


def _create_user(org_name: str = "Test Org"):
    org = Organization(name=f"{org_name}-{uuid4().hex[:6]}")
    db.session.add(org)
    db.session.flush()

    user = User(
        username=f"user_{uuid4().hex[:6]}",
        email=f"{uuid4().hex}@example.com",
        organization_id=org.id,
        user_type="customer",
        is_active=True,
    )
    db.session.add(user)
    db.session.commit()
    return user, org


def _get_category_id():
    category = ProductCategory.query.first()
    if not category:
        category = ProductCategory(name="Uncategorized")
        db.session.add(category)
        db.session.commit()
    return category.id


@pytest.mark.usefixtures("app_context")
def test_create_recipe_sets_authored_origin(app):
    user, _ = _create_user("Origin Authored Org")
    category_id = _get_category_id()

    with app.test_request_context():
        login_user(user)
        ok, recipe = create_recipe(
            name="Authored Origin",
            description="",
            instructions="",
            yield_amount=0,
            yield_unit="",
            ingredients=[],
            consumables=[],
            allowed_containers=[],
            category_id=category_id,
            status="draft",
        )
        logout_user()

    assert ok, f"Recipe creation failed: {recipe}"
    assert recipe.org_origin_recipe_id == recipe.id
    assert recipe.org_origin_type == "authored"
    assert recipe.org_origin_purchased is False
    assert recipe.is_sellable is True


@pytest.mark.usefixtures("app_context")
def test_clone_from_other_org_marks_purchased_origin(app):
    seller_user, seller_org = _create_user("Seller Org")
    buyer_user, _ = _create_user("Buyer Org")
    category_id = _get_category_id()

    with app.test_request_context():
        login_user(seller_user)
        ok, seller_recipe = create_recipe(
            name="Seller Recipe",
            description="",
            instructions="",
            yield_amount=0,
            yield_unit="",
            ingredients=[],
            consumables=[],
            allowed_containers=[],
            category_id=category_id,
            status="draft",
        )
        logout_user()
    assert ok, f"Seller recipe creation failed: {seller_recipe}"

    with app.test_request_context():
        login_user(buyer_user)
        ok, purchased_recipe = create_recipe(
            name="Purchased Copy",
            description="",
            instructions="",
            yield_amount=0,
            yield_unit="",
            ingredients=[],
            consumables=[],
            allowed_containers=[],
            category_id=category_id,
            status="draft",
            cloned_from_id=seller_recipe.id,
        )
        logout_user()

    assert ok, f"Purchased recipe creation failed: {purchased_recipe}"
    assert purchased_recipe.org_origin_purchased is True
    assert purchased_recipe.org_origin_type == "purchased"
    assert purchased_recipe.org_origin_recipe_id == purchased_recipe.id
    assert purchased_recipe.org_origin_source_org_id == seller_org.id
    assert purchased_recipe.org_origin_source_recipe_id == seller_recipe.root_recipe_id or seller_recipe.id
    assert purchased_recipe.root_recipe_id == seller_recipe.root_recipe_id
    assert purchased_recipe.is_sellable is False


@pytest.mark.usefixtures("app_context")
def test_variation_inherits_org_origin(app):
    user, _ = _create_user("Variation Org")
    category_id = _get_category_id()

    with app.test_request_context():
        login_user(user)
        ok, parent_recipe = create_recipe(
            name="Parent Recipe",
            description="",
            instructions="",
            yield_amount=0,
            yield_unit="",
            ingredients=[],
            consumables=[],
            allowed_containers=[],
            category_id=category_id,
            status="draft",
        )
        assert ok, f"Parent recipe failed: {parent_recipe}"

        ok, variation = create_recipe(
            name="Variation Recipe",
            description="",
            instructions="",
            yield_amount=0,
            yield_unit="",
            ingredients=[],
            consumables=[],
            allowed_containers=[],
            category_id=category_id,
            status="draft",
            parent_recipe_id=parent_recipe.id,
        )
        logout_user()

    assert ok, f"Variation creation failed: {variation}"
    assert variation.org_origin_recipe_id == parent_recipe.org_origin_recipe_id
    assert variation.org_origin_type == parent_recipe.org_origin_type
    assert variation.org_origin_purchased == parent_recipe.org_origin_purchased
    assert variation.is_sellable is True
