import logging
from app.models import db, InventoryItem
from ._fifo_ops import _internal_add_fifo_entry_enhanced

logger = logging.getLogger(__name__)

def handle_initial_stock(item, quantity, change_type, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, customer=None, sale_price=None, order_id=None, target_quantity=None, unit=None, **kwargs):
    """
    Handle initial stock creation for new inventory items.

    This is called when the first inventory entry is made for an item.
    It creates the initial FIFO lot and sets the item's quantity.
    """
    try:
        logger.info(f"INITIAL STOCK: Creating first entry for item {item.id} with {quantity} units")

        # Use provided cost or item's default cost
        cost_per_unit = cost_override if cost_override is not None else (item.cost_per_unit or 0.0)

        # Create the initial FIFO entry
        success, error = _internal_add_fifo_entry_enhanced(
            item_id=item.id,
            quantity=quantity,
            change_type=change_type,  # Use the original change_type for history
            unit=unit or item.unit or 'count',
            notes=notes or f"Initial stock entry: {change_type}",
            cost_per_unit=cost_per_unit,
            created_by=created_by,
            custom_expiration_date=custom_expiration_date,
            custom_shelf_life_days=custom_shelf_life_days
        )

        if success:
            # Set the item's quantity to match the FIFO entry
            from app.models import db
            item.quantity = float(quantity)
            db.session.add(item)

            message = f"Initial stock: {quantity} {unit or item.unit or 'units'} added"
            logger.info(f"INITIAL STOCK SUCCESS: {message} for item {item.id}")
            return True, message
        else:
            logger.error(f"INITIAL STOCK FAILED: {error} for item {item.id}")
            return False, error

    except Exception as e:
        logger.error(f"INITIAL STOCK ERROR: {str(e)} for item {item.id}")
        return False, str(e)

def create_inventory_item(form_data, organization_id, created_by):
    """
    Creates a new inventory item and optionally adds initial stock.
    This function should NOT call process_inventory_adjustment to avoid circular dependencies.
    """
    try:
        # Extract form data
        name = form_data.get('name', '').strip()
        if not name:
            return False, "Item name is required.", None

        category_id = form_data.get('category_id')
        unit = form_data.get('unit', 'count')
        cost_per_unit = float(form_data.get('cost_per_unit', 0.0))
        low_stock_threshold = float(form_data.get('low_stock_threshold', 0.0))
        item_type = form_data.get('type', 'ingredient')

        # Perishable fields
        is_perishable = form_data.get('is_perishable', False)
        shelf_life_days = None
        if is_perishable:
            shelf_life_days = form_data.get('shelf_life_days')
            if shelf_life_days:
                shelf_life_days = int(shelf_life_days)

        # Create the item (without initial quantity)
        item = InventoryItem(
            name=name,
            category_id=category_id if category_id else None,
            quantity=0.0,  # Start with 0, we'll add stock separately
            unit=unit,
            cost_per_unit=cost_per_unit,
            low_stock_threshold=low_stock_threshold,
            type=item_type,
            is_perishable=is_perishable,
            shelf_life_days=shelf_life_days,
            organization_id=organization_id,
            created_by=created_by
        )

        db.session.add(item)
        db.session.flush()  # Get the ID without committing

        # Add initial stock if provided
        initial_quantity = form_data.get('quantity')
        if initial_quantity and float(initial_quantity) > 0:
            quantity = float(initial_quantity)

            # Call the initial stock handler directly (not through dispatcher)
            success, message = handle_initial_stock(
                item=item,
                quantity=quantity,
                change_type='initial_stock',
                notes=f'Initial stock entry: {quantity}',
                created_by=created_by,
                cost_override=cost_per_unit, # Pass cost_per_unit as cost_override
                unit=unit # Pass unit to the handler
            )

            if not success:
                db.session.rollback()
                return False, f"Failed to add initial stock: {message}", None

        db.session.commit()
        logger.info(f"Created inventory item {item.id} with initial stock {initial_quantity or 0}")

        return True, "Item created successfully.", item.id

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating inventory item: {e}", exc_info=True)
        return False, f"Failed to create item: {str(e)}", None