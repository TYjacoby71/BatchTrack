
import pytest
from unittest.mock import patch
from app.services.pos_integration import POSIntegrationService
from app.models.inventory import InventoryItem
from app.models.product import ProductSKU


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
