import pytest

from app.extensions import db
from app.models import GlobalItem, InventoryItem
from app.services.bulk_inventory_service import BulkInventoryService


def _make_inventory_item(
    org_id: int, name: str = "Test Oil", quantity: float = 0.0
) -> InventoryItem:
    item = InventoryItem(
        name=name,
        organization_id=org_id,
        unit="gram",
        quantity=quantity,
        type="ingredient",
    )
    db.session.add(item)
    db.session.commit()
    return item


def test_bulk_service_restock_existing_item(app, test_user):
    with app.app_context():
        item = _make_inventory_item(test_user.organization_id)
        service = BulkInventoryService(
            organization_id=test_user.organization_id, user=test_user
        )

        payload = [
            {
                "inventory_item_id": item.id,
                "inventory_item_name": item.name,
                "inventory_type": item.type,
                "change_type": "restock",
                "quantity": 3,
                "unit": "gram",
            }
        ]

        result = service.submit_bulk_inventory_update(payload)

        assert result["success"] is True
        assert result["results"][0]["success"] is True
        updated = db.session.get(InventoryItem, item.id)
        assert pytest.approx(float(updated.quantity)) == 3.0


def test_bulk_service_creates_inventory_from_global_item(app, test_user):
    with app.app_context():
        global_item = GlobalItem(
            name="Global Wax", item_type="ingredient", default_unit="oz"
        )
        db.session.add(global_item)
        db.session.commit()

        service = BulkInventoryService(
            organization_id=test_user.organization_id, user=test_user
        )

        payload = [
            {
                "inventory_item_name": "My Global Wax",
                "inventory_type": "ingredient",
                "change_type": "create",
                "quantity": 7,
                "unit": "oz",
                "global_item_id": global_item.id,
                "allow_create": True,
            }
        ]

        result = service.submit_bulk_inventory_update(payload)

        assert result["success"] is True
        created = InventoryItem.query.filter_by(
            name="My Global Wax", organization_id=test_user.organization_id
        ).first()
        assert created is not None
        assert pytest.approx(float(created.quantity)) == 7.0
        assert created.unit == "oz"


def test_bulk_service_returns_draft_when_not_submitting(app, test_user):
    with app.app_context():
        service = BulkInventoryService(
            organization_id=test_user.organization_id, user=test_user
        )

        payload = [
            {
                "inventory_item_name": "Draft Item",
                "inventory_type": "ingredient",
                "change_type": "create",
                "quantity": 2,
                "unit": "gram",
            }
        ]

        result = service.submit_bulk_inventory_update(payload, submit_now=False)

        assert result["success"] is True
        assert "draft" in result
        assert isinstance(result["draft"], list)
        assert result["draft"][0]["quantity"] == 2.0


def test_bulk_service_aborts_and_rolls_back_on_error(app, test_user):
    with app.app_context():
        item = _make_inventory_item(test_user.organization_id)
        service = BulkInventoryService(
            organization_id=test_user.organization_id, user=test_user
        )

        payload = [
            {
                "inventory_item_id": item.id,
                "inventory_item_name": item.name,
                "inventory_type": item.type,
                "change_type": "restock",
                "quantity": 2,
                "unit": "gram",
            },
            {
                "inventory_item_id": item.id,
                "inventory_item_name": item.name,
                "inventory_type": item.type,
                "change_type": "restock",
                "quantity": 0,  # invalid to trigger abort
                "unit": "gram",
            },
        ]

        result = service.submit_bulk_inventory_update(payload)

        assert result["success"] is False
        assert "Bulk inventory aborted" in result["error"]
        db.session.refresh(item)
        assert pytest.approx(float(item.quantity or 0)) == 0.0


def test_bulk_service_creates_custom_item_without_global(app, test_user):
    with app.app_context():
        service = BulkInventoryService(
            organization_id=test_user.organization_id, user=test_user
        )

        payload = [
            {
                "inventory_item_name": "Custom Cocoa Chips",
                "inventory_type": "ingredient",
                "change_type": "create",
                "quantity": 4,
                "unit": "scoops",
                "allow_create": True,
            }
        ]

        result = service.submit_bulk_inventory_update(payload)

        assert result["success"] is True
        created = InventoryItem.query.filter_by(
            name="Custom Cocoa Chips", organization_id=test_user.organization_id
        ).first()
        assert created is not None
        assert created.unit == "scoops"
        assert pytest.approx(float(created.quantity)) == 4.0
