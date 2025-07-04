from flask import current_app
from flask_login import current_user
from app.models import db, InventoryItem, InventoryHistory
from datetime import datetime, timedelta
from app.services.conversion_wrapper import safe_convert
from app.services.unit_conversion import ConversionEngine
from app.blueprints.fifo.services import deduct_fifo, get_fifo_entries
from app.utils.fifo_generator import generate_fifo_id

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

        # Get ALL FIFO entries with remaining quantity (including frozen expired ones)
        from sqlalchemy import and_
        all_fifo_entries = InventoryHistory.query.filter(
            and_(
                InventoryHistory.inventory_item_id == item_id,
                InventoryHistory.remaining_quantity > 0
            )
        ).all()

        fifo_total = sum(entry.remaining_quantity for entry in all_fifo_entries)
        current_qty = item.quantity
        item_name = item.name

    # Allow small floating point differences (0.001)
    if abs(current_qty - fifo_total) > 0.001:
        error_msg = f"SYNC ERROR: {item_name} inventory ({current_qty}) != FIFO total ({fifo_total}) [includes frozen expired]"
        return False, error_msg, current_qty, fifo_total

    return True, "", current_qty, fifo_total

# FIFO ID generation now handled by centralized utils/fifo_generator.py

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
    Centralized inventory adjustment logic for use in both manual adjustments and batch deductions
    """
    # Handle different item types - ProductSKU vs InventoryItem
    if item_type == 'product':
        from app.models.product import ProductSKU
        item = ProductSKU.query.get_or_404(item_id)
    else:
        item = InventoryItem.query.get_or_404(item_id)

    # Convert units if needed (except for containers)
    # For ProductSKU, we don't need unit conversion as it's already in the right unit
    if item_type != 'product' and getattr(item, 'type', None) != 'container' and unit != item.unit:
        conversion = safe_convert(quantity, unit, item.unit, ingredient_id=item.id)
        if not conversion['ok']:
            raise ValueError(conversion['error'])
        quantity = conversion['result']['converted_value']

    # Determine quantity change and special handling
    # Handle different quantity property names
    current_quantity = getattr(item, 'current_quantity', None) or getattr(item, 'quantity', 0)

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
                item.quantity = (item.quantity or 0) - quantity
            # Create history entry but don't change total inventory
            qty_change = 0
        else:
            raise ValueError("Item type doesn't support reservations")
    elif change_type == 'returned':
        # Return from sale - add back to inventory
        qty_change = quantity
    else:
        qty_change = quantity

    # Handle expiration using ExpirationService
    from app.blueprints.expiration.services import ExpirationService

    expiration_date = None
    shelf_life_to_use = None

    # Handle custom expiration date (from batch completion)
    if custom_expiration_date:
        expiration_date = custom_expiration_date
        shelf_life_to_use = custom_shelf_life_days
    elif change_type in ['restock', 'recount'] and item.is_perishable and item.shelf_life_days and qty_change > 0:
        # Use ingredient's default shelf life for regular perishable restocks and positive recount adjustments
        expiration_date = ExpirationService.calculate_expiration_date(
            datetime.utcnow(), item.shelf_life_days
        )
        shelf_life_to_use = item.shelf_life_days

    # Get cost - handle weighted average vs override
    if item_type == 'product':
        # For ProductSKU, use the underlying inventory_item for cost calculations
        inventory_item = item.inventory_item

        if change_type in ['spoil', 'trash']:
            cost_per_unit = None
        elif change_type in ['restock', 'finished_batch'] and qty_change > 0:
            # Calculate weighted average on inventory_item
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
    else:
        # For InventoryItem, handle cost as before
        if change_type in ['spoil', 'trash']:
            cost_per_unit = None
        elif change_type in ['restock', 'finished_batch'] and qty_change > 0:
            current_value = item.quantity * item.cost_per_unit
            new_value = qty_change * (cost_override or item.cost_per_unit)
            total_quantity = item.quantity + qty_change

            if total_quantity > 0:
                weighted_avg_cost = (current_value + new_value) / total_quantity
                item.cost_per_unit = weighted_avg_cost

            cost_per_unit = cost_override or item.cost_per_unit
        elif cost_override is not None and change_type == 'cost_override':
            cost_per_unit = cost_override
        else:
            cost_per_unit = item.cost_per_unit

    # Deductions
    if qty_change < 0:
        # For spoil/trash/expired_disposal operations, allow targeting expired lots specifically
        if change_type in ['spoil', 'trash', 'expired_disposal']:
            from app.blueprints.fifo.services import get_expired_fifo_entries
            expired_entries = get_expired_fifo_entries(item.id)

            # If we have expired stock and the request quantity matches available expired stock,
            # deduct from expired lots instead of fresh stock
            expired_total = sum(entry.remaining_quantity for entry in expired_entries)
            if expired_total >= abs(qty_change):
                # Deduct from expired entries manually
                remaining_to_deduct = abs(qty_change)
                deductions = []

                for entry in expired_entries:
                    if remaining_to_deduct <= 0:
                        break

                    deduction = min(entry.remaining_quantity, remaining_to_deduct)
                    entry.remaining_quantity -= deduction
                    remaining_to_deduct -= deduction
                    deductions.append((entry.id, deduction, entry.unit_cost))
            else:
                # Fall back to normal FIFO if not enough expired stock
                success, deductions = deduct_fifo(item.id, abs(qty_change), change_type, notes)
                if not success:
                    raise ValueError("Insufficient FIFO stock (expired lots frozen)")
        else:
            # Regular operations use normal FIFO (skips expired)
            success, deductions = deduct_fifo(item.id, abs(qty_change), change_type, notes)
            if not success:
                raise ValueError("Insufficient fresh FIFO stock (expired lots frozen)")

        for entry_id, deduction_amount, _ in deductions:
            # Show clearer description for batch cancellations
            used_for_note = "canceled" if change_type == 'refunded' and batch_id else notes

            # Create deduction history for each FIFO entry used
            # Ensure unit is never None for containers
            history_unit = item.unit if item.unit else 'count'

            # Only set quantity_used for actual consumption (spoil, trash, batch usage)
            quantity_used_value = deduction_amount if change_type in ['spoil', 'trash', 'batch', 'use'] else 0.0

            # Create appropriate history entry based on item type
            if item_type == 'product':
                from app.models.product import ProductSKUHistory
                history = ProductSKUHistory(
                    sku_id=item.id,
                    change_type=change_type,
                    quantity_change=-deduction_amount,
                    unit=history_unit,
                    remaining_quantity=0,
                    fifo_reference_id=entry_id,
                    unit_cost=cost_per_unit,
                    notes=f"{used_for_note} (From FIFO #{entry_id})",
                    created_by=created_by,
                    customer=customer,
                    sale_price=sale_price,
                    order_id=order_id,
                    organization_id=current_user.organization_id
                )
            else:
                history = InventoryHistory(
                    inventory_item_id=item.id,
                    change_type=change_type,
                    quantity_change=-deduction_amount,
                    unit=history_unit,  # Record original unit used, default to 'count' for containers
                    remaining_quantity=0,
                    fifo_reference_id=entry_id,
                    unit_cost=cost_per_unit,
                    note=f"{used_for_note} (From FIFO #{entry_id})",
                    created_by=created_by,
                    quantity_used=quantity_used_value,  # Only set for actual consumption
                    used_for_batch_id=batch_id,
                    organization_id=current_user.organization_id
                )
            db.session.add(history)
        # Update quantity with rounding - handle ProductSKU vs InventoryItem
        rounded_qty_change = ConversionEngine.round_value(qty_change, 3)
        if item_type == 'product':
            # For ProductSKU, update the underlying inventory_item
            item.inventory_item.quantity = ConversionEngine.round_value(item.inventory_item.quantity + rounded_qty_change, 3)
        else:
            # For InventoryItem, update directly
            item.quantity = ConversionEngine.round_value(item.quantity + rounded_qty_change, 3)

    else:
        # Handle credits/refunds by finding original FIFO entries to credit back to
        if change_type == 'refunded' and batch_id:
            # Find the original deduction entries for this batch
            original_deductions = InventoryHistory.query.filter(
                InventoryHistory.inventory_item_id == item.id,
                InventoryHistory.used_for_batch_id == batch_id,
                InventoryHistory.quantity_change < 0,
                InventoryHistory.fifo_reference_id.isnot(None)
            ).order_by(InventoryHistory.timestamp.desc()).all()

            remaining_to_credit = qty_change

            # Credit back to the original FIFO entries
            for deduction in original_deductions:
                if remaining_to_credit <= 0:
                    break

                original_fifo_entry = InventoryHistory.query.get(deduction.fifo_reference_id)
                if original_fifo_entry:                    credit_amount = min(remaining_to_credit, abs(deduction.quantity_change))

                    # Credit back to the original FIFO entry's remaining quantity
                    original_fifo_entry.remaining_quantity += credit_amount
                    remaining_to_credit -= credit_amount

                    # Create credit history entry
                    # Ensure unit is never None for containers
                    credit_unit = item.unit if item.unit else 'count'
                    credit_history = InventoryHistory(
                        inventory_item_id=item.id,
                        change_type=change_type,
                        quantity_change=credit_amount,
                        unit=credit_unit,  # Record original unit used, default to 'count' for containers
                        remaining_quantity=0,  # Credits don't create new FIFO entries
                        unit_cost=cost_per_unit,
                        fifo_reference_id=original_fifo_entry.id,  # Reference the original FIFO entry
                        note=f"{notes} (Credited to FIFO #{original_fifo_entry.id})",
                        created_by=created_by,
                        quantity_used=0.0,  # Credits don't consume inventory
                        used_for_batch_id=batch_id,
                        organization_id=current_user.organization_id
                    )
                    db.session.add(credit_history)

            # If there's still quantity to credit (shouldn't happen in normal cases)
            if remaining_to_credit > 0:
                # Create new FIFO entry for any excess
                # Ensure unit is never None for containers
                excess_unit = item.unit if item.unit else 'count'
                excess_history = InventoryHistory(
                    inventory_item_id=item.id,
                    change_type='restock',  # Treat excess as new stock
                    quantity_change=remaining_to_credit,
                    unit=excess_unit,  # Use current inventory unit for new stock, default to 'count' for containers
                    remaining_quantity=remaining_to_credit,
                    unit_cost=cost_per_unit,
                    note=f"{notes} (Excess credit - no original FIFO found)",
                    created_by=created_by,
                    quantity_used=0.0,  # Restocks don't consume inventory
                    expiration_date=expiration_date,
                    used_for_batch_id=batch_id,
                    organization_id=current_user.organization_id
                )
                db.session.add(excess_history)
        else:
            # Regular additions (restock or recount or adjustment up)
            # Create new stock entry
            # Ensure unit is never None for containers
            addition_unit = item.unit if item.unit else 'count'

            # For recounts, calculate the original quantity before the recount
            original_quantity_for_recount = None
            if change_type == 'recount':
                original_quantity_for_recount = current_quantity

            # Create appropriate history entry based on item type
            if item_type == 'product':
                from app.models.product import ProductSKUHistory
                history = ProductSKUHistory(
                    sku_id=item.id,
                    change_type=change_type,
                    quantity_change=qty_change,
                    unit=addition_unit,
                    remaining_quantity=qty_change if change_type in ['restock', 'finished_batch', 'recount'] and qty_change > 0 else 0,
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
                    fifo_code=generate_fifo_id() if change_type in ['restock', 'finished_batch', 'recount'] and qty_change > 0 else None,
                    organization_id=current_user.organization_id
                )
            else:
                history = InventoryHistory(
                    inventory_item_id=item.id,
                    change_type=change_type,
                    quantity_change=qty_change,
                    unit=addition_unit,  # Record original unit used, default to 'count' for containers
                    remaining_quantity=qty_change if change_type in ['restock', 'finished_batch', 'recount'] and qty_change > 0 else 0,
                    unit_cost=cost_per_unit,
                    note=notes,
                    quantity_used=0.0,  # Additions don't consume inventory - always 0
                    created_by=created_by,
                    expiration_date=expiration_date,
                    shelf_life_days=shelf_life_to_use,  # Record the shelf life used for this entry
                    is_perishable=item.is_perishable if expiration_date else False,
                    batch_id=batch_id if change_type == 'finished_batch' else None,  # Set batch_id for finished_batch entries
                    used_for_batch_id=batch_id if change_type not in ['restock'] else None,  # Track batch for finished_batch
                    fifo_code=generate_fifo_id() if change_type in ['restock', 'finished_batch', 'recount'] and qty_change > 0 else None,
                    organization_id=current_user.organization_id
                )
            db.session.add(history)

        # Update quantity with rounding - handle ProductSKU vs InventoryItem
        rounded_qty_change = ConversionEngine.round_value(qty_change, 3)
        if item_type == 'product':
            # For ProductSKU, update the underlying inventory_item
            item.inventory_item.quantity = ConversionEngine.round_value(item.inventory_item.quantity + rounded_qty_change, 3)
        else:
            # For InventoryItem, update directly
            item.quantity = ConversionEngine.round_value(item.quantity + rounded_qty_change, 3)

    db.session.commit()

    # Validate inventory/FIFO sync after adjustment
    is_valid, error_msg, inv_qty, fifo_total = validate_inventory_fifo_sync(item_id, item_type)
    if not is_valid:
        # Rollback the transaction
        db.session.rollback()
        raise ValueError(f"Inventory adjustment failed validation: {error_msg}")

    return True