import pytest
from unittest.mock import patch
from uuid import uuid4

from flask_login import login_user

from app.models import InventoryItem, Reservation
from app.models.inventory_lot import InventoryLot
from app.services.reservation_service import ReservationService
from app.utils.timezone_utils import TimezoneUtils
from app.services.quantity_base import to_base_quantity, sync_item_quantity_from_base, sync_lot_quantities_from_base


@pytest.mark.usefixtures("app", "db_session")
class TestReservationCanonicalService:
    """Ensure reservation flows exercise the canonical FIFO helpers."""

    def test_create_reservation_creates_reserved_item_and_tracks_fifo(self, app, db_session, test_user):
        """create_reservation should materialize a reserved item and store FIFO lot metadata."""
        with app.test_request_context("/"):
            login_user(test_user)

            product = InventoryItem(
                name=f"Test Product {uuid4().hex[:6]}",
                type="product",
                unit="piece",
                quantity=20.0,
                cost_per_unit=4.25,
                organization_id=test_user.organization_id,
            )
            db_session.add(product)
            db_session.flush()
            product.quantity_base = to_base_quantity(20.0, product.unit, ingredient_id=product.id, density=product.density)
            sync_item_quantity_from_base(product)

            lot = InventoryLot(
                inventory_item_id=product.id,
                remaining_quantity=20.0,
                original_quantity=20.0,
                unit=product.unit,
                unit_cost=product.cost_per_unit,
                received_date=TimezoneUtils.utc_now(),
                source_type="restock",
                organization_id=product.organization_id,
                fifo_code=f"LOT-{uuid4().hex[:8]}",
            )
            lot.remaining_quantity_base = to_base_quantity(20.0, lot.unit, ingredient_id=product.id, density=product.density)
            lot.original_quantity_base = lot.remaining_quantity_base
            db_session.add(lot)
            db_session.commit()
            sync_lot_quantities_from_base(lot, product)

            reservation, error = ReservationService.create_reservation(
                inventory_item_id=product.id,
                quantity=5.0,
                order_id="ORD-CREATE-001",
                source_fifo_id=lot.id,
                unit_cost=product.cost_per_unit,
                notes="Reserved for order test",
                customer="Test Customer",
            )

            assert error is None
            db_session.commit()

            reserved_item = db_session.get(InventoryItem, reservation.reserved_item_id)
            assert reserved_item is not None
            assert reserved_item.type == "product-reserved"
            assert pytest.approx(reserved_item.quantity, rel=1e-9) == 5.0
            assert reservation.source_fifo_id == lot.id
            assert reservation.status == "active"

    def test_release_reservation_credits_fifo_and_marks_reservation(self, app, db_session, test_user):
        """release_reservation should call credit_specific_lot and update reserved inventory."""
        with app.test_request_context("/"):
            login_user(test_user)

            product = InventoryItem(
                name=f"Release Product {uuid4().hex[:6]}",
                type="product",
                unit="piece",
                quantity=10.0,
                cost_per_unit=6.0,
                organization_id=test_user.organization_id,
            )
            db_session.add(product)
            db_session.flush()
            product.quantity_base = to_base_quantity(10.0, product.unit, ingredient_id=product.id, density=product.density)
            sync_item_quantity_from_base(product)

            reserved_item = ReservationService.get_reserved_item_for_product(product.id)
            reserved_item.quantity_base = to_base_quantity(5.0, reserved_item.unit, ingredient_id=reserved_item.id, density=reserved_item.density)
            sync_item_quantity_from_base(reserved_item)

            lot = InventoryLot(
                inventory_item_id=product.id,
                remaining_quantity=10.0,
                original_quantity=10.0,
                unit=product.unit,
                unit_cost=product.cost_per_unit,
                received_date=TimezoneUtils.utc_now(),
                source_type="restock",
                organization_id=product.organization_id,
                fifo_code=f"LOT-{uuid4().hex[:8]}",
            )
            lot.remaining_quantity_base = to_base_quantity(10.0, lot.unit, ingredient_id=product.id, density=product.density)
            lot.original_quantity_base = lot.remaining_quantity_base
            db_session.add(lot)
            db_session.flush()
            sync_lot_quantities_from_base(lot, product)

            reservation = Reservation(
                order_id="ORD-RELEASE-001",
                product_item_id=product.id,
                reserved_item_id=reserved_item.id,
                quantity=5.0,
                unit=product.unit,
                unit_cost=product.cost_per_unit,
                organization_id=product.organization_id,
                status="active",
                source_fifo_id=lot.id,
            )
            db_session.add(reservation)
            db_session.commit()

            with patch("app.services.reservation_service.credit_specific_lot", return_value=(True, "Credited")) as mock_credit:
                success, message = ReservationService.release_reservation(reservation.order_id)

            assert success is True
            assert "Released" in message

            mock_credit.assert_called_once()
            call_args = mock_credit.call_args
            assert call_args.args[0] == lot.id
            assert call_args.args[1] == reservation.quantity
            assert call_args.kwargs["created_by"] == test_user.id
            assert "credit back lot" in call_args.kwargs["notes"]

            updated_reservation = db_session.get(Reservation, reservation.id)
            assert updated_reservation.status == "released"

            db_session.refresh(reserved_item)
            assert pytest.approx(reserved_item.quantity, rel=1e-9) == 0.0

    def test_get_total_reserved_counts_only_active(self, app, db_session, test_user):
        """get_total_reserved_for_item should ignore released reservations."""
        with app.app_context():
            product = InventoryItem(
                name=f"Summary Product {uuid4().hex[:6]}",
                type="product",
                unit="piece",
                quantity=30.0,
                cost_per_unit=2.5,
                organization_id=test_user.organization_id,
            )
            db_session.add(product)
            db_session.flush()
            product.quantity_base = to_base_quantity(30.0, product.unit, ingredient_id=product.id, density=product.density)
            sync_item_quantity_from_base(product)

            reserved_item = ReservationService.get_reserved_item_for_product(product.id)
            db_session.flush()

            active_qty = 7.0
            released_qty = 3.0

            active_reservation = Reservation(
                order_id="ORD-SUMMARY-ACTIVE",
                product_item_id=product.id,
                reserved_item_id=reserved_item.id,
                quantity=active_qty,
                unit=product.unit,
                unit_cost=product.cost_per_unit,
                organization_id=product.organization_id,
                status="active",
            )
            released_reservation = Reservation(
                order_id="ORD-SUMMARY-REL",
                product_item_id=product.id,
                reserved_item_id=reserved_item.id,
                quantity=released_qty,
                unit=product.unit,
                unit_cost=product.cost_per_unit,
                organization_id=product.organization_id,
                status="released",
            )
            db_session.add_all([active_reservation, released_reservation])
            reserved_item.quantity = active_qty + released_qty
            db_session.commit()

            total_reserved = ReservationService.get_total_reserved_for_item(product.id)
            assert pytest.approx(total_reserved, rel=1e-9) == active_qty
