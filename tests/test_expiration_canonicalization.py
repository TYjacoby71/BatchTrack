
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
