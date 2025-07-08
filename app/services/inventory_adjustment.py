from flask import current_app
from flask_login import current_user
from app.models import db, InventoryItem, InventoryHistory
from datetime import datetime, timedelta
from app.services.conversion_wrapper import safe_convert
from app.services.unit_conversion import ConversionEngine
from app.blueprints.fifo.services import FIFOService

def validate_inventory_fifo_sync(item_id, item_type=None):
    """
    Validates that inventory quantity matches sum of ALL FIFO remaining quantities (including frozen expired)
    For products: validates that available + reserved + expired = inventory total
    Returns: (is_valid, error_message, inventory_qty, fifo_total)
    """
    # Handle different item types
    if item_type == 'product':
        from app.models.product import ProductSKU, ProductSKUHistory
        # For products, item_id should be inventory_item_id
        item = InventoryItem.query.get(item_id)
        if not item or item.type != 'product':
            return False, "Product inventory item not found", 0, 0

        # Find the SKU that uses this inventory item
        sku = ProductSKU.query.filter_by(inventory_item_id=item_id).first()
        if not sku:
            return False, "Product SKU not found for inventory item", 0, 0

        # Get ALL FIFO entries with remaining quantity (including frozen expired ones)
        from sqlalchemy import and_
        all_fifo_entries = ProductSKUHistory.query.filter(
            and_(
                ProductSKUHistory.inventory_item_id == item_id,
                ProductSKUHistory.remaining_quantity > 0,
                ProductSKUHistory.organization_id == current_user.organization_id if current_user and current_user.is_authenticated else None
            )
        ).all()

        fifo_total = sum(entry.remaining_quantity for entry in all_fifo_entries)
        current_qty = item.quantity
        item_name = item.name

        # For products, check if inventory = available + reserved + expired
        # This accounts for reservations that reduce FIFO remaining quantities
        available_qty = item.available_quantity_for_sale
        reserved_qty = item.reserved_quantity
        expired_qty = item.expired_quantity if item.is_perishable else 0

        expected_total = available_qty + reserved_qty + expired_qty

        # Allow small floating point differences (0.001)
        if abs(current_qty - expected_total) > 0.001:
            error_msg = f"SYNC ERROR: {item_name} inventory ({current_qty}) != available ({available_qty}) + reserved ({reserved_qty}) + expired ({expired_qty}) = {expected_total}"
            return False, error_msg, current_qty, expected_total

        return True, "", current_qty, expected_total
    else:
        item = InventoryItem.query.get(item_id)
        if not item:
            return False, "Item not found", 0, 0

        # Use FIFO service to get all entries
        all_fifo_entries = FIFOService.get_all_fifo_entries(item_id)
        fifo_total = sum(entry.remaining_quantity for entry in all_fifo_entries)
        current_qty = item.quantity
        item_name = item.name

        # Allow small floating point differences (0.001)
        if abs(current_qty - fifo_total) > 0.001:
            error_msg = f"SYNC ERROR: {item_name} inventory ({current_qty}) != FIFO total ({fifo_total}) [includes frozen expired]"
            return False, error_msg, current_qty, fifo_total

        return True, "", current_qty, fifo_total

