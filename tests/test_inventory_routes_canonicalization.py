
import pytest
from unittest.mock import patch
from app.models.inventory import InventoryItem


def test_recount_adjustment_uses_canonical_service(client, app, db_session, test_user):
    """Test that inventory recount routes use the canonical adjustment service"""
    
    # Create test inventory item
    item = InventoryItem(
        name="Test Item", 
        quantity=100, 
        unit="count",
        organization_id=test_user.organization_id
    )
    db_session.add(item)
    db_session.commit()
    
    # Mock the canonical service
    with patch('app.blueprints.inventory.routes.process_inventory_adjustment') as mock_adjustment:
        mock_adjustment.return_value = True
        
        # Login
        client.post('/auth/login', data={'email': test_user.email, 'password': 'password'})
        
        # Make recount request
        response = client.post(f'/inventory/adjust/{item.id}', data={
            'adjustment_type': 'recount',
            'quantity': '80',
            'notes': 'Physical count adjustment'
        })
        
        # Verify canonical service was called
        mock_adjustment.assert_called_once()
        call_args = mock_adjustment.call_args
        
        assert call_args[1]['item_id'] == item.id
        assert call_args[1]['change_type'] == 'recount'
        assert 'Physical count' in call_args[1]['notes']
