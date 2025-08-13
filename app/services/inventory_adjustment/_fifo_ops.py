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
    """
    Records deduction history entries using the unified history model.
    No more branching logic - one model handles all inventory types.
    """
    from app.models import InventoryItem, UnifiedInventoryHistory
    from app.utils.fifo_generator import generate_fifo_code

    item = db.session.get(InventoryItem, item_id)
    if not item:
        logger.error(f"Cannot record deduction plan: Item {item_id} not found.")
        return False

    try:
        for entry_id, qty_deducted, unit_cost in deduction_plan:
            # Create unified history entry - works for all item types
            history_entry = UnifiedInventoryHistory(
                inventory_item_id=item_id,
                change_type=change_type,
                quantity_change=-abs(qty_deducted),
                remaining_quantity=0.0,  # Deductions are audit entries
                unit='count' if item.type == 'container' else item.unit,
                fifo_reference_id=entry_id,
                unit_cost=unit_cost,
                fifo_code=generate_fifo_code(change_type),
                batch_id=kwargs.get('batch_id'),
                created_by=kwargs.get('created_by'),
                notes=notes,
                quantity_used=0.0,
                # Product-specific fields (will be None for ingredients)
                customer=kwargs.get('customer'),
                sale_price=kwargs.get('sale_price'),
                order_id=kwargs.get('order_id'),
                organization_id=item.organization_id,
            )

            db.session.add(history_entry)

        db.session.flush()  # Persist all history entries for this plan
        return True

    except Exception as e:
        logger.error(f"Error recording deduction plan: {e}")
        return False


def _internal_add_fifo_entry_enhanced(
    item_id: int,
    quantity: float,
    change_type: str,
    unit: str,
    notes: str = None,
    cost_per_unit: float = None,
    expiration_date=None,
    shelf_life_days: int = None,
    batch_id: int = None,
    created_by: int = None,
    customer: str = None,
    sale_price: float = None,
    order_id: str = None,
    custom_expiration_date=None,
    custom_shelf_life_days: int = None
) -> tuple[bool, str]:
    """
    Internal helper to add FIFO entry with enhanced tracking.
    This creates the actual FIFO inventory tracking record.
    """
    from app.models import db, UnifiedInventoryHistory, InventoryItem
    from app.utils.fifo_generator import generate_fifo_code

    try:
        item = InventoryItem.query.get(item_id)
        if not item:
            return False, f"Item {item_id} not found"

        # Generate FIFO reference
        fifo_reference_id = generate_fifo_code()

        # Use provided expiration date or calculate from shelf life
        final_expiration_date = custom_expiration_date or expiration_date
        final_shelf_life = custom_shelf_life_days or shelf_life_days

        # Create FIFO entry in UnifiedInventoryHistory
        fifo_entry = UnifiedInventoryHistory(
            inventory_item_id=item_id,
            change_type=change_type,
            quantity_change=quantity,
            remaining_quantity=quantity,  # For additions, remaining = quantity added
            unit=unit,
            unit_cost=cost_per_unit,
            fifo_reference_id=fifo_reference_id,
            fifo_code=fifo_reference_id,  # Use same as reference for now
            batch_id=batch_id,
            notes=notes,
            created_by=created_by,
            quantity_used=0.0,  # No usage yet for new additions
            is_perishable=item.is_perishable,
            shelf_life_days=final_shelf_life,
            expiration_date=final_expiration_date,
            organization_id=item.organization_id,
            # Product-specific fields
            customer=customer,
            sale_price=sale_price,
            order_id=order_id
        )

        db.session.add(fifo_entry)
        db.session.flush()  # Get the ID

        # Update the item quantity
        item.quantity = item.quantity + quantity

        logger.info(f"Created FIFO entry {fifo_entry.id} for item {item_id}, quantity {quantity}")
        return True, None

    except Exception as e:
        logger.error(f"Failed to add FIFO entry for item {item_id}: {str(e)}")
        return False, str(e)