def process_inventory_adjustment(item_id, quantity, change_type, unit=None, notes=None, 
                                 created_by=None, batch_id=None, cost_override=None,
                                 custom_expiration_date=None, custom_shelf_life_days=None,
                                 item_type='ingredient', customer=None, sale_price=None, order_id=None):
    """
    Centralized inventory adjustment service that handles both ingredients and products
    with proper FIFO tracking and expiration management
    """
    try:
        # Get the item - treat item_id as inventory_item_id for unified handling
        item = InventoryItem.query.get(item_id)

        if not item:
            raise ValueError(f"Inventory item not found for ID: {item_id}")

        # Organization scoping check
        if current_user and current_user.is_authenticated:
            if item.organization_id != current_user.organization_id:
                raise ValueError("Access denied: Item does not belong to your organization")

        # Convert units if needed (except for containers and products)
        if item_type != 'product' and getattr(item, 'type', None) != 'container' and unit != item.unit:
            conversion = safe_convert(quantity, unit, item.unit, ingredient_id=item.id)
            if not conversion['ok']:
                raise ValueError(conversion['error'])
            quantity = conversion['result']['converted_value']

        # Determine quantity change and special handling
        current_quantity = item.quantity

        if change_type == 'recount':
            qty_change = quantity - current_quantity
        elif change_type in ['spoil', 'trash', 'sold', 'sale', 'gift', 'sample', 'tester', 'quality_fail', 'expired_disposal', 'damaged', 'expired']:
            qty_change = -abs(quantity)
        elif change_type == 'reserved':
            # Reserve inventory - reduce available but keep total inventory
            # This creates reservation entries and deducts from FIFO
            success, deduction_plan, available_qty = FIFOService.calculate_deduction_plan(
                item_id, quantity, change_type
            )

            if not success:
                raise ValueError(f"Insufficient available inventory for reservation. Available: {available_qty}, Requested: {quantity}")

            # Execute FIFO deduction (reduces remaining_quantity on FIFO entries)
            FIFOService.execute_deduction_plan(deduction_plan, item_id)

            # Create deduction history entries
            FIFOService.create_deduction_history(
                item_id, deduction_plan, change_type, notes, 
                created_by=created_by, customer=customer, 
                sale_price=sale_price, order_id=order_id
            )

            # Create reservation allocation entry to track what was reserved
            FIFOService.add_fifo_entry(
                inventory_item_id=item_id,
                quantity=0,  # Don't change total inventory for reservations
                change_type='reserved_allocation',
                unit=unit,
                notes=f"Reserved for order {order_id}" if order_id else "Reserved inventory",
                created_by=created_by,
                order_id=order_id
            )

            # Reserved quantity is calculated dynamically from FIFO entries
            # DO NOT change item.quantity for reservations!
            qty_change = 0  # No change to total inventory for reservations
        elif change_type == 'returned':
            qty_change = quantity
        elif change_type == 'unreserved':
            current_app.logger.info("=== UNRESERVED (RELEASE RESERVATION) ===")

            # Check current reserved quantity before releasing
            item = InventoryItem.query.get(item_id)
            if not item:
                current_app.logger.error(f"Item not found: {item_id}")
                return False

            current_reserved = item.reserved_quantity
            current_app.logger.info(f"Current reserved quantity: {current_reserved}")
            current_app.logger.info(f"Attempting to release: {quantity}")

            if quantity > current_reserved:
                current_app.logger.error(f"Cannot release {quantity} - only {current_reserved} reserved")
                raise ValueError(f"Cannot release {quantity} units. Only {current_reserved} units are currently reserved.")

            # For unreserving, we need to restore the quantity to FIFO entries
            success = FIFOService.release_reservation(
                inventory_item_id=item_id,
                quantity=quantity,
                notes=notes,
                order_id=order_id
            )
        else:
            qty_change = quantity

        # Handle expiration using ExpirationService
        from app.blueprints.expiration.services import ExpirationService

        expiration_date = None
        shelf_life_to_use = None

        if custom_expiration_date:
            expiration_date = custom_expiration_date
            shelf_life_to_use = custom_shelf_life_days
        elif change_type == 'restock' and item.is_perishable and item.shelf_life_days:
            expiration_date = ExpirationService.calculate_expiration_date(
                datetime.utcnow(), item.shelf_life_days
            )
            shelf_life_to_use = item.shelf_life_days

        # Handle cost calculations
        if change_type in ['spoil', 'trash']:
            cost_per_unit = None
        elif change_type in ['restock', 'finished_batch'] and qty_change > 0:
            # Calculate weighted average
            current_value = item.quantity * item.cost_per_unit
            new_value = qty_change * (cost_override or item.cost_per_unit)
            total_quantity = item.quantity + qty_change

            if total_quantity > 0:
                weighted_avg_cost = (current_value + new_value) / total_quantity
                item.cost_per_unit = weighted_avg_cost

            cost_per_unit = cost_override or item.cost_per_unit
        elif cost_override is not None and change_type == 'cost_override':
            cost_per_unit = cost_override
            item.cost_per_unit = cost_override
        else:
            cost_per_unit = item.cost_per_unit

        # Handle inventory changes using FIFO service
        if qty_change < 0:
            # Deductions - use FIFO service
            success, deduction_plan, available_qty = FIFOService.calculate_deduction_plan(
                item_id, abs(qty_change), change_type
            )

            if not success:
                raise ValueError("Insufficient fresh FIFO stock (expired lots frozen)")

            # Execute the deduction plan using FIFO service
            FIFOService.execute_deduction_plan(deduction_plan, item_id)

            # Use FIFO service for all deductions - it routes to the correct history table
            FIFOService.create_deduction_history(
                item_id, deduction_plan, change_type, notes, 
                batch_id=batch_id, created_by=created_by, 
                customer=customer, sale_price=sale_price, order_id=order_id
            )
        elif qty_change > 0:
            # Additions - use FIFO service
            if change_type == 'refunded' and batch_id:
                # Handle refund credits using FIFO service
                FIFOService.handle_refund_credits(
                    item_id, qty_change, batch_id, notes, created_by, cost_per_unit
                )
            else:
                # Use FIFO service for all additions - it routes to the correct history table
                FIFOService.add_fifo_entry(
                    inventory_item_id=item_id,
                    quantity=qty_change,
                    change_type=change_type,
                    unit=item.unit,
                    notes=notes,
                    cost_per_unit=cost_per_unit,
                    expiration_date=expiration_date,
                    shelf_life_days=shelf_life_to_use,
                    batch_id=batch_id,
                    created_by=created_by,
                    customer=customer,
                    sale_price=sale_price,
                    order_id=order_id
                )

        # Update inventory quantity with rounding
        rounded_qty_change = ConversionEngine.round_value(qty_change, 3)
        item.quantity = ConversionEngine.round_value(item.quantity + rounded_qty_change, 3)

        db.session.commit()

        # Validate inventory/FIFO sync after adjustment
        is_valid, error_msg, inv_qty, fifo_total = validate_inventory_fifo_sync(item_id, item_type)
        if not is_valid:
            # Rollback the transaction
            db.session.rollback()
            raise ValueError(f"Inventory adjustment failed validation: {error_msg}")

        return True

    except Exception as e:
        db.session.rollback()
        raise e