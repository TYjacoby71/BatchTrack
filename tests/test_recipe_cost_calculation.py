"""Regression tests for recipe costing unit conversion."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.extensions import db
from app.models import InventoryItem, Recipe, RecipeIngredient
from app.models.models import Organization, User
from app.models.product_category import ProductCategory
from app.services.production_planning._stock_validation import (
    validate_ingredients_with_uscs,
)
from app.services.recipe_cost_service import calculate_recipe_line_item_cost
from app.services.stock_check import UniversalStockCheckService


def _unique_name(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _create_recipe_with_honey_line(org: Organization) -> tuple[Recipe, InventoryItem]:
    category = ProductCategory(name=_unique_name("Cost Category"))
    db.session.add(category)
    db.session.flush()

    honey = InventoryItem(
        name=_unique_name("Honey"),
        unit="lb",
        type="ingredient",
        quantity=10.0,
        cost_per_unit=10.89,
        organization_id=org.id,
    )
    db.session.add(honey)
    db.session.flush()

    recipe = Recipe(
        name=_unique_name("Honey Recipe"),
        instructions="Mix ingredients",
        predicted_yield=100.0,
        predicted_yield_unit="gram",
        category_id=category.id,
        organization_id=org.id,
        status="published",
        is_current=True,
    )
    db.session.add(recipe)
    db.session.flush()

    db.session.add(
        RecipeIngredient(
            recipe_id=recipe.id,
            inventory_item_id=honey.id,
            quantity=50.0,
            unit="gram",
        )
    )
    db.session.commit()
    return recipe, honey


@pytest.mark.usefixtures("app_context")
def test_recipe_line_item_cost_converts_recipe_unit_to_inventory_unit():
    org = Organization.query.first()
    _recipe, honey = _create_recipe_with_honey_line(org)

    line_cost = calculate_recipe_line_item_cost(
        quantity=50.0,
        recipe_unit="gram",
        inventory_item=honey,
    )

    assert line_cost is not None
    assert line_cost == pytest.approx(1.2004, rel=1e-3)


@pytest.mark.usefixtures("app_context")
def test_validate_ingredients_cost_uses_inventory_unit_conversion(monkeypatch):
    org = Organization.query.first()
    recipe, honey = _create_recipe_with_honey_line(org)

    def _fake_check_recipe_stock(_self, recipe_id, scale):
        assert recipe_id == recipe.id
        assert scale == 1.0
        return {
            "success": True,
            "stock_check": [
                {
                    "item_id": honey.id,
                    "item_name": honey.name,
                    "needed_quantity": 50.0,
                    "needed_unit": "gram",
                    "available_quantity": 1000.0,
                    "status": "OK",
                }
            ],
        }

    monkeypatch.setattr(
        UniversalStockCheckService,
        "check_recipe_stock",
        _fake_check_recipe_stock,
    )

    requirements = validate_ingredients_with_uscs(
        recipe=recipe,
        scale=1.0,
        organization_id=org.id,
    )

    assert len(requirements) == 1
    assert requirements[0].total_cost == pytest.approx(1.2004, rel=1e-3)
    assert requirements[0].total_cost != pytest.approx(544.50, rel=1e-6)


def test_view_recipe_cost_card_uses_converted_units(app, client):
    with app.app_context():
        org = Organization.query.first()
        user = User.query.filter_by(organization_id=org.id).first()
        recipe, honey = _create_recipe_with_honey_line(org)
        user_id = user.id
        recipe_id = recipe.id
        honey_name = honey.name

    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True

    response = client.get(f"/recipes/{recipe_id}/view")
    assert response.status_code == 200
    body = response.get_data(as_text=True)

    assert honey_name in body
    assert "$1.20" in body
    assert "$544.50" not in body
