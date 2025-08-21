
"""
Advanced Inventory Scenarios Test Suite

This test suite validates complex inventory operations and edge cases:
- Complex multi-operation scenarios
- Perishable item handling
- High-volume operations
- Container and product type handling
- Unit conversion scenarios
- Batch integration
- Reservation system
- Advanced cost management

For basic operations, see test_inventory_basic_operations.py
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from flask_login import login_user
from app.models import (
    db, InventoryItem, UnifiedInventoryHistory, User, Organization, 
    SubscriptionTier
)
from app.services.inventory_adjustment import process_inventory_adjustment
# All inventory operations should go through canonical entry point:
# from app.services.inventory_adjustment import process_inventory_adjustment
# Removed direct internal imports that bypass canonical service


class TestInventoryAdvancedScenarios:
    """Advanced inventory scenarios test suite"""

    @pytest.fixture
    def setup_advanced_data(self, app, db_session):
        """Setup comprehensive test data for advanced scenarios"""
        with app.test_request_context():
            # Create tier
            tier = db_session.query(SubscriptionTier).filter_by(name="Advanced Test Tier").first()
            if not tier:
                tier = SubscriptionTier(
                    name="Advanced Test Tier",
                    tier_type="monthly",
                    user_limit=10
                )
                db_session.add(tier)
                db_session.flush()

            # Create organization
            org = db_session.query(Organization).filter_by(name="Advanced Test Org").first()
            if not org:
                org = Organization(
                    name="Advanced Test Org",
                    billing_status='active',
                    subscription_tier_id=tier.id
                )
                db_session.add(org)
                db_session.flush()

            # Create user
            user = db_session.query(User).filter_by(email="advanced@test.com").first()
            if not user:
                user = User(
                    username="advanced_test_user",
                    email="advanced@test.com",
                    organization_id=org.id
                )
                db_session.add(user)
                db_session.flush()

            # Create multiple test items
            ingredient = InventoryItem(
                name="Advanced Test Ingredient",
                type="ingredient",
                unit="g",
                quantity=0.0,
                cost_per_unit=1.50,
                organization_id=org.id
            )

            product = InventoryItem(
                name="Advanced Test Product", 
                type="product",
                unit="ml",
                quantity=0.0,
                cost_per_unit=8.0,
                organization_id=org.id
            )

            container = InventoryItem(
                name="Advanced Test Container",
                type="container",
                unit="",
                quantity=0.0,
                cost_per_unit=3.0,
                storage_amount=500,
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

    # ========== ADVANCED CREATION TESTS ==========

    def test_create_perishable_item_with_expiration(self, app, db_session, setup_advanced_data):
        """Test creating perishable item with expiration tracking"""
        data = setup_advanced_data

        form_data = {
            'name': 'Perishable Test Item',
            'type': 'ingredient',
            'unit': 'kg',
            'quantity': 25.0,
            'cost_per_unit': 4.0,
            'is_perishable': 'on',
            'shelf_life_days': 45
        }

        success, message, item_id = create_inventory_item(
            form_data, data['org'].id, data['user'].id
        )
        assert success is True

        item = InventoryItem.query.get(item_id)
        assert item.is_perishable is True
        assert item.shelf_life_days == 45
        assert item.expiration_date is not None

        # Verify FIFO entry has expiration data
        history = UnifiedInventoryHistory.query.filter_by(
            inventory_item_id=item_id
        ).first()
        assert history.is_perishable is True
        assert history.shelf_life_days == 45

    def test_create_container_with_storage_specs(self, app, db_session, setup_advanced_data):
        """Test creating container with storage specifications"""
        data = setup_advanced_data

        form_data = {
            'name': 'Advanced Test Container',
            'type': 'container',
            'quantity': 150.0,
            'cost_per_unit': 1.25,
            'storage_amount': 750,
            'storage_unit': 'ml'
        }

        success, message, item_id = create_inventory_item(
            form_data, data['org'].id, data['user'].id
        )

        assert success is True
        item = InventoryItem.query.get(item_id)
        assert item.storage_amount == 750
        assert item.storage_unit == 'ml'
        assert item.quantity == 150.0

    # ========== BATCH INTEGRATION TESTS ==========

    def test_finished_batch_addition_with_batch_tracking(self, app, db_session, setup_advanced_data):
        """Test adding inventory from finished batches with batch tracking"""
        data = setup_advanced_data
        item = data['product']

        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=96.0,
            change_type='finished_batch',
            notes='Batch #456 completed',
            batch_id=456,
            created_by=data['user'].id
        )
        assert success is True

        db_session.refresh(item)
        assert item.quantity == 96.0

        # Verify batch reference in history
        history = UnifiedInventoryHistory.query.filter_by(
            inventory_item_id=item.id,
            batch_id=456
        ).first()
        assert history is not None
        assert history.change_type == 'finished_batch'

    def test_batch_consumption_tracking(self, app, db_session, setup_advanced_data):
        """Test batch consumption with proper tracking"""
        data = setup_advanced_data
        item = data['ingredient']

        # Add stock first
        process_inventory_adjustment(
            item_id=item.id,
            quantity=200.0,
            change_type='restock',
            created_by=data['user'].id
        )

        # Use for batch production
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=75.0,
            change_type='batch',
            notes='Used in batch production',
            batch_id=789,
            created_by=data['user'].id
        )
        assert success is True

        db_session.refresh(item)
        assert item.quantity == 125.0

        # Verify batch consumption tracking
        batch_history = UnifiedInventoryHistory.query.filter_by(
            inventory_item_id=item.id,
            change_type='batch',
            batch_id=789
        ).first()
        assert batch_history is not None

    # ========== ADVANCED DEDUCTION SCENARIOS ==========

    def test_complex_sales_tracking(self, app, db_session, setup_advanced_data):
        """Test advanced sales tracking with customer and order data"""
        data = setup_advanced_data
        item = data['product']

        # Add stock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=100.0,
            change_type='finished_batch',
            created_by=data['user'].id
        )

        # Record detailed sale
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=5.0,
            change_type='sale',
            notes='Premium customer order',
            sale_price=40.0,
            customer='Jane Smith',
            order_id='ORD-789',
            created_by=data['user'].id
        )
        assert success is True

        db_session.refresh(item)
        assert item.quantity == 95.0

        # Verify detailed sale tracking
        sale_history = UnifiedInventoryHistory.query.filter_by(
            inventory_item_id=item.id,
            change_type='sale'
        ).first()
        assert sale_history.sale_price == 40.0
        assert sale_history.customer == 'Jane Smith'
        assert sale_history.order_id == 'ORD-789'

    def test_quality_control_operations(self, app, db_session, setup_advanced_data):
        """Test quality control related operations"""
        data = setup_advanced_data
        item = data['product']

        # Add stock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=120.0,
            change_type='finished_batch',
            created_by=data['user'].id
        )

        # Quality control operations
        operations = [
            ('quality_fail', 3.0, 'Failed QC inspection'),
            ('damaged', 2.0, 'Shipping damage'),
            ('sample', 0.5, 'Quality sample'),
            ('tester', 1.5, 'Customer tester'),
            ('gift', 3.0, 'Promotional gift')
        ]

        for op_type, qty, note in operations:
            success = process_inventory_adjustment(
                item_id=item.id,
                quantity=qty,
                change_type=op_type,
                notes=note,
                created_by=data['user'].id
            )
            assert success is True

        db_session.refresh(item)
        expected_remaining = 120.0 - sum(qty for _, qty, _ in operations)
        assert item.quantity == expected_remaining

    def test_expired_inventory_handling(self, app, db_session, setup_advanced_data):
        """Test handling of expired inventory"""
        data = setup_advanced_data
        item = data['ingredient']

        # Add stock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=80.0,
            change_type='restock',
            created_by=data['user'].id
        )

        # Record expired inventory
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=12.0,
            change_type='expired',
            notes='Past expiration date - removed from stock',
            created_by=data['user'].id
        )
        assert success is True

        db_session.refresh(item)
        assert item.quantity == 68.0

    # ========== RESERVATION SYSTEM TESTS ==========

    def test_inventory_reservation_system(self, app, db_session, setup_advanced_data):
        """Test inventory reservation and unreservation"""
        data = setup_advanced_data
        item = data['product']

        # Add stock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=150.0,
            change_type='finished_batch',
            created_by=data['user'].id
        )

        # Reserve inventory for order
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=30.0,
            change_type='reserved',
            notes='Reserved for order #ABC123',
            order_id='ABC123',
            created_by=data['user'].id
        )
        assert success is True

        # Partial unreservation (order changed)
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=8.0,
            change_type='unreserved',
            notes='Partial order cancellation',
            created_by=data['user'].id
        )
        assert success is True

        db_session.refresh(item)
        assert item.quantity == 128.0  # 150 - 30 + 8

        # Verify reservation tracking
        reserved_history = UnifiedInventoryHistory.query.filter_by(
            inventory_item_id=item.id,
            change_type='reserved'
        ).first()
        assert reserved_history.order_id == 'ABC123'

    # ========== WEIGHTED AVERAGE COST TESTS ==========

    def test_weighted_average_cost_tracking(self, app, db_session, setup_advanced_data):
        """Test that different costs are tracked properly in FIFO lots"""
        data = setup_advanced_data
        item = data['ingredient']

        # Add stock at different costs
        cost_batches = [
            (100.0, 1.00),
            (75.0, 1.50),
            (50.0, 2.00)
        ]

        for qty, cost in cost_batches:
            success = process_inventory_adjustment(
                item_id=item.id,
                quantity=qty,
                change_type='restock',
                cost_override=cost,
                created_by=data['user'].id
            )
            assert success is True

        # Verify costs are tracked in FIFO lots
        lots = UnifiedInventoryHistory.query.filter(
            UnifiedInventoryHistory.inventory_item_id == item.id,
            UnifiedInventoryHistory.remaining_quantity > 0
        ).order_by(UnifiedInventoryHistory.timestamp.asc()).all()

        assert len(lots) == 3
        assert lots[0].unit_cost == 1.00
        assert lots[1].unit_cost == 1.50
        assert lots[2].unit_cost == 2.00

        # Test FIFO cost deduction
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=125.0,  # Consume first lot completely + 25 from second
            change_type='use',
            created_by=data['user'].id
        )
        assert success is True

        # Verify remaining lots and costs
        remaining_lots = UnifiedInventoryHistory.query.filter(
            UnifiedInventoryHistory.inventory_item_id == item.id,
            UnifiedInventoryHistory.remaining_quantity > 0
        ).order_by(UnifiedInventoryHistory.timestamp.asc()).all()

        assert len(remaining_lots) == 2  # Second and third lots remain
        assert remaining_lots[0].remaining_quantity == 50.0  # 75 - 25
        assert remaining_lots[0].unit_cost == 1.50
        assert remaining_lots[1].remaining_quantity == 50.0
        assert remaining_lots[1].unit_cost == 2.00

    def test_cost_override_operation(self, app, db_session, setup_advanced_data):
        """Test cost override functionality"""
        data = setup_advanced_data
        item = data['ingredient']

        original_cost = item.cost_per_unit
        new_cost = 3.75

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

        # Verify cost override is tracked
        cost_history = UnifiedInventoryHistory.query.filter_by(
            inventory_item_id=item.id,
            change_type='cost_override'
        ).first()
        assert cost_history.unit_cost == new_cost

    # ========== COMPLEX MULTI-OPERATION SCENARIOS ==========

    def test_complex_multi_operation_scenario(self, app, db_session, setup_advanced_data):
        """Test complex scenario with multiple operation types"""
        data = setup_advanced_data
        item = data['ingredient']

        # Complex workflow simulation
        operations = [
            ('restock', 500.0, 1.00, 'Initial large restock'),
            ('batch', 150.0, None, 'Used in batch #001'),
            ('spoil', 25.0, None, 'Found expired stock'),
            ('restock', 100.0, 1.25, 'Emergency restock at higher cost'),
            ('use', 75.0, None, 'General production use'),
            ('recount', 340.0, None, 'Physical count adjustment'),  # Target quantity
            ('sale', 20.0, None, 'Direct sale to customer')
        ]

        for op_type, qty, cost, note in operations:
            kwargs = {
                'item_id': item.id,
                'quantity': qty,
                'change_type': op_type,
                'notes': note,
                'created_by': data['user'].id
            }
            if cost:
                kwargs['cost_override'] = cost

            success = process_inventory_adjustment(**kwargs)
            assert success is True

        # Final validation
        db_session.refresh(item)
        expected_final = 320.0  # After recount to 340, then sale of 20
        assert item.quantity == expected_final

        # Validate FIFO sync
        is_valid, error, inventory_qty, fifo_total = validate_inventory_fifo_sync(item.id)
        assert is_valid is True

    def test_high_volume_operations(self, app, db_session, setup_advanced_data):
        """Test system performance with high volume operations"""
        data = setup_advanced_data
        item = data['ingredient']

        # Add large initial stock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=5000.0,
            change_type='restock',
            created_by=data['user'].id
        )

        # Perform many small operations
        for i in range(25):
            # Alternate between different operation types
            if i % 3 == 0:
                op_type = 'use'
                qty = 20.0
            elif i % 3 == 1:
                op_type = 'batch'
                qty = 15.0
            else:
                op_type = 'spoil'
                qty = 5.0

            success = process_inventory_adjustment(
                item_id=item.id,
                quantity=qty,
                change_type=op_type,
                notes=f'High volume operation {i+1}',
                created_by=data['user'].id
            )
            assert success is True

        # Calculate expected final quantity
        # 25 operations: ~8 use (160), ~8 batch (120), ~9 spoil (45) = 325 total deducted
        expected_remaining = 5000.0 - (8*20.0 + 8*15.0 + 9*5.0)
        
        db_session.refresh(item)
        assert abs(item.quantity - expected_remaining) < 1.0  # Allow for rounding

        # Verify FIFO integrity after high volume
        is_valid, error, inventory_qty, fifo_total = validate_inventory_fifo_sync(item.id)
        assert is_valid is True

    # ========== ITEM UPDATE INTEGRATION TESTS ==========

    def test_item_update_with_quantity_recount(self, app, db_session, setup_advanced_data):
        """Test updating item details with quantity changes via recount"""
        data = setup_advanced_data
        item = data['ingredient']

        # Add initial stock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=200.0,
            change_type='restock',
            created_by=data['user'].id
        )

        # Update item with quantity change
        form_data = {
            'name': 'Updated Advanced Ingredient',
            'unit': 'kg',
            'quantity': 275.0,  # Increase quantity via recount
            'cost_per_unit': 2.25
        }

        success, message = update_inventory_item(item.id, form_data)
        assert success is True

        db_session.refresh(item)
        assert item.name == 'Updated Advanced Ingredient'
        assert item.quantity == 275.0

        # Verify recount operation was logged
        recount_history = UnifiedInventoryHistory.query.filter_by(
            inventory_item_id=item.id,
            change_type='recount'
        ).first()
        assert recount_history is not None

    def test_perishable_status_change_propagation(self, app, db_session, setup_advanced_data):
        """Test changing perishable status affects FIFO entries"""
        data = setup_advanced_data
        item = data['ingredient']

        # Add initial stock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=100.0,
            change_type='restock',
            created_by=data['user'].id
        )

        # Update to perishable with shelf life
        form_data = {
            'name': item.name,
            'unit': item.unit,
            'quantity': item.quantity,
            'cost_per_unit': item.cost_per_unit,
            'is_perishable': 'on',
            'shelf_life_days': 90
        }

        success, message = update_inventory_item(item.id, form_data)
        assert success is True

        db_session.refresh(item)
        assert item.is_perishable is True
        assert item.shelf_life_days == 90

        # Verify existing FIFO entries were updated
        fifo_entries = UnifiedInventoryHistory.query.filter(
            UnifiedInventoryHistory.inventory_item_id == item.id,
            UnifiedInventoryHistory.remaining_quantity > 0
        ).all()

        for entry in fifo_entries:
            assert entry.is_perishable is True
            assert entry.shelf_life_days == 90

    # ========== EDGE CASES AND ERROR HANDLING ==========

    def test_concurrent_transaction_simulation(self, app, db_session, setup_advanced_data):
        """Test handling of rapid sequential operations"""
        data = setup_advanced_data
        item = data['ingredient']

        # Add base stock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=1000.0,
            change_type='restock',
            created_by=data['user'].id
        )

        # Simulate rapid operations that might occur concurrently
        rapid_operations = [
            ('use', 50.0),
            ('restock', 25.0),
            ('batch', 30.0),
            ('sale', 15.0),
            ('spoil', 10.0),
            ('use', 40.0)
        ]

        for op_type, qty in rapid_operations:
            success = process_inventory_adjustment(
                item_id=item.id,
                quantity=qty,
                change_type=op_type,
                created_by=data['user'].id
            )
            assert success is True

        # Validate final state consistency
        db_session.refresh(item)
        is_valid, error, inventory_qty, fifo_total = validate_inventory_fifo_sync(item.id)
        assert is_valid is True

    def test_inventory_precision_handling(self, app, db_session, setup_advanced_data):
        """Test handling of decimal precision in inventory calculations"""
        data = setup_advanced_data
        item = data['ingredient']

        # Test with precise decimal values
        precise_operations = [
            ('restock', 100.333),
            ('use', 25.667),
            ('restock', 50.125),
            ('spoil', 10.891)
        ]

        for op_type, qty in precise_operations:
            success = process_inventory_adjustment(
                item_id=item.id,
                quantity=qty,
                change_type=op_type,
                created_by=data['user'].id
            )
            assert success is True

        # Verify precision is maintained
        db_session.refresh(item)
        expected = 100.333 - 25.667 + 50.125 - 10.891
        assert abs(item.quantity - expected) < 0.001

    def test_audit_trail_completeness_advanced(self, app, db_session, setup_advanced_data):
        """Test comprehensive audit trail for complex scenarios"""
        data = setup_advanced_data
        item = data['ingredient']

        # Perform various operations
        operations = [
            ('restock', 200.0, 'Initial stock'),
            ('batch', 50.0, 'Batch production'),
            ('recount', 140.0, 'Physical count'),  # Target quantity
            ('sale', 25.0, 'Customer order')
        ]

        for op_type, qty, note in operations:
            success = process_inventory_adjustment(
                item_id=item.id,
                quantity=qty,
                change_type=op_type,
                notes=note,
                created_by=data['user'].id
            )
            assert success is True

        # Verify complete audit trail
        all_history = UnifiedInventoryHistory.query.filter_by(
            inventory_item_id=item.id
        ).order_by(UnifiedInventoryHistory.timestamp.asc()).all()

        # Should have entries for: restock, batch, recount (meta + adjustment), sale
        assert len(all_history) >= 4

        # Verify each operation is properly documented
        operation_types = [entry.change_type for entry in all_history]
        expected_types = ['restock', 'batch', 'sale']
        for expected_type in expected_types:
            assert expected_type in operation_types

        # Verify all have proper organization scoping
        for entry in all_history:
            assert entry.organization_id == data['org'].id
            assert entry.created_by == data['user'].id
            assert entry.timestamp is not None
