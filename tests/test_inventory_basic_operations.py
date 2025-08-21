
"""
Basic Inventory Operations Test Suite

This test suite validates the core inventory adjustment operations through the
canonical inventory adjustment service. Focuses on fundamental operations:
- Item creation with initial stock
- Basic restock operations
- Simple deductions (use, sale, spoil)
- FIFO validation
- Basic recount operations

For advanced scenarios, see test_inventory_advanced_scenarios.py
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
from app.services.inventory_adjustment._validation import validate_inventory_fifo_sync
from app.services.inventory_adjustment._creation_logic import create_inventory_item


class TestInventoryBasicOperations:
    """Basic inventory operations test suite"""

    @pytest.fixture
    def setup_basic_data(self, app, db_session):
        """Setup minimal test data for basic operations"""
        with app.test_request_context():
            # Create tier
            tier = db_session.query(SubscriptionTier).filter_by(name="Basic Test Tier").first()
            if not tier:
                tier = SubscriptionTier(
                    name="Basic Test Tier",
                    tier_type="monthly",
                    user_limit=5
                )
                db_session.add(tier)
                db_session.flush()

            # Create organization
            org = db_session.query(Organization).filter_by(name="Basic Test Org").first()
            if not org:
                org = Organization(
                    name="Basic Test Org",
                    billing_status='active',
                    subscription_tier_id=tier.id
                )
                db_session.add(org)
                db_session.flush()

            # Create user
            user = db_session.query(User).filter_by(email="basic@test.com").first()
            if not user:
                user = User(
                    username="basic_test_user",
                    email="basic@test.com",
                    organization_id=org.id
                )
                db_session.add(user)
                db_session.flush()

            # Create test item
            ingredient = InventoryItem(
                name="Basic Test Ingredient",
                type="ingredient",
                unit="g",
                quantity=0.0,
                cost_per_unit=1.0,
                organization_id=org.id
            )

            db_session.add(ingredient)
            db_session.commit()

            login_user(user)

            return {
                'user': user,
                'org': org,
                'tier': tier,
                'ingredient': ingredient
            }

    # ========== ITEM CREATION TESTS ==========

    def test_create_ingredient_with_initial_stock(self, app, db_session, setup_basic_data):
        """Test creating ingredient with initial stock"""
        data = setup_basic_data

        form_data = {
            'name': 'New Basic Ingredient',
            'type': 'ingredient',
            'unit': 'kg',
            'quantity': 100.0,
            'cost_per_unit': 2.50,
            'notes': 'Basic creation test'
        }

        success, message, item_id = create_inventory_item(
            form_data, data['org'].id, data['user'].id
        )

        assert success is True
        assert item_id is not None

        # Verify item was created correctly
        item = InventoryItem.query.get(item_id)
        assert item.name == 'New Basic Ingredient'
        assert item.quantity == 100.0
        assert item.cost_per_unit == 2.50

        # Verify FIFO entry was created
        history = UnifiedInventoryHistory.query.filter_by(
            inventory_item_id=item_id
        ).first()
        assert history is not None
        assert history.quantity_change == 100.0
        assert history.remaining_quantity == 100.0
        assert history.change_type == 'initial_stock'

    def test_create_ingredient_zero_stock(self, app, db_session, setup_basic_data):
        """Test creating ingredient with zero initial stock"""
        data = setup_basic_data

        form_data = {
            'name': 'Zero Stock Ingredient',
            'type': 'ingredient',
            'unit': 'ml',
            'quantity': 0.0,
            'cost_per_unit': 5.0
        }

        success, message, item_id = create_inventory_item(
            form_data, data['org'].id, data['user'].id
        )

        assert success is True
        item = InventoryItem.query.get(item_id)
        assert item.quantity == 0.0

    # ========== BASIC RESTOCK TESTS ==========

    def test_simple_restock_operation(self, app, db_session, setup_basic_data):
        """Test basic restock operation"""
        data = setup_basic_data
        item = data['ingredient']

        # Perform restock
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=50.0,
            change_type='restock',
            notes='Basic restock test',
            created_by=data['user'].id
        )
        assert success is True

        # Verify quantity updated
        db_session.refresh(item)
        assert item.quantity == 50.0

        # Verify FIFO entry
        history = UnifiedInventoryHistory.query.filter_by(
            inventory_item_id=item.id,
            change_type='restock'
        ).first()
        assert history is not None
        assert history.quantity_change == 50.0
        assert history.remaining_quantity == 50.0

    def test_multiple_restock_operations(self, app, db_session, setup_basic_data):
        """Test multiple restock operations build up inventory"""
        data = setup_basic_data
        item = data['ingredient']

        # First restock
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=30.0,
            change_type='restock',
            created_by=data['user'].id
        )
        assert success is True

        # Second restock
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=20.0,
            change_type='restock',
            created_by=data['user'].id
        )
        assert success is True

        # Verify total quantity
        db_session.refresh(item)
        assert item.quantity == 50.0

        # Verify two separate FIFO lots
        lots = UnifiedInventoryHistory.query.filter(
            UnifiedInventoryHistory.inventory_item_id == item.id,
            UnifiedInventoryHistory.remaining_quantity > 0
        ).order_by(UnifiedInventoryHistory.timestamp.asc()).all()

        assert len(lots) == 2
        assert lots[0].remaining_quantity == 30.0
        assert lots[1].remaining_quantity == 20.0

    # ========== BASIC DEDUCTION TESTS ==========

    def test_simple_use_deduction(self, app, db_session, setup_basic_data):
        """Test basic 'use' deduction"""
        data = setup_basic_data
        item = data['ingredient']

        # Add stock first
        process_inventory_adjustment(
            item_id=item.id,
            quantity=100.0,
            change_type='restock',
            created_by=data['user'].id
        )

        # Use some inventory
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=25.0,
            change_type='use',
            notes='Basic use test',
            created_by=data['user'].id
        )
        assert success is True

        # Verify quantity reduced
        db_session.refresh(item)
        assert item.quantity == 75.0

        # Verify FIFO lot was reduced
        remaining_lot = UnifiedInventoryHistory.query.filter(
            UnifiedInventoryHistory.inventory_item_id == item.id,
            UnifiedInventoryHistory.remaining_quantity > 0
        ).first()
        assert remaining_lot.remaining_quantity == 75.0

    def test_sale_deduction(self, app, db_session, setup_basic_data):
        """Test basic sale deduction"""
        data = setup_basic_data
        item = data['ingredient']

        # Add stock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=50.0,
            change_type='restock',
            created_by=data['user'].id
        )

        # Record sale
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=10.0,
            change_type='sale',
            notes='Basic sale',
            sale_price=25.0,
            created_by=data['user'].id
        )
        assert success is True

        # Verify quantity and sale data
        db_session.refresh(item)
        assert item.quantity == 40.0

        sale_history = UnifiedInventoryHistory.query.filter_by(
            inventory_item_id=item.id,
            change_type='sale'
        ).first()
        assert sale_history.sale_price == 25.0

    def test_spoilage_deduction(self, app, db_session, setup_basic_data):
        """Test basic spoilage deduction"""
        data = setup_basic_data
        item = data['ingredient']

        # Add stock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=80.0,
            change_type='restock',
            created_by=data['user'].id
        )

        # Record spoilage
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=15.0,
            change_type='spoil',
            notes='Expired inventory',
            created_by=data['user'].id
        )
        assert success is True

        db_session.refresh(item)
        assert item.quantity == 65.0

    # ========== FIFO VALIDATION TESTS ==========

    def test_fifo_deduction_order(self, app, db_session, setup_basic_data):
        """Test that deductions follow FIFO (first-in-first-out) order"""
        data = setup_basic_data
        item = data['ingredient']

        # Add stock in two batches at different times
        process_inventory_adjustment(
            item_id=item.id,
            quantity=60.0,
            change_type='restock',
            notes='First batch',
            created_by=data['user'].id
        )

        # Small delay to ensure different timestamps
        import time
        time.sleep(0.01)

        process_inventory_adjustment(
            item_id=item.id,
            quantity=40.0,
            change_type='restock',
            notes='Second batch',
            created_by=data['user'].id
        )

        # Use 70 units (should consume first batch completely + 10 from second)
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=70.0,
            change_type='use',
            notes='FIFO test',
            created_by=data['user'].id
        )
        assert success is True

        # Verify remaining inventory
        db_session.refresh(item)
        assert item.quantity == 30.0

        # Verify FIFO structure - first batch should be gone, second batch partially consumed
        remaining_lots = UnifiedInventoryHistory.query.filter(
            UnifiedInventoryHistory.inventory_item_id == item.id,
            UnifiedInventoryHistory.remaining_quantity > 0
        ).order_by(UnifiedInventoryHistory.timestamp.asc()).all()

        assert len(remaining_lots) == 1  # Only second batch remains
        assert remaining_lots[0].remaining_quantity == 30.0  # 40 - 10 consumed

    def test_inventory_fifo_sync_validation(self, app, db_session, setup_basic_data):
        """Test that inventory quantities stay in sync with FIFO totals"""
        data = setup_basic_data
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
            quantity=30.0,
            change_type='use',
            created_by=data['user'].id
        )

        process_inventory_adjustment(
            item_id=item.id,
            quantity=25.0,
            change_type='restock',
            created_by=data['user'].id
        )

        # Validate sync
        is_valid, error, inventory_qty, fifo_total = validate_inventory_fifo_sync(item.id)
        assert is_valid is True
        assert inventory_qty == fifo_total
        assert inventory_qty == 95.0  # 100 - 30 + 25

    # ========== BASIC RECOUNT TESTS ==========

    def test_recount_increase(self, app, db_session, setup_basic_data):
        """Test recount that increases inventory"""
        data = setup_basic_data
        item = data['ingredient']

        # Add initial stock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=50.0,
            change_type='restock',
            created_by=data['user'].id
        )

        # Recount to higher amount
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=75.0,  # Target quantity
            change_type='recount',
            notes='Found more during count',
            created_by=data['user'].id
        )
        assert success is True

        db_session.refresh(item)
        assert item.quantity == 75.0

    def test_recount_decrease(self, app, db_session, setup_basic_data):
        """Test recount that decreases inventory"""
        data = setup_basic_data
        item = data['ingredient']

        # Add initial stock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=80.0,
            change_type='restock',
            created_by=data['user'].id
        )

        # Recount to lower amount
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=65.0,  # Target quantity
            change_type='recount',
            notes='Some missing during count',
            created_by=data['user'].id
        )
        assert success is True

        db_session.refresh(item)
        assert item.quantity == 65.0

    # ========== ERROR HANDLING TESTS ==========

    def test_insufficient_inventory_protection(self, app, db_session, setup_basic_data):
        """Test protection against overdraft (insufficient inventory)"""
        data = setup_basic_data
        item = data['ingredient']

        # Add small amount of stock
        process_inventory_adjustment(
            item_id=item.id,
            quantity=20.0,
            change_type='restock',
            created_by=data['user'].id
        )

        # Try to deduct more than available
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=30.0,  # More than the 20 available
            change_type='sale',
            created_by=data['user'].id
        )

        # Should fail
        assert success is False

        # Verify quantity unchanged
        db_session.refresh(item)
        assert item.quantity == 20.0

    def test_nonexistent_item_handling(self, app, db_session, setup_basic_data):
        """Test handling of operations on nonexistent items"""
        data = setup_basic_data

        success = process_inventory_adjustment(
            item_id=99999,  # Non-existent ID
            quantity=10.0,
            change_type='restock',
            created_by=data['user'].id
        )
        assert success is False

    # ========== PARAMETERIZED BASIC OPERATIONS ==========

    @pytest.mark.parametrize("change_type,adjustment_qty", [
        ("restock", 50.0),
        ("manual_addition", 25.0),
        ("returned", 15.0),
        ("use", 30.0),
        ("sale", 20.0),
        ("spoil", 10.0),
    ])
    def test_basic_adjustment_types(self, app, db_session, setup_basic_data, change_type, adjustment_qty):
        """Parameterized test for basic adjustment types"""
        data = setup_basic_data
        item = data['ingredient']

        # Add initial stock for deductive operations
        if change_type in ['use', 'sale', 'spoil']:
            process_inventory_adjustment(
                item_id=item.id,
                quantity=100.0,
                change_type='restock',
                created_by=data['user'].id
            )

        # Perform the adjustment
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=adjustment_qty,
            change_type=change_type,
            notes=f'Basic {change_type} test',
            created_by=data['user'].id
        )

        # All basic operations should succeed
        assert success is True

        # Verify history entry was created
        history = UnifiedInventoryHistory.query.filter_by(
            inventory_item_id=item.id,
            change_type=change_type
        ).first()
        assert history is not None
        assert history.quantity_change == adjustment_qty

    def test_audit_trail_completeness(self, app, db_session, setup_basic_data):
        """Test that operations create proper audit trails"""
        data = setup_basic_data
        item = data['ingredient']

        # Perform operation
        process_inventory_adjustment(
            item_id=item.id,
            quantity=45.0,
            change_type='restock',
            notes='Audit trail test',
            created_by=data['user'].id
        )

        # Verify audit trail
        history = UnifiedInventoryHistory.query.filter_by(
            inventory_item_id=item.id
        ).first()

        assert history.change_type == 'restock'
        assert history.quantity_change == 45.0
        assert history.notes == 'Audit trail test'
        assert history.created_by == data['user'].id
        assert history.organization_id == data['org'].id
        assert history.timestamp is not None

    def test_cost_tracking_basic(self, app, db_session, setup_basic_data):
        """Test basic cost tracking in FIFO entries"""
        data = setup_basic_data
        item = data['ingredient']

        # Add stock with specific cost
        success = process_inventory_adjustment(
            item_id=item.id,
            quantity=50.0,
            change_type='restock',
            cost_override=2.50,
            created_by=data['user'].id
        )
        assert success is True

        # Verify cost is tracked in FIFO entry
        history = UnifiedInventoryHistory.query.filter_by(
            inventory_item_id=item.id,
            change_type='restock'
        ).first()
        assert history.unit_cost == 2.50
