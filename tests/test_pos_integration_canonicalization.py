import pytest
from unittest.mock import patch, MagicMock
from app.services.pos_integration import POSIntegrationService


def test_pos_sale_uses_canonical_service(app, db_session):
    """Test that POS sales use the canonical inventory adjustment service"""

    # Create test data
    item = InventoryItem(name="Test Product", quantity=100, unit="count")
    db_session.add(item)

    sku = ProductSKU(
        name="Test SKU",
        inventory_item_id=item.id,
        quantity=100
    )
    db_session.add(sku)
    db_session.commit()

    # Mock the canonical service
    with patch('app.services.pos_integration.process_inventory_adjustment') as mock_adjustment:
        mock_adjustment.return_value = True

        # Call POS sale
        success, message = POSIntegrationService.process_sale(
            item_id=item.id,
            quantity=10,
            notes="Test POS sale"
        )

        # Verify canonical service was called
        mock_adjustment.assert_called_once()
        call_args = mock_adjustment.call_args

        assert call_args[1]['item_id'] == item.id
        assert call_args[1]['quantity'] == -10  # Negative for deduction
        assert call_args[1]['change_type'] == 'sale'
        assert 'POS Sale' in call_args[1]['notes']
        assert success is True

class TestPOSIntegrationCanonicalService:
    """Verify POS integration uses canonical inventory adjustment service"""

    @patch('app.services.pos_integration.process_inventory_adjustment')
    @patch('app.services.pos_integration.InventoryItem')
    @patch('app.services.pos_integration.ReservationService')
    @patch('app.services.pos_integration.current_user')
    def test_reserve_inventory_calls_canonical_service(self, mock_user, mock_reservation_service, mock_item, mock_process):
        """Test that inventory reservation calls process_inventory_adjustment"""
        # Mock the original inventory item
        mock_original_item = MagicMock()
        mock_original_item.id = 1
        mock_original_item.name = "Test Product"
        mock_original_item.type = 'product'
        mock_original_item.unit = 'piece'
        mock_original_item.cost_per_unit = 10.0
        mock_original_item.available_quantity = 50.0
        mock_original_item.organization_id = 1

        # Mock reserved item
        mock_reserved_item = MagicMock()
        mock_reserved_item.id = 2
        mock_reserved_item.quantity = 0.0

        mock_item.query.get.return_value = mock_original_item
        mock_item.query.filter_by.return_value.first.return_value = mock_reserved_item

        mock_user.id = 1
        mock_user.is_authenticated = True
        mock_user.organization_id = 1

        # Mock ReservationService.create_reservation
        mock_create_reservation = MagicMock()
        mock_reservation_service.create_reservation.return_value = (MagicMock(), None)

        # Mock process_inventory_adjustment to succeed
        mock_process.return_value = (True, "Success")

        # Mock reservation creation to succeed
        mock_create_reservation.return_value = (MagicMock(), None)

        # Call the service
        success, message = POSIntegrationService.reserve_inventory(
            item_id=1,
            quantity=5.0,
            order_id="ORD-123",
            source="shopify",
            notes="Test reservation"
        )

        # Verify canonical service was called at least once
        # The exact number depends on the implementation details
        assert mock_process.called, "process_inventory_adjustment should be called"

        # Verify reservation service was called
        assert mock_reservation_service.create_reservation.called, "ReservationService.create_reservation should be called"