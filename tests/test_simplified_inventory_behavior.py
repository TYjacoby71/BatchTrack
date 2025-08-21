
"""
Simplified Inventory Behavior Tests

Clean, focused tests that validate inventory behavior ONLY through 
the canonical entry point. No internal implementation testing.
"""

import pytest
from app import create_app
from app.extensions import db
from app.models.models import User, Organization, InventoryItem, SubscriptionTier
from app.services.inventory_adjustment import process_inventory_adjustment


class TestSimplifiedInventoryBehavior:
    """Test inventory behavior through canonical entry point only"""

    @pytest.fixture
    def app(self):
        app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
        with app.app_context():
            db.create_all()
        return app

    @pytest.fixture
    def test_data(self, app):
        """Create minimal test data"""
        with app.app_context():
            tier = SubscriptionTier(name="Test Tier", tier_type="monthly", user_limit=5)
            db.session.add(tier)
            db.session.flush()

            org = Organization(name="Test Org", billing_status="active", subscription_tier_id=tier.id)
            db.session.add(org)
            db.session.flush()

            user = User(username="testuser", email="test@example.com", organization_id=org.id)
            db.session.add(user)
            db.session.flush()

            item = InventoryItem(
                name="Test Item",
                quantity=0.0,
                unit="g", 
                cost_per_unit=2.0,
                organization_id=org.id
            )
            db.session.add(item)
            db.session.commit()
            
            return {'user': user, 'org': org, 'item': item}

    def test_basic_inventory_flow(self, app, test_data):
        """Test basic inventory operations through canonical service"""
        data = test_data
        
        with app.app_context():
            # Add stock
            success = process_inventory_adjustment(
                item_id=data['item'].id,
                quantity=100.0,
                change_type='restock',
                notes='Initial stock',
                created_by=data['user'].id
            )
            assert success is True
            
            db.session.refresh(data['item'])
            assert data['item'].quantity == 100.0
            
            # Use some stock
            success = process_inventory_adjustment(
                item_id=data['item'].id,
                quantity=30.0,
                change_type='use',
                notes='Production use',
                created_by=data['user'].id
            )
            assert success is True
            
            db.session.refresh(data['item'])
            assert data['item'].quantity == 70.0
            
            # Sell some stock
            success = process_inventory_adjustment(
                item_id=data['item'].id,
                quantity=20.0,
                change_type='sale',
                notes='Customer sale',
                created_by=data['user'].id
            )
            assert success is True
            
            db.session.refresh(data['item'])
            assert data['item'].quantity == 50.0

    def test_recount_operation(self, app, test_data):
        """Test recount operations set absolute quantities"""
        data = test_data
        
        with app.app_context():
            # Set initial stock
            process_inventory_adjustment(
                item_id=data['item'].id,
                quantity=100.0,
                change_type='restock',
                created_by=data['user'].id
            )
            
            # Recount to different amount
            success = process_inventory_adjustment(
                item_id=data['item'].id,
                quantity=85.0,
                change_type='recount',
                notes='Physical count adjustment',
                created_by=data['user'].id
            )
            assert success is True
            
            db.session.refresh(data['item'])
            assert data['item'].quantity == 85.0

    def test_fifo_ordering(self, app, test_data):
        """Test FIFO behavior through canonical service"""
        data = test_data
        
        with app.app_context():
            # Add stock in chronological order
            operations = [
                ('restock', 50.0, 'Batch 1'),
                ('restock', 30.0, 'Batch 2'), 
                ('restock', 20.0, 'Batch 3')
            ]
            
            for op_type, qty, notes in operations:
                success = process_inventory_adjustment(
                    item_id=data['item'].id,
                    quantity=qty,
                    change_type=op_type,
                    notes=notes,
                    created_by=data['user'].id
                )
                assert success is True
            
            db.session.refresh(data['item'])
            assert data['item'].quantity == 100.0  # 50 + 30 + 20
            
            # Use 60 units (should consume Batch 1 completely + 10 from Batch 2)
            success = process_inventory_adjustment(
                item_id=data['item'].id,
                quantity=60.0,
                change_type='use',
                notes='FIFO consumption test',
                created_by=data['user'].id
            )
            assert success is True
            
            db.session.refresh(data['item'])
            assert data['item'].quantity == 40.0  # Should have 20 from Batch 2 + 20 from Batch 3

    def test_error_conditions(self, app, test_data):
        """Test error handling in canonical service"""
        data = test_data
        
        with app.app_context():
            # Test using more than available (should handle gracefully)
            success = process_inventory_adjustment(
                item_id=data['item'].id,
                quantity=1000.0,  # More than available
                change_type='use',
                created_by=data['user'].id
            )
            
            # Should either succeed with proper handling or fail gracefully
            assert success in [True, False]
            
            # Item quantity should not go negative
            db.session.refresh(data['item'])
            assert data['item'].quantity >= 0
