"""
Creation logic handler - handles initial stock entries for new items.
This handler should work with the centralized quantity update system.
"""

import logging
from app.models import db, InventoryItem, IngredientCategory, Unit, UnifiedInventoryHistory
from ._fifo_ops import create_new_fifo_lot

logger = logging.getLogger(__name__)

def create_inventory_item(form_data, organization_id, created_by):
    """
    Create a new inventory item from form data.
    Returns (success, message, item_id)
    """
    try:
        logger.info(f"CREATE INVENTORY ITEM: Organization {organization_id}, User {created_by}")
        logger.info(f"Form data: {dict(form_data)}")

        # Extract and validate required fields
        name = form_data.get('name', '').strip()
        if not name:
            return False, "Item name is required", None

        item_type = form_data.get('type', 'ingredient')

        # Handle unit - get from form or default
        unit_input = form_data.get('unit', '').strip()
        if unit_input:
            # Try to find existing unit or create/validate
            unit = db.session.query(Unit).filter_by(name=unit_input).first()
            if not unit:
                # Create new unit if it doesn't exist
                unit = Unit(name=unit_input, symbol=unit_input)
                db.session.add(unit)
                db.session.flush()
            final_unit = unit.name
        else:
            final_unit = 'count'  # Default unit

        # Handle category
        category_id = None
        category_name = form_data.get('category')
        if category_name:
            category = db.session.query(IngredientCategory).filter_by(name=category_name).first()
            if category:
                category_id = category.id

        # Extract numeric fields with defaults
        cost_per_unit = 0.0
        try:
            cost_input = form_data.get('cost_per_unit')
            if cost_input:
                cost_per_unit = float(cost_input)
        except (ValueError, TypeError):
            pass

        shelf_life_days = None
        try:
            shelf_life_input = form_data.get('shelf_life_days')
            if shelf_life_input:
                shelf_life_days = int(shelf_life_input)
        except (ValueError, TypeError):
            pass

        # Determine if item is perishable
        is_perishable = bool(shelf_life_days) or form_data.get('is_perishable') == 'on'

        # Create the new inventory item with quantity = 0
        # The initial stock will be added via process_inventory_adjustment
        new_item = InventoryItem(
            name=name,
            type=item_type,
            quantity=0.0,  # Start with 0, will be set by initial stock adjustment
            unit=final_unit,
            cost_per_unit=cost_per_unit,
            is_perishable=is_perishable,
            shelf_life_days=shelf_life_days,
            organization_id=organization_id,
            category_id=category_id
        )

        # Save the new item
        db.session.add(new_item)
        db.session.flush()  # Get the ID without committing

        logger.info(f"CREATED: New inventory item {new_item.id} - {new_item.name}")

        # Handle initial stock if quantity > 0
        if initial_quantity > 0:
            # Use the central inventory adjustment service for initial stock
            success, adjustment_message = process_inventory_adjustment(
                item_id=new_item.id,
                quantity=initial_quantity,
                change_type='initial',
                notes='Initial inventory entry',
                created_by=created_by,
                custom_expiration_date=custom_expiration_date,
                custom_shelf_life_days=custom_shelf_life_days
            )

            if not success:
                db.session.rollback()
                return False, f"Item created but initial stock failed: {adjustment_message}", None

        # Commit the transaction
        db.session.commit()

        # Double-check the item was created
        created_item = InventoryItem.query.get(new_item.id)
        if not created_item:
            logger.error(f"Item {new_item.id} not found after creation")
            return False, "Item creation failed - not found after commit", None

        return True, f"Created {new_item.name}", new_item.id

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating inventory item: {str(e)}")
        return False, f"Failed to create inventory item: {str(e)}", None

def handle_initial_stock(item, quantity, change_type, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, **kwargs):
    """
    Handle the initial stock entry for a newly created item.
    This is called when an item gets its very first inventory.
    Works just like any other lot creation - can be 0 or any positive value.
    Returns (success, message, quantity_delta) - does NOT modify item.quantity
    """
    try:
        logger.info(f"INITIAL_STOCK: Adding {quantity} to new item {item.id}")

        unit = kwargs.get('unit') or item.unit or 'count'
        final_cost = cost_override if cost_override is not None else item.cost_per_unit

        # Create the initial FIFO entry - works for any quantity including 0
        success, message, lot_id = create_new_fifo_lot(
            item_id=item.id,
            quantity=quantity,
            change_type='initial_stock',
            unit=unit,
            notes=notes or "Initial stock entry",
            cost_per_unit=final_cost,
            created_by=created_by,
            custom_expiration_date=custom_expiration_date,
            custom_shelf_life_days=custom_shelf_life_days
        )

        if not success:
            return False, f"Failed to create initial stock entry: {message}", 0

        # The create_new_fifo_lot already created the history record
        # No need to create a duplicate here

        # Return delta for core to apply - works for 0 quantity too
        quantity_delta = float(quantity)
        logger.info(f"INITIAL_STOCK SUCCESS: Will set item {item.id} quantity to {quantity}")

        if quantity == 0:
            return True, f"Initial stock entry created with 0 {unit}", quantity_delta
        else:
            return True, f"Initial stock of {quantity} {unit} added", quantity_delta

    except Exception as e:
        logger.error(f"Error in initial stock operation: {str(e)}")
        return False, f"Initial stock failed: {str(e)}", 0