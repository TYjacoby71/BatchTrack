from unittest.mock import patch
from uuid import uuid4

import pytest
from flask_login import login_user

from app.blueprints.expiration.services import ExpirationService
from app.models import InventoryHistory, InventoryItem, Recipe, RecipeIngredient
from app.services.batch_service.batch_operations import BatchOperationsService


@pytest.mark.usefixtures("app", "db_session")
def test_batch_start_routes_all_deductions_through_canonical_service(
    app, db_session, test_user
):
    ingredient = InventoryItem(
        name=f"Canon Ingredient {uuid4().hex}",
        type="ingredient",
        unit="g",
        quantity=500,
        organization_id=test_user.organization_id,
    )
    db_session.add(ingredient)
    db_session.flush()

    recipe = Recipe(
        name=f"Batch Recipe {uuid4().hex}",
        predicted_yield=100,
        predicted_yield_unit="g",
        organization_id=test_user.organization_id,
        created_by=test_user.id,
    )
    db_session.add(recipe)
    db_session.flush()

    assoc = RecipeIngredient(
        recipe_id=recipe.id,
        inventory_item_id=ingredient.id,
        quantity=100,
        unit="g",
    )
    db_session.add(assoc)
    db_session.commit()

    plan_snapshot = {
        "recipe_id": recipe.id,
        "scale": 1.0,
        "batch_type": "ingredient",
        "notes": "",
        "containers": [],
    }

    with app.test_request_context("/"):
        login_user(test_user)

        with patch(
            "app.services.batch_service.batch_operations.process_inventory_adjustment"
        ) as mock_adjust, patch.object(
            BatchOperationsService, "_process_batch_consumables", return_value=[]
        ), patch(
            "app.services.batch_service.batch_operations.ConversionEngine.convert_units",
            side_effect=lambda qty, from_unit, to_unit, **_: {"converted_value": qty},
        ):

            mock_adjust.return_value = (True, None)

            batch, errors = BatchOperationsService.start_batch(plan_snapshot)

            assert errors == [], errors
            assert batch is not None
            assert mock_adjust.called

            calls = [c.kwargs for c in mock_adjust.call_args_list]
            ingredient_calls = [c for c in calls if c.get("item_id") == ingredient.id]
            assert ingredient_calls, "Ingredient deduction must hit canonical service"
            assert ingredient_calls[0]["change_type"] == "batch"


@pytest.mark.usefixtures("app", "db_session")
def test_expiration_service_uses_canonical_adjustment_from_inventory_routes(
    app, db_session, test_user
):
    item = InventoryItem(
        name=f"Perishable {uuid4().hex}",
        type="ingredient",
        unit="ml",
        quantity=50,
        organization_id=test_user.organization_id,
    )
    db_session.add(item)
    db_session.flush()

    history = InventoryHistory(
        inventory_item_id=item.id,
        change_type="restock",
        quantity_change=50,
        remaining_quantity=50,
        unit="ml",
    )
    db_session.add(history)
    db_session.commit()

    with app.test_request_context("/"):
        login_user(test_user)

        with patch(
            "app.blueprints.expiration.services.process_inventory_adjustment"
        ) as mock_adjust:
            mock_adjust.return_value = True

            success, message = ExpirationService.mark_as_expired(
                kind="fifo",
                entry_id=history.id,
                quantity=10,
                notes="Spoiled test stock",
            )

            assert success is True
            assert "Successfully marked" in message

            mock_adjust.assert_called_once()
            call_kwargs = mock_adjust.call_args.kwargs
            assert call_kwargs["item_id"] == item.id
            assert call_kwargs["change_type"] == "spoil"
            assert call_kwargs["quantity"] == -10
