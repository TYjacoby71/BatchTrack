
from flask_login import current_user
from app.models import db, InventoryItem, InventoryHistory
from datetime import datetime, timedelta
from sqlalchemy import and_
import logging

logger = logging.getLogger(__name__)


def _calculate_deduction_plan_internal(item_id, required_quantity, change_type='use'):
    """Calculate FIFO deduction plan with expiration awareness"""
    from app.models import InventoryItem, InventoryHistory
    from sqlalchemy import and_
    from datetime import datetime

    item = InventoryItem.query.get(item_id)
    if not item:
        return None, "Item not found"

    # Get organization for proper scoping
    org_id = current_user.organization_id if current_user.is_authenticated else item.organization_id

    # Use different history tables based on item type
    if item.type == 'product':
        from app.models.product import ProductSKUHistory
        available_entries = ProductSKUHistory.query.filter(
            and_(
                ProductSKUHistory.inventory_item_id == item_id,
                ProductSKUHistory.remaining_quantity > 0,
                ProductSKUHistory.organization_id == org_id
            )
        ).order_by(ProductSKUHistory.timestamp.asc()).all()
    else:
        available_entries = InventoryHistory.query.filter(
            and_(
                InventoryHistory.inventory_item_id == item_id,
                InventoryHistory.remaining_quantity > 0,
                InventoryHistory.organization_id == org_id
            )
        ).order_by(InventoryHistory.timestamp.asc()).all()

    # Separate fresh and expired entries
    today = datetime.now().date()
    fresh_entries = []
    expired_entries = []

    for entry in available_entries:
        if hasattr(entry, 'expiration_date') and entry.expiration_date and entry.expiration_date < today:
            expired_entries.append(entry)
        else:
            fresh_entries.append(entry)

    # For most operations, only use fresh inventory
    if change_type in ['spoil', 'expired', 'trash']:
        # These operations can consume from any inventory (including expired)
        usable_entries = fresh_entries + expired_entries
    else:
        # Normal operations should only consume fresh inventory
        usable_entries = fresh_entries

    deduction_plan = []
    remaining_needed = float(required_quantity)

    for entry in usable_entries:
        if remaining_needed <= 0:
            break

        available_qty = float(entry.remaining_quantity)
        deduct_from_entry = min(available_qty, remaining_needed)

        if deduct_from_entry > 0:
            deduction_plan.append((
                entry.id,
                deduct_from_entry,
                getattr(entry, 'unit_cost', None)
            ))
            remaining_needed -= deduct_from_entry

    # Check if we have enough fresh inventory for non-spoilage operations
    if remaining_needed > 0:
        if change_type not in ['spoil', 'expired', 'trash']:
            fresh_total = sum(float(e.remaining_quantity) for e in fresh_entries)
            return None, f"Insufficient fresh inventory: need {required_quantity}, available {fresh_total}"
        else:
            # For spoilage/trash, we tried everything and still don't have enough
            total_available = sum(float(e.remaining_quantity) for e in available_entries)
            return None, f"Insufficient inventory: need {required_quantity}, available {total_available}"

    return deduction_plan, None


def _execute_deduction_plan_internal(deduction_plan, item_id):
    """Execute FIFO deduction plan"""
    from app.models import InventoryItem, InventoryHistory
    from app.models.product import ProductSKUHistory

    item = InventoryItem.query.get(item_id)
    if not item:
        return False, "Item not found"

    for entry_id, deduct_quantity, unit_cost in deduction_plan:
        if item.type == 'product':
            entry = ProductSKUHistory.query.get(entry_id)
        else:
            entry = InventoryHistory.query.get(entry_id)

        if not entry:
            return False, f"FIFO entry {entry_id} not found"

        new_remaining = float(entry.remaining_quantity) - deduct_quantity
        entry.remaining_quantity = max(0.0, new_remaining)

    try:
        db.session.flush()
        return True, None
    except Exception as e:
        return False, f"Database error during deduction: {str(e)}"


def _record_deduction_plan_internal(item_id, deduction_plan, change_type, notes, **kwargs):
    """Record deduction history entries"""
    from app.models import InventoryItem
    from app.utils.fifo_generator import generate_fifo_code

    item = InventoryItem.query.get(item_id)
    if not item:
        return False

    # Extract optional parameters
    batch_id = kwargs.get('batch_id')
    created_by = kwargs.get('created_by')
    customer = kwargs.get('customer')
    sale_price = kwargs.get('sale_price')
    order_id = kwargs.get('order_id')

    history_unit = 'count' if item.type == 'container' else item.unit
    org_id = current_user.organization_id if current_user.is_authenticated else item.organization_id

    try:
        for entry_id, qty_deducted, unit_cost in deduction_plan:
            fifo_code = generate_fifo_code(change_type)
            
            if item.type == 'product':
                from app.models.product import ProductSKUHistory
                history = ProductSKUHistory(
                    inventory_item_id=item_id,
                    change_type=change_type,
                    quantity_change=-qty_deducted,
                    remaining_quantity=0.0,
                    unit=history_unit,
                    notes=notes,
                    created_by=created_by,
                    organization_id=org_id,
                    fifo_code=fifo_code,
                    fifo_reference_id=entry_id,
                    unit_cost=unit_cost,
                    batch_id=batch_id,
                    customer=customer,
                    sale_price=sale_price,
                    order_id=order_id
                )
            else:
                history = InventoryHistory(
                    inventory_item_id=item_id,
                    change_type=change_type,
                    quantity_change=-qty_deducted,
                    remaining_quantity=0.0,
                    unit=history_unit,
                    note=notes,
                    created_by=created_by,
                    quantity_used=0.0,
                    organization_id=org_id,
                    fifo_code=fifo_code,
                    fifo_reference_id=entry_id,
                    unit_cost=unit_cost,
                    batch_id=batch_id,
                    customer=customer,
                    sale_price=sale_price,
                    order_id=order_id
                )
            
            db.session.add(history)
        
        db.session.flush()
        return True
    except Exception as e:
        logger.error(f"Error recording deduction plan: {str(e)}")
        return False


