import pytest


def test_extras_cannot_use_expired_lot(app, db_session, test_user, test_org):
    from app.models import InventoryItem, Recipe
    from app.models.inventory_lot import InventoryLot
    from app.services.batch_service.batch_operations import BatchOperationsService
    from app.utils.timezone_utils import TimezoneUtils
    from datetime import timedelta

    # Create perishable inventory item
    item = InventoryItem(
        name="Expired Apple",
        unit="g",
        quantity=0.0,
        is_perishable=True,
        shelf_life_days=7,
        cost_per_unit=1.0,
        organization_id=test_org.id
    )
    db_session.add(item)
    db_session.flush()

    # Create an expired lot for the item
    expired_dt = TimezoneUtils.utc_now() - timedelta(days=1)
    lot = InventoryLot(
        inventory_item_id=item.id,
        remaining_quantity=100.0,
        original_quantity=100.0,
        unit="g",
        unit_cost=1.0,
        received_date=TimezoneUtils.utc_now() - timedelta(days=10),
        expiration_date=expired_dt,
        source_type="restock",
        organization_id=test_org.id
    )
    db_session.add(lot)
    db_session.flush()

    # Minimal recipe and batch
    recipe = Recipe(name="Test Recipe", predicted_yield=100, predicted_yield_unit="g", organization_id=test_org.id)
    db_session.add(recipe)
    db_session.flush()

    # Ensure a request and user context exists for batch start
    from flask_login import login_user
    from flask import current_app
    with app.test_request_context():
        login_user(test_user)
        batch, errors = BatchOperationsService.start_batch(recipe.id, scale=1.0, batch_type='ingredient', notes='test')
        assert batch is not None, f"Failed to start batch: {errors}"

    # Attempt to add expired item as an extra
    from flask_login import login_user
    with app.test_request_context():
        login_user(test_user)
        success, message, err_list = BatchOperationsService.add_extra_items_to_batch(
            batch_id=batch.id,
            extra_ingredients=[{"item_id": item.id, "quantity": 10, "unit": "g"}],
            extra_containers=[],
            extra_consumables=[]
        )

    assert success is False, "Extras addition should fail due to expired-only stock"
    assert err_list and any("Not enough" in (e.get("message") or "") or "stock" in (e.get("message") or "") for e in err_list)

