
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
import pytest
from unittest.mock import patch, MagicMock
from app.blueprints.expiration.services import ExpirationService

class TestExpirationCanonicalService:
    """Verify expiration operations use canonical inventory adjustment service"""
    
    @patch('app.blueprints.expiration.services.process_inventory_adjustment')
    @patch('app.blueprints.expiration.services.InventoryHistory')
    @patch('app.blueprints.expiration.services.current_user')
    def test_mark_fifo_expired_calls_canonical_service(self, mock_user, mock_history, mock_process):
        """Test that marking FIFO entry as expired calls process_inventory_adjustment"""
        # Mock the FIFO entry
        mock_fifo_entry = MagicMock()
        mock_fifo_entry.id = 123
        mock_fifo_entry.inventory_item_id = 456
        mock_fifo_entry.remaining_quantity = 10.0
        mock_fifo_entry.unit = 'g'
        
        mock_history.query.get.return_value = mock_fifo_entry
        mock_user.id = 1
        mock_user.is_authenticated = True
        mock_process.return_value = True
        
        # Call the service
        success, message = ExpirationService.mark_as_expired('fifo', 123, quantity=5.0, notes="Test expiration")
        
        # Verify canonical service was called
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
    @patch('app.blueprints.expiration.services.ProductSKUHistory')
    @patch('app.blueprints.expiration.services.current_user')
    def test_mark_product_expired_calls_canonical_service(self, mock_user, mock_sku_history, mock_process):
        """Test that marking product SKU as expired calls process_inventory_adjustment"""
        # Mock the product SKU history entry
        mock_sku_entry = MagicMock()
        mock_sku_entry.id = 789
        mock_sku_entry.inventory_item_id = 101
        mock_sku_entry.remaining_quantity = 20.0
        mock_sku_entry.unit = 'ml'
        
        mock_sku_history.query.get.return_value = mock_sku_entry
        mock_user.id = 2
        mock_user.is_authenticated = True
        mock_process.return_value = True
        
        # Call the service
        success, message = ExpirationService.mark_as_expired('product', 789, quantity=15.0, notes="Product expired")
        
        # Verify canonical service was called with product type
        mock_process.assert_called_once_with(
            item_id=101,
            quantity=-15.0,
            change_type="spoil",
            unit='ml',
            notes="Expired product lot disposal #789: Product expired",
            created_by=2,
            item_type='product'
        )
        
        assert success is True
        assert "Successfully marked product FIFO entry" in message
