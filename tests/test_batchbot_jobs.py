import pytest
from flask_login import login_user, logout_user

from app.extensions import db
from app.models import InventoryItem, Recipe, User
from app.services.batchbot_service import BatchBotService


def _reload_user(user_id: int) -> User:
    return db.session.get(User, user_id)


def test_batchbot_recipe_draft_tool_creates_items_and_recipe(app, test_user):
    with app.app_context():
        app.config["GOOGLE_AI_API_KEY"] = "test-key"
        user = _reload_user(test_user.id)
        service = BatchBotService(user)
        user_org_id = user.organization_id

        payload = {
            "recipe_name": "BatchBot Truffle Base",
            "instructions": "Melt oils, mix, pour into molds.",
            "yield_amount": 24,
            "yield_unit": "bars",
            "status": "draft",
            "ingredients": [
                {
                    "inventory_item_name": "BatchBot Cocoa Butter",
                    "quantity": 2.5,
                    "unit": "kg",
                    "allow_create": True,
                },
                {
                    "inventory_item_name": "BatchBot Shea Butter",
                    "quantity": 1.75,
                    "unit": "kg",
                    "allow_create": True,
                },
            ],
        }

        with app.test_request_context():
            login_user(user)
            result = service._tool_create_recipe_draft(payload)
            logout_user()

        assert result["success"] is True
        assert len(result["created_inventory_items"]) == 2

        recipe = db.session.get(Recipe, result["recipe_id"])
        assert recipe is not None
        assert recipe.status == "draft"
        assert recipe.organization_id == user_org_id

        ingredient_names = sorted(
            ingredient.inventory_item.name for ingredient in recipe.recipe_ingredients
        )
        assert ingredient_names == ["BatchBot Cocoa Butter", "BatchBot Shea Butter"]
        assert sorted(result["created_inventory_items"]) == ingredient_names


def test_batchbot_bulk_inventory_tool_handles_restock_and_create(app, test_user):
    with app.app_context():
        app.config["GOOGLE_AI_API_KEY"] = "test-key"
        user = _reload_user(test_user.id)
        service = BatchBotService(user)

        existing_item = InventoryItem(
            name="Existing Olive Oil",
            organization_id=user.organization_id,
            unit="kg",
            quantity=0.0,
            type="ingredient",
        )
        db.session.add(existing_item)
        db.session.commit()
        existing_item_id = existing_item.id

        payload = {
            "lines": [
                {
                    "inventory_item_id": existing_item.id,
                    "change_type": "restock",
                    "quantity": 4,
                    "unit": "kg",
                    "cost_per_unit": 5.25,
                    "notes": "BatchBot restock",
                },
                {
                    "inventory_item_name": "Fresh Citrus Peel",
                    "change_type": "create",
                    "quantity": 2.25,
                    "unit": "kg",
                    "allow_create": True,
                },
            ]
        }

        with app.test_request_context():
            login_user(user)
            result = service._tool_submit_bulk_inventory_update(payload)
            logout_user()

        assert result["success"] is True
        assert len(result["results"]) == 2
        assert all(entry["success"] for entry in result["results"])

        refreshed_item = db.session.get(InventoryItem, existing_item_id)
        assert refreshed_item.quantity == pytest.approx(4.0)

        new_item = (
            InventoryItem.query.filter_by(
                name="Fresh Citrus Peel", organization_id=user.organization_id
            )
            .order_by(InventoryItem.id.desc())
            .first()
        )
        assert new_item is not None
        assert new_item.quantity == pytest.approx(2.25)
