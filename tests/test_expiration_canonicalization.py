import pytest
from unittest.mock import patch, MagicMock
from app.blueprints.expiration.services import ExpirationService
from app.models.inventory import InventoryHistory, InventoryItem


def test_expiration_service_uses_canonical_adjustment(app, db_session):
    """Test that expiration disposal uses the canonical inventory adjustment service"""

    # Create test data
    item = InventoryItem(name="Test Item", quantity=100, unit="count")
    db_session.add(item)
    db_session.commit()

    fifo_entry = InventoryHistory(
        inventory_item_id=item.id,
        remaining_quantity=50,
        unit="count"
    )
    db_session.add(fifo_entry)
    db_session.commit()

    # Mock the canonical service
    with patch('app.blueprints.expiration.services.process_inventory_adjustment') as mock_adjustment:
        mock_adjustment.return_value = True

        # Call the expiration service
        result = ExpirationService.mark_as_expired('fifo', fifo_entry.id, 50, 'Test expiration')

        # Verify canonical service was called
        mock_adjustment.assert_called_once()
        call_args = mock_adjustment.call_args

        assert call_args[1]['item_id'] == item.id
        assert call_args[1]['quantity'] == -50  # Negative for deduction
        assert call_args[1]['change_type'] == 'spoil'
        assert 'Expired lot' in call_args[1]['notes']

class TestExpirationCanonicalService:
    """Verify expiration operations use canonical inventory adjustment service"""

    @patch('app.blueprints.expiration.services.process_inventory_adjustment')
    @patch('app.blueprints.expiration.services.db')
    @patch('app.blueprints.expiration.services.current_user')
    def test_mark_fifo_expired_calls_canonical_service(self, mock_user, mock_db, mock_process):
        """Test that marking FIFO entry as expired calls process_inventory_adjustment"""
        from app import create_app
        from app.blueprints.expiration import services as expiration_services

        app = create_app({'TESTING': True})
        with app.app_context():
            mock_fifo_entry = MagicMock()
            mock_fifo_entry.id = 123
            mock_fifo_entry.inventory_item_id = 456
            mock_fifo_entry.remaining_quantity = 10.0
            mock_fifo_entry.unit = 'g'

            InventoryLot = expiration_services.InventoryLot
            UnifiedInventoryHistory = expiration_services.UnifiedInventoryHistory
            InventoryHistory = expiration_services.InventoryHistory

            def fake_get(model, entry_id):
                if model is InventoryLot:
                    return None
                if model is UnifiedInventoryHistory:
                    return None
                if model is InventoryHistory:
                    return mock_fifo_entry
                return None

            mock_db.session.get.side_effect = fake_get
            mock_user.id = 1
            mock_user.is_authenticated = True
            mock_process.return_value = True

            success, message = ExpirationService.mark_as_expired('fifo', 123, quantity=5.0, notes="Test expiration")

            mock_process.assert_called_once_with(
                item_id=456,
                quantity=-5.0,
                change_type="spoil",
                unit='g',
                notes="Expired lot disposal #123: Test expiration",
                created_by=1
            )

            assert success is True
            assert "Successfully marked FIFO entry" in message

    @patch('app.blueprints.expiration.services.process_inventory_adjustment')
    @patch('app.blueprints.expiration.services.db')
    @patch('app.blueprints.expiration.services.current_user')
    def test_mark_product_expired_calls_canonical_service(self, mock_user, mock_db, mock_process):
        """Test that marking product SKU as expired calls process_inventory_adjustment"""
        from app import create_app
        from app.blueprints.expiration import services as expiration_services

        app = create_app({'TESTING': True})
        with app.app_context():
            mock_lot_entry = MagicMock()
            mock_lot_entry.id = 789
            mock_lot_entry.inventory_item_id = 101
            mock_lot_entry.remaining_quantity = 20.0
            mock_lot_entry.unit = 'ml'

            InventoryLot = expiration_services.InventoryLot

            def fake_get(model, entry_id):
                if model is InventoryLot and entry_id == mock_lot_entry.id:
                    return mock_lot_entry
                return None

            mock_db.session.get.side_effect = fake_get
            mock_user.id = 2
            mock_user.is_authenticated = True
            mock_process.return_value = True

            success, message = ExpirationService.mark_as_expired('product', 789, quantity=15.0, notes="Product expired")

            mock_process.assert_called_once_with(
                item_id=101,
                quantity=-15.0,
                change_type="spoil",
                unit='ml',
                notes="Expired product lot disposal #789: Product expired",
                created_by=2
            )

            assert success is True
            assert "Successfully marked product FIFO entry" in message