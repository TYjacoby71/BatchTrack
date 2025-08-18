import logging
from datetime import datetime, timedelta
from app.models import db, InventoryItem
from ._core import process_inventory_adjustment
from ._audit import record_audit_entry


def handle_initial_stock(item, quantity, change_type, unit=None, notes=None, created_by=None,
                        cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, **kwargs):
    """
    Handles initial stock entry for items with no FIFO history.
    This delegates ALL FIFO operations to the FIFO service - no direct lot creation.
    """
    try:
        from ._fifo_ops import _internal_add_fifo_entry_enhanced

        final_unit = unit or getattr(item, 'unit', 'count')
        final_notes = notes or 'Initial stock entry'

        if quantity == 0:
            # Create a "priming" entry with zero quantity to establish FIFO history
            success, error = _internal_add_fifo_entry_enhanced(
                item_id=item.id,
                quantity=0.01,  # Minimal priming amount
                change_type='initial_stock',
                unit=final_unit,
                notes='FIFO history priming entry',
                cost_per_unit=cost_override or item.cost_per_unit,
                created_by=created_by,
                **kwargs
            )

            if success:
                # Immediately deduct the priming amount to get back to zero
                from ._fifo_ops import _calculate_deduction_plan_internal, _execute_deduction_plan_internal
                plan, _ = _calculate_deduction_plan_internal(item.id, 0.01, 'initial_stock_adjustment')
                if plan:
                    _execute_deduction_plan_internal(plan, item.id)

            record_audit_entry(
                item_id=item.id,
                change_type='initial_stock',
                notes='Item created with zero initial stock',
                created_by=created_by
            )
            return True, "Item initialized with zero stock"

        # For non-zero quantities, delegate to FIFO service
        cost_per_unit = cost_override if cost_override is not None else item.cost_per_unit

        success, error = _internal_add_fifo_entry_enhanced(
            item_id=item.id,
            quantity=quantity,
            change_type='initial_stock',
            unit=final_unit,
            notes=final_notes,
            cost_per_unit=cost_per_unit,
            created_by=created_by,
            expiration_date=custom_expiration_date,
            shelf_life_days=custom_shelf_life_days,
            **kwargs
        )

        if not success:
            return False, f"Failed to create initial stock: {error}"

        record_audit_entry(
            item_id=item.id,
            change_type='initial_stock',
            notes=f'Initial stock: {quantity} {final_unit}',
            created_by=created_by
        )

        return True, f"Initial stock added: {quantity} {final_unit}"

    except Exception as e:
        return False, f"Error in initial stock creation: {str(e)}"


logger = logging.getLogger(__name__)

def create_inventory_item(form_data: dict, organization_id: int, created_by: int) -> tuple[bool, str, int]:
    """
    Canonical service for creating new inventory items.

    Returns:
        tuple: (success: bool, message: str, item_id: int)
    """
    try:
        # Extract and validate form data
        name = form_data.get('name', '').strip()
        if not name:
            return False, "Item name is required", None

        # Check for duplicate name
        existing_item = InventoryItem.query.filter_by(
            name=name,
            organization_id=organization_id
        ).first()
        if existing_item:
            return False, f'An item with the name "{name}" already exists. Please choose a different name.', None

        # Parse form data
        quantity = float(form_data.get('quantity', 0))
        unit = form_data.get('unit', '')
        item_type = form_data.get('type', 'ingredient')

        # Handle cost calculation
        cost_entry_type = form_data.get('cost_entry_type', 'per_unit')
        cost_input = float(form_data.get('cost_per_unit', 0))

        if cost_entry_type == 'total' and quantity > 0:
            cost_per_unit = cost_input / quantity
        else:
            cost_per_unit = cost_input

        low_stock_threshold = float(form_data.get('low_stock_threshold', 0))
        is_perishable = form_data.get('is_perishable') == 'on'

        # Handle expiration
        expiration_date = None
        shelf_life_days = None
        if is_perishable:
            shelf_life_days = int(form_data.get('shelf_life_days', 0))
            if shelf_life_days > 0:
                expiration_date = datetime.utcnow().date() + timedelta(days=shelf_life_days)

        # Handle container-specific fields
        storage_amount = None
        storage_unit = None
        history_unit = unit

        if item_type == 'container':
            storage_amount = float(form_data.get('storage_amount', 0))
            storage_unit = form_data.get('storage_unit', '')
            unit = ''  # Containers don't have a unit on the item itself
            history_unit = 'count'  # But history entries use 'count'
        elif item_type == 'product':
            history_unit = unit if unit else 'count'

        # Create the inventory item
        item = InventoryItem(
            name=name,
            quantity=0,  # Start at 0, will be updated by adjustment service
            unit=unit,
            type=item_type,
            cost_per_unit=cost_per_unit,
            low_stock_threshold=low_stock_threshold,
            is_perishable=is_perishable,
            shelf_life_days=shelf_life_days,
            expiration_date=expiration_date,
            storage_amount=storage_amount,
            storage_unit=storage_unit,
            organization_id=organization_id
        )

        db.session.add(item)
        db.session.flush()  # Get the ID without committing

        # Always create initial stock entry to prime FIFO history
        notes = form_data.get('notes', '') or 'Initial stock creation'

        # Use handle_initial_stock for first-time setup (handles both zero and non-zero)
        success, message = handle_initial_stock(
            item=item,
            quantity=quantity,
            change_type='initial_stock',
            unit=history_unit,
            notes=notes,
            created_by=created_by,
            cost_override=cost_per_unit,
            custom_expiration_date=expiration_date,
            custom_shelf_life_days=shelf_life_days
        )

        if not success:
            db.session.rollback()
            return False, f'Error creating inventory item: {message}', None

        db.session.commit()
        record_audit_entry(item.id, 'item_created', f'Created item: {name}')

        return True, 'Inventory item added successfully', item.id

    except ValueError as e:
        logger.error(f"ValueError in create_inventory_item: {str(e)}")
        db.session.rollback()
        return False, f'Invalid input values: {str(e)}', None

    except Exception as e:
        logger.error(f"Unexpected error in create_inventory_item: {str(e)}")
        db.session.rollback()
        return False, f'Error adding inventory item: {str(e)}', None