def _internal_add_fifo_entry_enhanced(
    item_id: int,
    quantity: float,
    change_type: str,
    unit: str | None,
    notes: str | None,
    cost_per_unit: float | None,
    **kwargs,
) -> tuple[bool, str | None]:
    """
    Robustly creates a new FIFO lot and updates the parent inventory item.
    This is the single source of truth for all inventory additions.
    """
    from app.models.inventory import InventoryItem, InventoryHistory
    from app.models.product import ProductSKUHistory
    from app.utils.fifo_generator import generate_fifo_code
    from datetime import datetime, timedelta

    item = db.session.get(InventoryItem, item_id)
    if not item:
        logger.error(f"Cannot add FIFO entry: InventoryItem with ID {item_id} not found.")
        return False, "Item not found"

    # --- 1. Prepare data for the history record ---
    history_data = {
        "inventory_item_id": item_id,
        "timestamp": datetime.utcnow(),
        "change_type": change_type,
        "quantity_change": float(quantity),
        "unit": unit or item.unit,
        "remaining_quantity": float(quantity),  # New lots start with full remaining quantity
        "unit_cost": cost_per_unit,
        "batch_id": kwargs.get("batch_id"),
        "created_by": kwargs.get("created_by"),
        "organization_id": item.organization_id,  # Inherit org_id from the parent item
        "fifo_code": generate_fifo_code(change_type),
    }

    # Handle expiration data
    expiration_date = kwargs.get('expiration_date')
    shelf_life_days = kwargs.get('shelf_life_days')
    custom_expiration_date = kwargs.get('custom_expiration_date')
    custom_shelf_life_days = kwargs.get('custom_shelf_life_days')

    final_expiration_date = None
    final_shelf_life_days = None
    is_perishable = False

    if item.is_perishable:
        is_perishable = True
        if custom_expiration_date:
            final_expiration_date = custom_expiration_date
        elif expiration_date:
            final_expiration_date = expiration_date
        elif custom_shelf_life_days and custom_shelf_life_days > 0:
            final_shelf_life_days = custom_shelf_life_days
            final_expiration_date = datetime.utcnow().date() + timedelta(days=custom_shelf_life_days)
        elif shelf_life_days and shelf_life_days > 0:
            final_shelf_life_days = shelf_life_days
            final_expiration_date = datetime.utcnow().date() + timedelta(days=shelf_life_days)
        elif item.shelf_life_days and item.shelf_life_days > 0:
            final_shelf_life_days = item.shelf_life_days
            final_expiration_date = datetime.utcnow().date() + timedelta(days=item.shelf_life_days)

    history_data.update({
        "is_perishable": is_perishable,
        "shelf_life_days": final_shelf_life_days,
        "expiration_date": final_expiration_date,
    })

    # --- 2. Create the correct type of history record ---
    # The models have different column names, so we handle them separately.
    if item.type == 'product':
        # ProductSKUHistory has extra fields for sales context
        product_specific_data = {
            "customer": kwargs.get("customer"),
            "sale_price": kwargs.get("sale_price"),
            "order_id": kwargs.get("order_id"),
            "notes": notes,  # ProductSKUHistory uses 'notes'
        }
        history_data.update(product_specific_data)
        history_entry = ProductSKUHistory(**history_data)
    else:
        # InventoryHistory is for raw ingredients/containers
        history_data.update({
            "note": notes,  # InventoryHistory uses 'note'
            "quantity_used": 0.0,  # Required field for InventoryHistory
        })
        history_entry = InventoryHistory(**history_data)

    try:
        db.session.add(history_entry)
        db.session.flush()  # Ensure the entry is persisted before updating the parent

        # --- 3. Atomically update the parent InventoryItem quantity ---
        item.quantity = (item.quantity or 0.0) + float(quantity)

        # The commit will happen in the main process_inventory_adjustment function
        return True, None

    except TypeError as e:
        # This catches errors like the one you saw: passing an invalid keyword
        logger.error(f"Error creating history entry for item {item_id}: {e}")
        return False, f"Error creating FIFO entry: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error creating FIFO entry for item {item_id}: {e}")
        return False, f"Error creating FIFO entry: {str(e)}"
