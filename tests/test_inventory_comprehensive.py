
"""
Comprehensive Inventory System Test Suite

This test suite validates ALL inventory operations through the canonical
inventory adjustment service. It ensures every inventory action works
correctly with FIFO logic, audit trails, and data consistency.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from flask_login import login_user
from app.models import (
    db, InventoryItem, UnifiedInventoryHistory, User, Organization, 
    SubscriptionTier
)
from app.services.inventory_adjustment import (
    process_inventory_adjustment,
    create_inventory_item, 
    update_inventory_item,
    validate_inventory_fifo_sync
)


class TestInventorySystemComprehensive:
    """Comprehensive test suite for all inventory operations"""

    @pytest.fixture
    def setup_test_data(self, app, db_session):
        """Setup test organization, user, and base items for testing"""
        with app.test_request_context():
            # Create tier
            tier = SubscriptionTier(
                name="Test Tier",
                tier_type="monthly",
                user_limit=10,
                max_inventory_items=1000
            )
            db_session.add(tier)
            db_session.flush()

            # Create organization
            org = Organization(
                name="Test Org",
                billing_status='active',
                subscription_tier_id=tier.id
            )
            db_session.add(org)
            db_session.flush()

            # Create user
            user = User(
                username="test_inventory_user",
                email="inventory@test.com",
                organization_id=org.id
            )
            db_session.add(user)
            db_session.flush()

            # Create test inventory items
            ingredient = InventoryItem(
                name="Test Ingredient",
                type="ingredient",
                unit="g",
                quantity=0.0,
                cost_per_unit=0.50,
                organization_id=org.id
            )
            
            product = InventoryItem(
                name="Test Product", 
                type="product",
                unit="ml",
                quantity=0.0,
                cost_per_unit=5.0,
                organization_id=org.id
            )
            
            container = InventoryItem(
                name="Test Container",
                type="container",
                unit="",
                quantity=0.0,
                cost_per_unit=2.0,
                storage_amount=250,
                storage_unit="ml",
                organization_id=org.id
            )

            db_session.add_all([ingredient, product, container])
            db_session.commit()

            login_user(user)

            return {
                'user': user,
                'org': org,
                'tier': tier,
                'ingredient': ingredient,
                'product': product,
                'container': container
            }

    # ========== ITEM CREATION TESTS ==========

    def test_create_ingredient_with_initial_stock(self, app, db_session, setup_test_data):
        """Test creating ingredient with initial stock"""
        data = setup_test_data
        
        form_data = {
            'name': 'New Test Ingredient',
            'type': 'ingredient',
            'unit': 'kg',
            'quantity': 50.0,
            'cost_per_unit': 1.25,
            'notes': 'Initial stock test'
        }
        
        success, message, item_id = create_inventory_item(
            form_data, data['org'].id, data['user'].id
        )
        
        assert success is True
        assert item_id is not None
        
        # Verify item was created correctly
        item = InventoryItem.query.get(item_id)
        assert item.name == 'New Test Ingredient'
        assert item.quantity == 50.0
        assert item.cost_per_unit == 1.25
        
        # Verify FIFO entry was created
        history = UnifiedInventoryHistory.query.filter_by(
            inventory_item_id=item_id
        ).first()
        assert history is not None
        assert history.quantity_change == 50.0
        assert history.remaining_quantity == 50.0

    def test_create_product_zero_initial_stock(self, app, db_session, setup_test_data):
        """Test creating product with zero initial stock"""
        data = setup_test_data
        
        form_data = {
            'name': 'New Test Product',
            'type': 'product', 
            'unit': 'bottle',
            'quantity': 0.0,
            'cost_per_unit': 10.0
        }
        
        success, message, item_id = create_inventory_item(
            form_data, data['org'].id, data['user'].id
        )
        
        assert success is True
        item = InventoryItem.query.get(item_id)
        assert item.quantity == 0.0

    def test_create_container_with_storage_specs(self, app, db_session, setup_test_data):
        """Test creating container with storage specifications"""
        data = setup_test_data
        
        form_data = {
            'name': 'New Test Container',
            'type': 'container',
            'quantity': 100.0,
            'cost_per_unit': 0.75,
            'storage_amount': 500,
            'storage_unit': 'ml'
        }
        
        success, message, item_id = create_inventory_item(
            form_data, data['org'].id, data['user'].id
        )
        
        assert success is True
        item = InventoryItem.query.get(item_id)
        assert item.storage_amount == 500
        assert item.storage_unit == 'ml'

    # ========== ADDITIVE OPERATIONS TESTS ==========

    def test_restock_operation(self, app, db_session, setup_test_data):
        """Test restocking existing inventory"""
        data = setup_test_data
        item = data['ingredient']
        
        # Add initial stock
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=100.0,
            change_type='restock',
            notes='Initial restock',
            created_by=data['user'].id
        )
        assert success is True
        
        # Add more stock
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=50.0,
            change_type='restock',
            notes='Additional restock',
            created_by=data['user'].id
        )
        assert success is True
        
        db_session.refresh(item)
        assert item.quantity == 150.0
        
        # Verify FIFO structure
        lots = UnifiedInventoryHistory.query.filter(
            UnifiedInventoryHistory.inventory_item_id == item.id,
            UnifiedInventoryHistory.remaining_quantity > 0
        ).order_by(UnifiedInventoryHistory.timestamp.asc()).all()
        
        assert len(lots) == 2
        assert lots[0].remaining_quantity == 100.0
        assert lots[1].remaining_quantity == 50.0

    def test_manual_addition(self, app, db_session, setup_test_data):
        """Test manual inventory addition"""
        data = setup_test_data
        item = data['product']
        
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=25.0,
            change_type='manual_addition',
            notes='Found extra inventory',
            created_by=data['user'].id
        )
        assert success is True
        
        db_session.refresh(item)
        assert item.quantity == 25.0

    def test_finished_batch_addition(self, app, db_session, setup_test_data):
        """Test adding inventory from finished batch"""
        data = setup_test_data
        item = data['product']
        
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=48.0,
            change_type='finished_batch',
            notes='Batch #123 completed',
            created_by=data['user'].id,
            batch_id=123
        )
        assert success is True
        
        db_session.refresh(item)
        assert item.quantity == 48.0
        
        # Verify batch reference in history
        history = UnifiedInventoryHistory.query.filter_by(
            inventory_item_id=item.id,
            batch_id=123
        ).first()
        assert history is not None

    def test_returned_refunded_inventory(self, app, db_session, setup_test_data):
        """Test returned and refunded inventory operations"""
        data = setup_test_data
        item = data['product']
        
        # Test returned
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=5.0,
            change_type='returned',
            notes='Customer return',
            created_by=data['user'].id
        )
        assert success is True
        
        # Test refunded 
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=3.0,
            change_type='refunded',
            notes='Refund processed',
            created_by=data['user'].id
        )
        assert success is True
        
        db_session.refresh(item)
        assert item.quantity == 8.0

    # ========== DEDUCTIVE OPERATIONS TESTS ==========

    def test_fifo_deduction_order(self, app, db_session, setup_test_data):
        """Test FIFO (first-in-first-out) deduction order"""
        data = setup_test_data
        item = data['ingredient']
        
        # Add stock in layers with different costs
        process_inventory_adjustment(
            item_id=item.id,
            quantity=100.0,
            change_type='restock',
            cost_override=1.0,
            notes='First batch',
            created_by=data['user'].id
        )
        
        process_inventory_adjustment(
            item_id=item.id,
            quantity=50.0,
            change_type='restock', 
            cost_override=1.50,
            notes='Second batch',
            created_by=data['user'].id
        )
        
        # Deduct 75 units (should come from first batch first)
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=75.0,
            change_type='use',
            notes='FIFO test deduction',
            created_by=data['user'].id
        )
        assert success is True
        
        # Verify remaining quantities
        lots = UnifiedInventoryHistory.query.filter(
            UnifiedInventoryHistory.inventory_item_id == item.id,
            UnifiedInventoryHistory.remaining_quantity > 0
        ).order_by(UnifiedInventoryHistory.timestamp.asc()).all()
        
        assert len(lots) == 2
        assert lots[0].remaining_quantity == 25.0  # First batch partially consumed
        assert lots[1].remaining_quantity == 50.0  # Second batch untouched

    def test_batch_consumption(self, app, db_session, setup_test_data):
        """Test batch consumption deduction"""
        data = setup_test_data
        item = data['ingredient']
        
        # Add stock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=200.0,
            change_type='restock',
            created_by=data['user'].id
        )
        
        # Use for batch
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=75.0,
            change_type='batch',
            notes='Used in batch production',
            batch_id=456,
            created_by=data['user'].id
        )
        assert success is True
        
        db_session.refresh(item)
        assert item.quantity == 125.0

    def test_spoilage_tracking(self, app, db_session, setup_test_data):
        """Test spoilage and waste tracking"""
        data = setup_test_data
        item = data['ingredient']
        
        # Add stock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=100.0,
            change_type='restock',
            created_by=data['user'].id
        )
        
        # Record spoilage
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=15.0,
            change_type='spoil',
            notes='Expired ingredients',
            created_by=data['user'].id
        )
        assert success is True
        
        # Record trash
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=5.0,
            change_type='trash',
            notes='Damaged packaging',
            created_by=data['user'].id
        )
        assert success is True
        
        db_session.refresh(item)
        assert item.quantity == 80.0

    def test_sales_tracking(self, app, db_session, setup_test_data):
        """Test sales and revenue tracking"""
        data = setup_test_data
        item = data['product']
        
        # Add stock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=50.0,
            change_type='finished_batch',
            created_by=data['user'].id
        )
        
        # Record sale
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=3.0,
            change_type='sale',
            notes='Customer purchase',
            sale_price=15.0,
            customer='John Doe',
            order_id='ORD-123',
            created_by=data['user'].id
        )
        assert success is True
        
        db_session.refresh(item)
        assert item.quantity == 47.0
        
        # Verify sale data in history
        sale_history = UnifiedInventoryHistory.query.filter_by(
            inventory_item_id=item.id,
            change_type='sale'
        ).first()
        assert sale_history.sale_price == 15.0
        assert sale_history.customer == 'John Doe'
        assert sale_history.order_id == 'ORD-123'

    def test_quality_control_deductions(self, app, db_session, setup_test_data):
        """Test quality control related deductions"""
        data = setup_test_data
        item = data['product']
        
        # Add stock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=100.0,
            change_type='finished_batch',
            created_by=data['user'].id
        )
        
        # Quality fail
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=2.0,
            change_type='quality_fail',
            notes='Failed QC inspection',
            created_by=data['user'].id
        )
        assert success is True
        
        # Damaged goods
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=1.0,
            change_type='damaged',
            notes='Shipping damage',
            created_by=data['user'].id
        )
        assert success is True
        
        db_session.refresh(item)
        assert item.quantity == 97.0

    def test_sampling_and_testing(self, app, db_session, setup_test_data):
        """Test sampling and testing deductions"""
        data = setup_test_data
        item = data['product']
        
        # Add stock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=50.0,
            change_type='finished_batch',
            created_by=data['user'].id
        )
        
        # Sample
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=0.5,
            change_type='sample',
            notes='Quality sample',
            created_by=data['user'].id
        )
        assert success is True
        
        # Tester
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=1.0,
            change_type='tester',
            notes='Customer tester',
            created_by=data['user'].id
        )
        assert success is True
        
        # Gift
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=2.0,
            change_type='gift',
            notes='Promotional gift',
            created_by=data['user'].id
        )
        assert success is True
        
        db_session.refresh(item)
        assert item.quantity == 46.5

    # ========== RECOUNT OPERATIONS TESTS ==========

    def test_recount_increase(self, app, db_session, setup_test_data):
        """Test recount that increases inventory"""
        data = setup_test_data
        item = data['ingredient']
        
        # Add initial stock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=100.0,
            change_type='restock',
            created_by=data['user'].id
        )
        
        # Recount to higher amount
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=120.0,  # Target quantity, not delta
            change_type='recount',
            notes='Physical count found more',
            created_by=data['user'].id
        )
        assert success is True
        
        db_session.refresh(item)
        assert item.quantity == 120.0

    def test_recount_decrease(self, app, db_session, setup_test_data):
        """Test recount that decreases inventory"""
        data = setup_test_data
        item = data['ingredient']
        
        # Add initial stock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=100.0,
            change_type='restock',
            created_by=data['user'].id
        )
        
        # Recount to lower amount
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=85.0,  # Target quantity, not delta
            change_type='recount',
            notes='Physical count found less',
            created_by=data['user'].id
        )
        assert success is True
        
        db_session.refresh(item)
        assert item.quantity == 85.0

    def test_recount_to_zero(self, app, db_session, setup_test_data):
        """Test recount to zero inventory"""
        data = setup_test_data
        item = data['ingredient']
        
        # Add initial stock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=50.0,
            change_type='restock',
            created_by=data['user'].id
        )
        
        # Recount to zero
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=0.0,
            change_type='recount',
            notes='All inventory missing',
            created_by=data['user'].id
        )
        assert success is True
        
        db_session.refresh(item)
        assert item.quantity == 0.0

    # ========== COST MANAGEMENT TESTS ==========

    def test_cost_override(self, app, db_session, setup_test_data):
        """Test cost override functionality"""
        data = setup_test_data
        item = data['ingredient']
        
        original_cost = item.cost_per_unit
        new_cost = 2.75
        
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=0,  # No quantity change
            change_type='cost_override',
            cost_override=new_cost,
            notes='Updated supplier pricing',
            created_by=data['user'].id
        )
        assert success is True
        
        db_session.refresh(item)
        assert item.cost_per_unit == new_cost

    def test_weighted_average_cost_tracking(self, app, db_session, setup_test_data):
        """Test that different costs are tracked in FIFO lots"""
        data = setup_test_data
        item = data['ingredient']
        
        # Add stock at different costs
        process_inventory_adjustment(
            item_id=item.id,
            quantity=100.0,
            change_type='restock',
            cost_override=1.0,
            created_by=data['user'].id
        )
        
        process_inventory_adjustment(
            item_id=item.id,
            quantity=50.0,
            change_type='restock',
            cost_override=1.50,
            created_by=data['user'].id
        )
        
        # Verify costs are tracked in FIFO lots
        lots = UnifiedInventoryHistory.query.filter(
            UnifiedInventoryHistory.inventory_item_id == item.id,
            UnifiedInventoryHistory.remaining_quantity > 0
        ).order_by(UnifiedInventoryHistory.timestamp.asc()).all()
        
        assert lots[0].unit_cost == 1.0
        assert lots[1].unit_cost == 1.50

    # ========== PERISHABLE ITEMS TESTS ==========

    def test_perishable_item_expiration_tracking(self, app, db_session, setup_test_data):
        """Test expiration tracking for perishable items"""
        data = setup_test_data
        
        # Create perishable item
        form_data = {
            'name': 'Perishable Ingredient',
            'type': 'ingredient',
            'unit': 'kg',
            'quantity': 25.0,
            'cost_per_unit': 3.0,
            'is_perishable': 'on',
            'shelf_life_days': 30
        }
        
        success, message, item_id = create_inventory_item(
            form_data, data['org'].id, data['user'].id
        )
        assert success is True
        
        item = InventoryItem.query.get(item_id)
        assert item.is_perishable is True
        assert item.shelf_life_days == 30
        assert item.expiration_date is not None
        
        # Verify FIFO entry has expiration data
        history = UnifiedInventoryHistory.query.filter_by(
            inventory_item_id=item_id
        ).first()
        assert history.is_perishable is True
        assert history.shelf_life_days == 30

    def test_expired_inventory_handling(self, app, db_session, setup_test_data):
        """Test handling of expired inventory"""
        data = setup_test_data
        item = data['ingredient']
        
        # Add stock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=50.0,
            change_type='restock',
            created_by=data['user'].id
        )
        
        # Record expired inventory
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=10.0,
            change_type='expired',
            notes='Past expiration date',
            created_by=data['user'].id
        )
        assert success is True
        
        db_session.refresh(item)
        assert item.quantity == 40.0

    # ========== RESERVATION SYSTEM TESTS ==========

    def test_inventory_reservation(self, app, db_session, setup_test_data):
        """Test inventory reservation functionality"""
        data = setup_test_data
        item = data['product']
        
        # Add stock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=100.0,
            change_type='finished_batch',
            created_by=data['user'].id
        )
        
        # Reserve inventory
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=25.0,
            change_type='reserved',
            notes='Reserved for order #456',
            order_id='ORD-456',
            created_by=data['user'].id
        )
        assert success is True
        
        # Unreserve inventory
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=5.0,
            change_type='unreserved',
            notes='Partial order cancellation',
            created_by=data['user'].id
        )
        assert success is True
        
        db_session.refresh(item)
        assert item.quantity == 80.0  # 100 - 25 + 5

    # ========== DATA CONSISTENCY TESTS ==========

    def test_inventory_fifo_sync_validation(self, app, db_session, setup_test_data):
        """Test that inventory quantities stay in sync with FIFO totals"""
        data = setup_test_data
        item = data['ingredient']
        
        # Perform multiple operations
        process_inventory_adjustment(
            item_id=item.id,
            quantity=100.0,
            change_type='restock',
            created_by=data['user'].id
        )
        
        process_inventory_adjustment(
            item_id=item.id,
            quantity=25.0,
            change_type='use',
            created_by=data['user'].id
        )
        
        process_inventory_adjustment(
            item_id=item.id,
            quantity=50.0,
            change_type='restock',
            created_by=data['user'].id
        )
        
        # Validate sync
        is_valid, error, inventory_qty, fifo_total = validate_inventory_fifo_sync(item.id)
        assert is_valid is True
        assert inventory_qty == fifo_total
        assert inventory_qty == 125.0

    def test_audit_trail_completeness(self, app, db_session, setup_test_data):
        """Test that all operations create proper audit trails"""
        data = setup_test_data
        item = data['ingredient']
        
        # Perform operation
        process_inventory_adjustment(
            item_id=item.id,
            quantity=75.0,
            change_type='restock',
            notes='Audit trail test',
            created_by=data['user'].id
        )
        
        # Verify audit trail
        history_entries = UnifiedInventoryHistory.query.filter_by(
            inventory_item_id=item.id
        ).all()
        
        assert len(history_entries) > 0
        entry = history_entries[0]
        assert entry.change_type == 'restock'
        assert entry.quantity_change == 75.0
        assert entry.notes == 'Audit trail test'
        assert entry.created_by == data['user'].id
        assert entry.organization_id == data['org'].id

    # ========== ERROR HANDLING TESTS ==========

    def test_insufficient_inventory_handling(self, app, db_session, setup_test_data):
        """Test handling of insufficient inventory scenarios"""
        data = setup_test_data
        item = data['ingredient']
        
        # Add small amount of stock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=10.0,
            change_type='restock',
            created_by=data['user'].id
        )
        
        # Try to deduct more than available
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=25.0,
            change_type='use',
            notes='Should fail - insufficient stock',
            created_by=data['user'].id
        )
        assert success is False

    def test_invalid_quantity_handling(self, app, db_session, setup_test_data):
        """Test handling of invalid quantity values"""
        data = setup_test_data
        item = data['ingredient']
        
        # Try negative quantity for additive operation
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=-10.0,
            change_type='restock',
            created_by=data['user'].id
        )
        assert success is True  # Should handle gracefully

    def test_nonexistent_item_handling(self, app, db_session, setup_test_data):
        """Test handling of operations on nonexistent items"""
        data = setup_test_data
        
        success = process_inventory_adjustment(
            item_id=99999,  # Non-existent ID
            quantity=10.0,
            change_type='restock',
            created_by=data['user'].id
        )
        assert success is False

    # ========== COMPLEX SCENARIO TESTS ==========

    def test_complex_multi_operation_scenario(self, app, db_session, setup_test_data):
        """Test complex scenario with multiple operation types"""
        data = setup_test_data
        item = data['ingredient']
        
        # Initial restock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=1000.0,
            change_type='restock',
            cost_override=1.0,
            created_by=data['user'].id
        )
        
        # Use in batches
        process_inventory_adjustment(
            item_id=item.id,
            quantity=250.0,
            change_type='batch',
            batch_id=1,
            created_by=data['user'].id
        )
        
        # Record spoilage
        process_inventory_adjustment(
            item_id=item.id,
            quantity=50.0,
            change_type='spoil',
            created_by=data['user'].id
        )
        
        # Add more stock at different cost
        process_inventory_adjustment(
            item_id=item.id,
            quantity=200.0,
            change_type='restock',
            cost_override=1.25,
            created_by=data['user'].id
        )
        
        # Recount adjustment
        process_inventory_adjustment(
            item_id=item.id,
            quantity=890.0,  # Target quantity
            change_type='recount',
            created_by=data['user'].id
        )
        
        # Final validation
        db_session.refresh(item)
        is_valid, error, inventory_qty, fifo_total = validate_inventory_fifo_sync(item.id)
        assert is_valid is True
        assert inventory_qty == 890.0

    def test_high_volume_operations(self, app, db_session, setup_test_data):
        """Test system performance with high volume operations"""
        data = setup_test_data
        item = data['ingredient']
        
        # Add large initial stock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=10000.0,
            change_type='restock',
            created_by=data['user'].id
        )
        
        # Perform many small deductions
        for i in range(50):
            process_inventory_adjustment(
                item_id=item.id,
                quantity=10.0,
                change_type='use',
                notes=f'Small deduction {i+1}',
                created_by=data['user'].id
            )
        
        # Verify final state
        db_session.refresh(item)
        assert item.quantity == 9500.0
        
        # Verify FIFO integrity
        is_valid, error, inventory_qty, fifo_total = validate_inventory_fifo_sync(item.id)
        assert is_valid is True

    # ========== ITEM UPDATE TESTS ==========

    def test_item_update_with_quantity_change(self, app, db_session, setup_test_data):
        """Test updating item details with quantity changes"""
        data = setup_test_data
        item = data['ingredient']
        
        # Add initial stock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=100.0,
            change_type='restock',
            created_by=data['user'].id
        )
        
        # Update item with quantity change
        form_data = {
            'name': 'Updated Ingredient Name',
            'unit': 'kg',
            'quantity': 150.0,  # Increase quantity
            'cost_per_unit': 1.75
        }
        
        success, message = update_inventory_item(item.id, form_data)
        assert success is True
        
        db_session.refresh(item)
        assert item.name == 'Updated Ingredient Name'
        assert item.quantity == 150.0

    def test_perishable_status_change(self, app, db_session, setup_test_data):
        """Test changing perishable status of existing item"""
        data = setup_test_data
        item = data['ingredient']
        
        # Update to perishable
        form_data = {
            'name': item.name,
            'unit': item.unit,
            'quantity': item.quantity,
            'cost_per_unit': item.cost_per_unit,
            'is_perishable': 'on',
            'shelf_life_days': 60
        }
        
        success, message = update_inventory_item(item.id, form_data)
        assert success is True
        
        db_session.refresh(item)
        assert item.is_perishable is True
        assert item.shelf_life_days == 60
