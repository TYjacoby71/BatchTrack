
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
import pytest
from unittest.mock import patch, MagicMock
from app import create_app
from app.extensions import db

class TestInventoryRoutesCanonicalService:
    """Verify inventory routes use canonical inventory adjustment service"""
    
    @pytest.fixture
    def app(self):
        app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
        return app
    
    @pytest.fixture
    def client(self, app):
        return app.test_client()
    
    @patch('app.blueprints.inventory.routes.process_inventory_adjustment')
    @patch('app.blueprints.inventory.routes.InventoryItem')
    @patch('app.blueprints.inventory.routes.current_user')
    def test_adjust_inventory_initial_stock_calls_canonical_service(self, mock_user, mock_item, mock_process, client, app):
        """Test that initial stock creation calls process_inventory_adjustment"""
        with app.test_request_context():
            # Mock the inventory item with no history
            mock_inventory_item = MagicMock()
            mock_inventory_item.id = 1
            mock_inventory_item.type = 'ingredient'
            mock_inventory_item.unit = 'g'
            mock_inventory_item.cost_per_unit = 2.5
            mock_inventory_item.is_perishable = False
            
            mock_item.query.get_or_404.return_value = mock_inventory_item
            mock_user.id = 1
            mock_process.return_value = True
            
            # Mock InventoryHistory count to simulate no existing history
            with patch('app.blueprints.inventory.routes.InventoryHistory') as mock_history:
                mock_history.query.filter_by.return_value.count.return_value = 0
                
                # Make POST request to adjust inventory
                response = client.post('/inventory/adjust/1', data={
                    'change_type': 'restock',
                    'quantity': '100.0',
                    'input_unit': 'g',
                    'notes': 'Initial stock',
                    'cost_entry_type': 'per_unit',
                    'cost_per_unit': '3.0'
                })
                
                # Verify canonical service was called
                mock_process.assert_called_once_with(
                    item_id=1,
                    quantity=100.0,
                    change_type="restock",
                    unit='g',
                    notes='Initial stock',
                    created_by=1,
                    cost_override=3.0
                )
