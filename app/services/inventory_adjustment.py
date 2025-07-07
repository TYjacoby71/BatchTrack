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
    Returns: (is_valid, error_message, inventory_qty, fifo_total)
    """
    # Handle different item types
    if item_type == 'product':
        from app.models.product import ProductSKU, ProductSKUHistory
        item = ProductSKU.query.get(item_id)
        if not item:
            return False, "Product SKU not found", 0, 0

        # Get ALL FIFO entries with remaining quantity (including frozen expired ones)
        from sqlalchemy import and_
        all_fifo_entries = ProductSKUHistory.query.filter(
            and_(
                ProductSKUHistory.sku_id == item_id,
                ProductSKUHistory.remaining_quantity > 0
            )
        ).all()

        fifo_total = sum(entry.remaining_quantity for entry in all_fifo_entries)
        current_qty = item.current_quantity
        item_name = item.display_name
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

def process_inventory_adjustment(
    item_id,
    quantity,
    change_type,
    unit=None,
    notes=None,
    batch_id=None,
    created_by=None,
    cost_override=None,
    custom_expiration_date=None,
    custom_shelf_life_days=None,
    item_type=None,  # 'ingredient', 'container', 'product'
    customer=None,  # For sales tracking
    sale_price=None,  # For sales tracking
    order_id=None,  # For marketplace integration
):
    """
    Centralized inventory adjustment logic - coordinates with FIFO service
    """
    # Handle different item types - ProductSKU vs InventoryItem
    if item_type == 'product':
        from app.models.product import ProductSKU
        item = ProductSKU.query.get_or_404(item_id)
        target_item_id = item.inventory_item.id  # Use underlying inventory item for FIFO
        inventory_item = item.inventory_item
    else:
        item = InventoryItem.query.get_or_404(item_id)
        target_item_id = item_id
        inventory_item = item

    # Convert units if needed (except for containers and products)
    if item_type != 'product' and getattr(item, 'type', None) != 'container' and unit != inventory_item.unit:
        conversion = safe_convert(quantity, unit, inventory_item.unit, ingredient_id=inventory_item.id)
        if not conversion['ok']:
            raise ValueError(conversion['error'])
        quantity = conversion['result']['converted_value']

    # Determine quantity change and special handling
    current_quantity = getattr(item, 'current_quantity', None) or getattr(inventory_item, 'quantity', 0)

    if change_type == 'recount':
        qty_change = quantity - current_quantity
    elif change_type in ['spoil', 'trash', 'sold', 'gift', 'tester', 'quality_fail', 'expired_disposal']:
        qty_change = -abs(quantity)
    elif change_type == 'reserved':
        # Special handling: move from current to reserved, don't change total
        if hasattr(item, 'reserved_quantity'):
            item.reserved_quantity = (item.reserved_quantity or 0) + quantity
            if hasattr(item, 'current_quantity'):
                item.current_quantity = (item.current_quantity or 0) - quantity
            else:
                inventory_item.quantity = (inventory_item.quantity or 0) - quantity
            # Create history entry but don't change total inventory
            qty_change = 0
        else:
            raise ValueError("Item type doesn't support reservations")
    elif change_type == 'returned':
        qty_change = quantity
    else:
        qty_change = quantity

    # Handle expiration using ExpirationService
    from app.blueprints.expiration.services import ExpirationService

    expiration_date = None
    shelf_life_to_use = None

    if custom_expiration_date:
        expiration_date = custom_expiration_date
        shelf_life_to_use = custom_shelf_life_days
    elif change_type == 'restock' and inventory_item.is_perishable and inventory_item.shelf_life_days:
        expiration_date = ExpirationService.calculate_expiration_date(
            datetime.utcnow(), inventory_item.shelf_life_days
        )
        shelf_life_to_use = inventory_item.shelf_life_days

    # Handle cost calculations
    if change_type in ['spoil', 'trash']:
        cost_per_unit = None
    elif change_type in ['restock', 'finished_batch'] and qty_change > 0:
        # Calculate weighted average
        current_value = inventory_item.quantity * inventory_item.cost_per_unit
        new_value = qty_change * (cost_override or inventory_item.cost_per_unit)
        total_quantity = inventory_item.quantity + qty_change

        if total_quantity > 0:
            weighted_avg_cost = (current_value + new_value) / total_quantity
            inventory_item.cost_per_unit = weighted_avg_cost

        cost_per_unit = cost_override or inventory_item.cost_per_unit
    elif cost_override is not None and change_type == 'cost_override':
        cost_per_unit = cost_override
        inventory_item.cost_per_unit = cost_override
    else:
        cost_per_unit = inventory_item.cost_per_unit

    # Handle inventory changes using FIFO service
    if qty_change < 0:
        # Deductions - use appropriate FIFO service
        if item_type == 'product':
            success, deduction_plan, available_qty = FIFOService.calculate_product_sku_deduction_plan(
                item.id, abs(qty_change), change_type
            )
        else:
            success, deduction_plan, available_qty = FIFOService.calculate_deduction_plan(
                target_item_id, abs(qty_change), change_type
            )

        if not success:
            raise ValueError("Insufficient fresh FIFO stock (expired lots frozen)")

        # Execute the deduction plan
        if item_type == 'product':
            FIFOService.execute_product_sku_deduction_plan(deduction_plan)
        else:
            FIFOService.execute_deduction_plan(deduction_plan)

        # Create history entries for deductions
        if item_type == 'product':
            # Handle ProductSKU history separately
            from app.models.product import ProductSKUHistory
            history_unit = inventory_item.unit if inventory_item.unit else 'count'

            for entry_id, deduction_amount, unit_cost in deduction_plan:
                used_for_note = "canceled" if change_type == 'refunded' and batch_id else notes
                quantity_used_value = deduction_amount if change_type in ['spoil', 'trash', 'batch', 'use'] else 0.0

                history = ProductSKUHistory(
                    sku_id=item.id,
                    change_type=change_type,
                    quantity_change=-deduction_amount,  # Ensure negative for deductions
                    unit=history_unit,
                    remaining_quantity=0,  # Deductions don't create new FIFO entries
                    fifo_reference_id=entry_id,
                    unit_cost=unit_cost,  # Use unit cost from deduction plan
                    notes=f"{used_for_note} (From FIFO #{entry_id})",
                    created_by=created_by,
                    customer=customer,
                    sale_price=sale_price,
                    order_id=order_id,
                    quantity_used=quantity_used_value,
                    organization_id=current_user.organization_id if current_user and current_user.is_authenticated else None
                )
                db.session.add(history)
        else:
            # Use FIFO service for regular inventory items
            FIFOService.create_deduction_history(
                target_item_id, deduction_plan, change_type, notes,
                batch_id, created_by, customer, sale_price, order_id
            )

    elif qty_change > 0:
        # Additions - use FIFO service
        if change_type == 'refunded' and batch_id:
            # Handle refund credits using FIFO service
            if item_type == 'product':
                # For ProductSKU refunds, add directly to most recent entry or create new
                from app.models.product import ProductSKUHistory
                
                recent_entry = ProductSKUHistory.query.filter(
                    and_(
                        ProductSKUHistory.sku_id == item.id,
                        ProductSKUHistory.batch_id == batch_id,
                        ProductSKUHistory.remaining_quantity.isnot(None)
                    )
                ).order_by(ProductSKUHistory.timestamp.desc()).first()
                
                if recent_entry:
                    recent_entry.remaining_quantity += qty_change
                
                # Create refund history record
                history = ProductSKUHistory(
                    sku_id=item.id,
                    change_type='refunded',
                    quantity_change=qty_change,
                    unit=inventory_item.unit,
                    remaining_quantity=0,  # Just a record
                    fifo_reference_id=recent_entry.id if recent_entry else None,
                    unit_cost=cost_per_unit,
                    notes=f"{notes} (Credited to FIFO #{recent_entry.id if recent_entry else 'new'})",
                    batch_id=batch_id,
                    created_by=created_by,
                    organization_id=current_user.organization_id if current_user and current_user.is_authenticated else None
                )
                db.session.add(history)
            else:
                FIFOService.handle_refund_credits(
                    target_item_id, qty_change, batch_id, notes, created_by, cost_per_unit
                )
        else:
            # Regular additions using FIFO service
            if item_type == 'product':
                # Handle ProductSKU history separately
                from app.models.product import ProductSKUHistory
                history_unit = inventory_item.unit if inventory_item.unit else 'count'

                history = ProductSKUHistory(
                    sku_id=item.id,
                    change_type=change_type,
                    quantity_change=qty_change,  # Positive for additions
                    unit=history_unit,
                    remaining_quantity=qty_change if change_type in ['restock', 'finished_batch', 'manual_addition', 'returned'] else None,
                    original_quantity=qty_change if change_type in ['restock', 'finished_batch', 'manual_addition', 'returned'] else None,
                    unit_cost=cost_per_unit,
                    notes=notes,
                    created_by=created_by,
                    expiration_date=expiration_date,
                    shelf_life_days=shelf_life_to_use,
                    is_perishable=expiration_date is not None,
                    batch_id=batch_id if change_type == 'finished_batch' else None,
                    customer=customer,
                    sale_price=sale_price,
                    order_id=order_id,
                    organization_id=current_user.organization_id if current_user and current_user.is_authenticated else None
                )
                db.session.add(history)
            else:
                # Use FIFO service for regular inventory items
                FIFOService.add_fifo_entry(
                    inventory_item_id=target_item_id,
                    quantity=qty_change,
                    change_type=change_type,
                    unit=inventory_item.unit,
                    notes=notes,
                    cost_per_unit=cost_per_unit,
                    expiration_date=expiration_date,
                    shelf_life_days=shelf_life_to_use,
                    batch_id=batch_id,
                    created_by=created_by
                )

    # Update inventory quantity with rounding
    rounded_qty_change = ConversionEngine.round_value(qty_change, 3)
    inventory_item.quantity = ConversionEngine.round_value(inventory_item.quantity + rounded_qty_change, 3)

    db.session.commit()

    # Validate inventory/FIFO sync after adjustment
    is_valid, error_msg, inv_qty, fifo_total = validate_inventory_fifo_sync(item_id, item_type)
    if not is_valid:
        # Rollback the transaction
        db.session.rollback()
        raise ValueError(f"Inventory adjustment failed validation: {error_msg}")

    return True