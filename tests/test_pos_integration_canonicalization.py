from unittest.mock import patch
from uuid import uuid4

import pytest
from flask_login import login_user

from app.models import InventoryItem, Organization, Reservation
from app.services.pos_integration import POSIntegrationService


def test_process_sale_delegates_to_canonical_service():
    with patch(
        "app.services.pos_integration.process_inventory_adjustment"
    ) as mock_adjust:
        mock_adjust.return_value = True

        success, message = POSIntegrationService.process_sale(
            item_id=123, quantity=4, notes="Test sale"
        )

        assert success is True
        assert "Sale processed" in message

        mock_adjust.assert_called_once()
        call_kwargs = mock_adjust.call_args.kwargs
        assert call_kwargs["item_id"] == 123
        assert call_kwargs["change_type"] == "sale"
        assert call_kwargs["quantity"] == -4
        assert "POS Sale" in call_kwargs["notes"]


@pytest.mark.usefixtures("app", "db_session")
def test_reserve_inventory_calls_canonical_service(app, db_session, test_user):
    suffix = uuid4().hex
    item = InventoryItem(
        name=f"POS Item {suffix}",
        type="product",
        unit="count",
        quantity=25,
        organization_id=test_user.organization_id,
        cost_per_unit=3.0,
    )
    db_session.add(item)
    db_session.commit()

    with app.test_request_context("/"):
        login_user(test_user)

        with patch(
            "app.services.pos_integration.process_inventory_adjustment"
        ) as mock_adjust:
            mock_adjust.return_value = True

            success, message = POSIntegrationService.reserve_inventory(
                item_id=item.id,
                quantity=5,
                order_id=f"ORD-{suffix}",
                source="shopify",
                notes="Reserve for test",
            )

            assert success is True
            assert "ORD-" in message

            assert mock_adjust.call_count == 2
            reserve_call = mock_adjust.call_args_list[0].kwargs
            allocation_call = mock_adjust.call_args_list[1].kwargs

            assert reserve_call["item_id"] == item.id
            assert reserve_call["change_type"] == "reserved"
            assert reserve_call["quantity"] == 5

            assert allocation_call["change_type"] == "reserved_allocation"
            assert allocation_call["quantity"] == 5


@pytest.mark.usefixtures("app", "db_session")
def test_confirm_sale_uses_canonical_service(app, db_session):
    suffix = uuid4().hex
    org = Organization(name=f"POS Org {suffix}")
    db_session.add(org)
    db_session.flush()

    product = InventoryItem(
        name=f"Sold Product {suffix}",
        type="product",
        unit="piece",
        quantity=30,
        organization_id=org.id,
    )
    reserved = InventoryItem(
        name=f"Sold Product {suffix} (Reserved)",
        type="product-reserved",
        unit="piece",
        quantity=5,
        organization_id=org.id,
    )
    db_session.add_all([product, reserved])
    db_session.flush()

    reservation = Reservation(
        order_id=f"ORDER-{suffix}",
        product_item_id=product.id,
        reserved_item_id=reserved.id,
        quantity=5,
        unit="piece",
        unit_cost=2.5,
        organization_id=org.id,
        status="active",
    )
    db_session.add(reservation)
    db_session.commit()

    with patch(
        "app.services.pos_integration.process_inventory_adjustment"
    ) as mock_adjust:
        mock_adjust.return_value = True

        success, message = POSIntegrationService.confirm_sale(
            order_id=f"ORDER-{suffix}", notes="Shipment fulfilled"
        )

        assert success is True
        assert "Confirmed sale" in message

        sale_call = mock_adjust.call_args_list[0].kwargs
        assert sale_call["item_id"] == product.id
        assert sale_call["change_type"] == "sale"
        assert sale_call["quantity"] == -5
        assert "POS Sale" in sale_call["notes"]


@pytest.mark.usefixtures("app", "db_session")
def test_confirm_return_uses_canonical_service(app, db_session):
    suffix = uuid4().hex
    org = Organization(name=f"POS Org Return {suffix}")
    db_session.add(org)
    db_session.flush()

    product = InventoryItem(
        name=f"Returned Product {suffix}",
        type="product",
        unit="piece",
        quantity=10,
        organization_id=org.id,
    )
    reserved = InventoryItem(
        name=f"Returned Product {suffix} (Reserved)",
        type="product-reserved",
        unit="piece",
        quantity=0,
        organization_id=org.id,
    )
    db_session.add_all([product, reserved])
    db_session.flush()

    reservation = Reservation(
        order_id=f"ORDER-{suffix}",
        product_item_id=product.id,
        reserved_item_id=reserved.id,
        quantity=4,
        unit="piece",
        status="converted_to_sale",
        organization_id=org.id,
    )
    db_session.add(reservation)
    db_session.commit()

    with patch(
        "app.services.pos_integration.process_inventory_adjustment"
    ) as mock_adjust:
        mock_adjust.return_value = True

        with patch.object(
            Reservation,
            "mark_returned",
            lambda self: setattr(self, "status", "returned"),
            create=True,
        ):
            success, message = POSIntegrationService.confirm_return(
                order_id=f"ORDER-{suffix}", notes="Customer return"
            )

        assert success is True, message
        assert "Processed return" in message

        return_call = mock_adjust.call_args_list[0].kwargs
        assert return_call["item_id"] == product.id
        assert return_call["change_type"] == "return"
        assert return_call["quantity"] == 4
