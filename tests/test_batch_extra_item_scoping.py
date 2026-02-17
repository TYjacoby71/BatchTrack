from __future__ import annotations

import pytest
from flask_login import login_user

from app.extensions import db
from app.models import Batch, InventoryItem
from app.models.models import Organization, User
from app.models.product_category import ProductCategory
from app.models.recipe import Recipe
from app.services.batch_service.batch_management import BatchManagementService
from app.services.batch_service.batch_operations import BatchOperationsService


def _build_in_progress_batch_for_user(user: User) -> Batch:
    category = ProductCategory.query.filter_by(name="Uncategorized").first()
    assert category is not None

    recipe = Recipe(
        name="Scoped Extras Recipe",
        label_prefix="SCOPED",
        predicted_yield=10.0,
        predicted_yield_unit="gram",
        category_id=category.id,
        organization_id=user.organization_id,
        created_by=user.id,
    )
    db.session.add(recipe)
    db.session.flush()

    batch = Batch(
        recipe_id=recipe.id,
        label_code="SCOPED-001",
        batch_type="ingredient",
        status="in_progress",
        organization_id=user.organization_id,
        created_by=user.id,
        scale=1.0,
    )
    db.session.add(batch)
    db.session.commit()
    return batch


@pytest.mark.usefixtures("app_context")
def test_batch_context_inventory_lists_are_scoped_to_batch_org(app):
    with app.test_request_context("/"):
        user = User.query.filter_by(email="test@example.com").first()
        assert user is not None
        login_user(user)

        batch = _build_in_progress_batch_for_user(user)

        foreign_org = Organization(name="Foreign Org")
        db.session.add(foreign_org)
        db.session.flush()

        own_ingredient = InventoryItem(
            name="Own Ingredient",
            type="ingredient",
            unit="gram",
            quantity=25.0,
            cost_per_unit=0.0042,
            organization_id=user.organization_id,
            is_active=True,
            is_archived=False,
        )
        own_consumable = InventoryItem(
            name="Own Consumable",
            type="consumable",
            unit="gram",
            quantity=10.0,
            organization_id=user.organization_id,
            is_active=True,
            is_archived=False,
        )
        own_container = InventoryItem(
            name="Own Container",
            type="container",
            unit="count",
            quantity=12.0,
            organization_id=user.organization_id,
            is_active=True,
            is_archived=False,
        )
        inactive_item = InventoryItem(
            name="Inactive Ingredient",
            type="ingredient",
            unit="gram",
            quantity=99.0,
            organization_id=user.organization_id,
            is_active=False,
            is_archived=False,
        )
        archived_item = InventoryItem(
            name="Archived Ingredient",
            type="ingredient",
            unit="gram",
            quantity=99.0,
            organization_id=user.organization_id,
            is_active=True,
            is_archived=True,
        )
        foreign_ingredient = InventoryItem(
            name="Foreign Ingredient",
            type="ingredient",
            unit="gram",
            quantity=25.0,
            organization_id=foreign_org.id,
            is_active=True,
            is_archived=False,
        )
        foreign_consumable = InventoryItem(
            name="Foreign Consumable",
            type="consumable",
            unit="gram",
            quantity=25.0,
            organization_id=foreign_org.id,
            is_active=True,
            is_archived=False,
        )
        foreign_container = InventoryItem(
            name="Foreign Container",
            type="container",
            unit="count",
            quantity=10.0,
            organization_id=foreign_org.id,
            is_active=True,
            is_archived=False,
        )
        db.session.add_all(
            [
                own_ingredient,
                own_consumable,
                own_container,
                inactive_item,
                archived_item,
                foreign_ingredient,
                foreign_consumable,
                foreign_container,
            ]
        )
        db.session.commit()

        context = BatchManagementService.get_batch_context_data(batch)

        ingredient_ids = {item.id for item in context["all_ingredients"]}
        consumable_ids = {item.id for item in context["all_consumables"]}
        inventory_ids = {item.id for item in context["inventory_items"]}

        assert own_ingredient.id in ingredient_ids
        assert own_consumable.id in consumable_ids
        assert own_container.id in inventory_ids

        assert inactive_item.id not in ingredient_ids
        assert archived_item.id not in ingredient_ids

        assert foreign_ingredient.id not in ingredient_ids
        assert foreign_consumable.id not in consumable_ids
        assert foreign_container.id not in inventory_ids


@pytest.mark.usefixtures("app_context")
@pytest.mark.parametrize(
    ("item_type", "message"),
    [
        ("ingredient", "Ingredient not found"),
        ("container", "Container not found"),
        ("consumable", "Consumable not found"),
    ],
)
def test_add_extra_items_rejects_cross_org_item_ids(app, item_type, message):
    with app.test_request_context("/"):
        user = User.query.filter_by(email="test@example.com").first()
        assert user is not None
        login_user(user)

        batch = _build_in_progress_batch_for_user(user)

        foreign_org = Organization(name=f"Foreign Org {item_type}")
        db.session.add(foreign_org)
        db.session.flush()

        foreign_item = InventoryItem(
            name=f"Foreign {item_type.title()}",
            type=item_type,
            unit="count" if item_type == "container" else "gram",
            quantity=100.0,
            organization_id=foreign_org.id,
            is_active=True,
            is_archived=False,
        )
        db.session.add(foreign_item)
        db.session.commit()

        extra_ingredients = []
        extra_containers = []
        extra_consumables = []
        if item_type == "ingredient":
            extra_ingredients = [
                {"item_id": foreign_item.id, "quantity": 2.0, "unit": "gram"}
            ]
        elif item_type == "container":
            extra_containers = [
                {"item_id": foreign_item.id, "quantity": 1, "reason": "extra_yield"}
            ]
        else:
            extra_consumables = [
                {"item_id": foreign_item.id, "quantity": 2.0, "unit": "gram"}
            ]

        success, _, errors = BatchOperationsService.add_extra_items_to_batch(
            batch_id=batch.id,
            extra_ingredients=extra_ingredients,
            extra_containers=extra_containers,
            extra_consumables=extra_consumables,
        )

        assert success is False
        assert any(err.get("message") == message for err in errors)


@pytest.mark.usefixtures("app_context")
def test_format_unit_cost_filter_shows_subcent_precision(app):
    formatter = app.jinja_env.filters["format_unit_cost"]
    assert formatter(0) == "$0.00"
    assert formatter(0.25) == "$0.25"
    assert formatter(0.0042) == "$0.0042"
