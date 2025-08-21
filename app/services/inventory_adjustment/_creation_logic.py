"""
Creation logic handler - handles initial stock entries for new items.
This handler should work with the centralized quantity update system.
"""

import logging
from app.models import db, InventoryItem, IngredientCategory, Unit
from ._fifo_ops import _internal_add_fifo_entry_enhanced

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

        db.session.add(new_item)
        db.session.flush()  # Get the ID

        logger.info(f"CREATED: New inventory item {new_item.id} - {name}")
        return True, f"New inventory item '{name}' created successfully", new_item.id

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating inventory item: {str(e)}")
        return False, f"Failed to create inventory item: {str(e)}", None

def handle_initial_stock(item, quantity, change_type, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, **kwargs):
    """
    Handle the initial stock entry for a newly created item.
    This creates ONLY an InventoryLot - no duplicate history entry.
    The lot IS the inventory record.
    Returns (success, message, quantity_delta) - does NOT modify item.quantity
    """
    try:
        from app.models.inventory_lot import InventoryLot
        from app.utils.fifo_generator import generate_fifo_code
        from app.utils.timezone_utils import TimezoneUtils
        from datetime import timedelta

        logger.info(f"INITIAL_STOCK: Creating InventoryLot with {quantity} for item {item.id}")

        unit = kwargs.get('unit') or item.unit or 'count'
        final_cost = cost_override if cost_override is not None else item.cost_per_unit

        # Calculate expiration if needed
        final_expiration_date = None
        final_shelf_life_days = None

        if custom_expiration_date:
            final_expiration_date = custom_expiration_date
        elif item.is_perishable and item.shelf_life_days:
            final_expiration_date = TimezoneUtils.utc_now() + timedelta(days=item.shelf_life_days)
            final_shelf_life_days = item.shelf_life_days
        elif custom_shelf_life_days and item.is_perishable:
            final_expiration_date = TimezoneUtils.utc_now() + timedelta(days=custom_shelf_life_days)
            final_shelf_life_days = custom_shelf_life_days

        # Set shelf_life_days if item is perishable
        if item.is_perishable:
            final_shelf_life_days = final_shelf_life_days or item.shelf_life_days or custom_shelf_life_days

        fifo_code = generate_fifo_code('initial_stock', item.id)

        # Create ONLY the InventoryLot - this IS the inventory record
        lot = InventoryLot(
            inventory_item_id=item.id,
            remaining_quantity=float(quantity),  # This is the actual available inventory
            original_quantity=float(quantity),   # This is the lot's full capacity
            unit=unit,
            unit_cost=float(final_cost),
            received_date=TimezoneUtils.utc_now(),
            expiration_date=final_expiration_date,
            shelf_life_days=final_shelf_life_days,
            source_type='initial_stock',
            source_notes=notes or "Initial stock entry",
            created_by=created_by,
            fifo_code=fifo_code,
            batch_id=kwargs.get('batch_id'),
            organization_id=item.organization_id
        )

        db.session.add(lot)

        logger.info(f"INITIAL_STOCK SUCCESS: Created InventoryLot {fifo_code} with capacity {quantity} {unit}")

        # Return delta for core to apply
        quantity_delta = float(quantity)

        if quantity == 0:
            return True, f"Initial stock lot created with 0 {unit} capacity", quantity_delta
        else:
            return True, f"Initial stock lot created with {quantity} {unit} capacity", quantity_delta

    except Exception as e:
        logger.error(f"Error in initial stock operation: {str(e)}")
        db.session.rollback()
        return False, f"Initial stock failed: {str(e)}", 0