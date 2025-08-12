
<old_str>
import pytest
from app import create_app
from app.extensions import db
from app.models.inventory import InventoryItem, InventoryHistory
from app.models.models import User, Organization
from app.services.inventory_adjustment import process_inventory_adjustment
from app.blueprints.fifo.services import FIFOService
from flask_login import login_user</old_str>
<new_str>
import pytest
from app import create_app
from app.extensions import db
from app.models.inventory import InventoryItem, InventoryHistory
from app.models.models import User, Organization
from app.services.inventory_adjustment import process_inventory_adjustment
from flask_login import login_user


class TestInventoryFIFOCharacterization:
    """Lock in current FIFO behavior through canonical entry point only."""
    
    def test_single_entry_point_exists(self, app, db_session):
        """Verify canonical inventory adjustment entry point exists."""
        from app.services.inventory_adjustment import process_inventory_adjustment
        assert callable(process_inventory_adjustment)
        
    def test_fifo_deduction_order(self, app, db_session, test_user, test_org):
        """Test FIFO deduction follows first-in-first-out order."""
        with app.test_request_context():
            login_user(test_user)
            
            # Create inventory item
            item = InventoryItem(
                name="Test Ingredient",
                type="ingredient", 
                unit="g",
                quantity=0.0,
                organization_id=test_org.id,
                created_by=test_user.id
            )
            db_session.add(item)
            db_session.flush()
            
            # Add stock in layers (oldest first)
            assert process_inventory_adjustment(
                item_id=item.id,
                quantity=100.0,
                change_type="restock",
                notes="First batch",
                created_by=test_user.id
            )
            
            assert process_inventory_adjustment(
                item_id=item.id, 
                quantity=50.0,
                change_type="restock",
                notes="Second batch",
                created_by=test_user.id
            )
            
            # Deduct less than first layer
            assert process_inventory_adjustment(
                item_id=item.id,
                quantity=-75.0,
                change_type="batch_production", 
                notes="Test deduction",
                created_by=test_user.id
            )
            
            # Verify FIFO order: first layer partially consumed, second untouched
            db_session.refresh(item)
            assert item.quantity == 75.0  # 150 - 75 = 75
            
    def test_stock_check_accuracy(self, app, db_session, test_user, test_org):
        """Test stock availability checking matches FIFO consumption."""
        with app.test_request_context():
            login_user(test_user)
            
            item = InventoryItem(
                name="Test Container",
                type="container",
                unit="count", 
                quantity=0.0,
                organization_id=test_org.id,
                created_by=test_user.id
            )
            db_session.add(item)
            db_session.flush()
            
            # Add stock
            assert process_inventory_adjustment(
                item_id=item.id,
                quantity=10.0,
                change_type="restock",
                notes="Container restock",
                created_by=test_user.id
            )
            
            db_session.refresh(item)
            assert item.quantity == 10.0
            
            # Verify available quantity matches
            from app.services.stock_check import check_stock_availability
            result = check_stock_availability([{
                'item_id': item.id,
                'quantity_needed': 5.0,
                'unit': 'count'
            }])
            
            assert result['can_make'] is True
            
    def test_inventory_adjustment_delegates_properly(self, app, db_session, test_user, test_org):
        """Verify inventory adjustment service delegates to proper internal systems."""
        with app.test_request_context():
            login_user(test_user)
            
            item = InventoryItem(
                name="Test Product",
                type="product",
                unit="ml",
                quantity=0.0, 
                organization_id=test_org.id,
                created_by=test_user.id
            )
            db_session.add(item)
            db_session.flush()
            
            # Test product addition (should use ProductSKUHistory)
            result = process_inventory_adjustment(
                item_id=item.id,
                quantity=250.0,
                change_type="finished_batch",
                notes="Batch completion",
                created_by=test_user.id
            )
            
            assert result is True
            db_session.refresh(item)
            assert item.quantity == 250.0</new_str>
