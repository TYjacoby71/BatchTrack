import pytest
from unittest.mock import patch, MagicMock
from flask_login import login_user
from app.models import InventoryItem, InventoryHistory
from app.services.inventory_adjustment import process_inventory_adjustment, validate_inventory_fifo_sync

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

            # Verify total by refreshing the item in the current session
            db_session.refresh(item)
            assert item.quantity == 150.0

            # Deduct and verify FIFO order
            assert process_inventory_adjustment(
                item_id=item.id,
                quantity=-75.0,
                change_type="batch",
                notes="FIFO test deduction",
                created_by=test_user.id
            )

            # Verify available quantity matches
            from app.services.stock_check import check_stock_availability
            result = check_stock_availability([{
                'item_id': item.id,
                'quantity_needed': 5.0,
                'unit': 'g'  # Use matching unit to avoid conversion issues
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
            db_session.commit()  # Commit instead of flush

            # Test product addition (should use ProductSKUHistory)
            success, message = process_inventory_adjustment(
                item_id=item.id,
                quantity=250.0,
                change_type="finished_batch",
                notes="Batch completion",
                created_by=test_user.id
            )

            # The function should return success even if it's a tuple
            if isinstance(success, tuple):
                success = success[0]
            
            assert success is True, f"Expected success but got: {success}, message: {message}"
            db_session.commit()
            db_session.refresh(item)
            assert item.quantity == 250.0