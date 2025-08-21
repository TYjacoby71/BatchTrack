import logging
from datetime import datetime, timedelta
from decimal import Decimal
from app.models import db, InventoryItem, UnifiedInventoryHistory
from app.utils.timezone_utils import TimezoneUtils
from sqlalchemy import and_

logger = logging.getLogger(__name__)


# ========== OPERATION TYPE CONFIGURATIONS ==========

ADDITIVE_OPERATIONS = {
    'restock': {'message': 'Restocked', 'use_cost_override': True},
    'manual_addition': {'message': 'Added manually', 'use_cost_override': False},
    'returned': {'message': 'Returned', 'use_cost_override': False},
    'refunded': {'message': 'Refunded', 'use_cost_override': False},
    'finished_batch': {'message': 'Added from finished batch', 'use_cost_override': False},
    'unreserved': {'message': 'Unreserved', 'use_cost_override': False},
    'initial_stock': {'message': 'Initial stock added', 'use_cost_override': True}
}

DEDUCTIVE_OPERATIONS = {
    'use': {'message': 'Used'},
    'batch': {'message': 'Used in batch'},
    'sale': {'message': 'Sold'},
    'spoil': {'message': 'Marked as spoiled'},
    'trash': {'message': 'Trashed'},
    'expired': {'message': 'Removed (expired)'},
    'damaged': {'message': 'Removed (damaged)'},
    'quality_fail': {'message': 'Removed (quality fail)'},
    'sample': {'message': 'Used for sample'},
    'tester': {'message': 'Used for tester'},
    'gift': {'message': 'Gave as gift'},
    'reserved': {'message': 'Reserved'},
    'recount_deduction': {'message': 'Recount adjustment'}
}

SPECIAL_OPERATIONS = {
    'cost_override': 'handle_cost_override_special',
    'recount': 'handle_recount_special'  # Handled in _recount_logic.py
}


# ========== UNIFIED HANDLERS ==========

def handle_additive_operation(item, quantity, change_type, notes=None, created_by=None, cost_override=None, **kwargs):
    """Universal handler for all additive operations"""
    try:
        if change_type not in ADDITIVE_OPERATIONS:
            return False, f"Unknown additive operation: {change_type}"

        config = ADDITIVE_OPERATIONS[change_type]

        # Determine cost per unit
        if config.get('use_cost_override') and cost_override is not None:
            cost_per_unit = cost_override
        else:
            cost_per_unit = item.cost_per_unit

        success, error = _internal_add_fifo_entry_enhanced(
            item_id=item.id,
            quantity=quantity,
            change_type=change_type,
            unit=getattr(item, 'unit', 'count'),
            notes=notes,
            cost_per_unit=cost_per_unit,
            created_by=created_by,
            **kwargs
        )

        if success:
            message = f"{config['message']} {quantity} {getattr(item, 'unit', 'units')}"
            return True, message
        return False, error

    except Exception as e:
        logger.error(f"Error in additive operation {change_type}: {str(e)}")
        return False, str(e)


def handle_deductive_operation(item, quantity, change_type, notes=None, created_by=None, **kwargs):
    """Universal handler for all deductive operations"""
    try:
        if change_type not in DEDUCTIVE_OPERATIONS:
            return False, f"Unknown deductive operation: {change_type}"

        config = DEDUCTIVE_OPERATIONS[change_type]

        success = _handle_deductive_operation_internal(
            item, quantity, change_type, notes, created_by, **kwargs
        )

        if success:
            message = f"{config['message']} {quantity} {getattr(item, 'unit', 'units')}"
            return True, message
        return False, "Insufficient inventory"

    except Exception as e:
        logger.error(f"Error in deductive operation {change_type}: {str(e)}")
        return False, str(e)


def handle_cost_override_special(item, quantity, notes=None, created_by=None, cost_override=None, **kwargs):
    """Special handler for cost override (no quantity change)"""
    try:
        if cost_override is not None:
            item.cost_per_unit = cost_override
            db.session.commit()
            return True, f"Updated cost to {cost_override}"
        return False, "No cost override provided"

    except Exception as e:
        logger.error(f"Error in cost override: {str(e)}")
        return False, str(e)


# ========== OPERATION DISPATCHER ==========

def get_operation_handler(change_type):
    """Get the appropriate handler for a change_type"""
    if change_type in ADDITIVE_OPERATIONS:
        return handle_additive_operation
    elif change_type in DEDUCTIVE_OPERATIONS:
        return handle_deductive_operation
    elif change_type in SPECIAL_OPERATIONS:
        handler_name = SPECIAL_OPERATIONS[change_type]
        if handler_name == 'handle_cost_override_special':
            return handle_cost_override_special
        # For recount, return None - it's handled in _recount_logic.py
        return None
    else:
        return None


# ========== INTERNAL HELPER FUNCTIONS ==========

def _handle_deductive_operation_internal(item, quantity, change_type, notes, created_by, **kwargs):
    """Internal logic for deductive operations using FIFO service"""
    try:
        # Get deduction plan from FIFO service
        deduction_plan, error = _calculate_deduction_plan_internal(
            item.id, abs(quantity), change_type
        )

        if error:
            logger.error(f"Deduction planning failed: {error}")
            return False

        if not deduction_plan:
            logger.warning(f"No deduction plan generated for {item.id}")
            return False

        # Execute deduction plan
        success, error = _execute_deduction_plan_internal(deduction_plan, item.id)
        if not success:
            logger.error(f"Deduction execution failed: {error}")
            return False

        # Record audit trail
        success = _record_deduction_plan_internal(
            item.id, deduction_plan, change_type, notes, 
            created_by=created_by, **kwargs
        )
        if not success:
            logger.error(f"Deduction recording failed")
            return False

        # Sync item quantity to FIFO total
        current_fifo_total = calculate_current_fifo_total(item.id)
        item.quantity = current_fifo_total

        return True

    except Exception as e:
        logger.error(f"Error in deductive operation: {str(e)}")
        return False


def _internal_add_fifo_entry_enhanced(item_id, quantity, change_type, unit, notes, cost_per_unit, created_by, expiration_date=None, shelf_life_days=None, **kwargs):
    """Enhanced FIFO entry creation with full parameter support"""
    try:
        item = db.session.get(InventoryItem, item_id)
        if not item:
            return False, "Item not found"

        # Create FIFO history entry
        history_entry = UnifiedInventoryHistory(
            inventory_item_id=item_id,
            organization_id=item.organization_id,
            change_type=change_type,
            quantity_change=quantity,
            remaining_quantity=quantity,
            unit_cost=cost_per_unit,
            notes=notes,
            created_by=created_by,
            timestamp=TimezoneUtils.utc_now(),
            **kwargs
        )

        # Handle expiration if applicable
        if expiration_date:
            history_entry.expiration_date = expiration_date
        elif shelf_life_days and shelf_life_days > 0:
            history_entry.shelf_life_days = shelf_life_days
            history_entry.expiration_date = TimezoneUtils.utc_now() + timedelta(days=shelf_life_days)

        db.session.add(history_entry)

        # Update item quantity
        item.quantity += quantity

        logger.info(f"FIFO: Updating inventory item {item_id} quantity: {item.quantity - quantity} → {item.quantity}")

        return True, f"Added {quantity} {unit}"

    except Exception as e:
        logger.error(f"Error in _internal_add_fifo_entry_enhanced: {str(e)}")
        return False, str(e)


def _calculate_deduction_plan_internal(item_id, quantity, change_type):
    """Calculate FIFO deduction plan"""
    try:
        available_lots = UnifiedInventoryHistory.query.filter(
            UnifiedInventoryHistory.inventory_item_id == item_id,
            UnifiedInventoryHistory.remaining_quantity > 0
        ).order_by(UnifiedInventoryHistory.timestamp.asc()).all()

        total_available = sum(lot.remaining_quantity for lot in available_lots)

        if total_available < quantity:
            return None, f"Insufficient inventory: need {quantity}, have {total_available}"

        deduction_plan = []
        remaining_to_deduct = quantity

        for lot in available_lots:
            if remaining_to_deduct <= 0:
                break

            if lot.remaining_quantity > 0:
                deduct_from_lot = min(lot.remaining_quantity, remaining_to_deduct)
                deduction_plan.append({
                    'lot_id': lot.id,
                    'deduct_quantity': deduct_from_lot,
                    'lot_remaining_before': lot.remaining_quantity
                })
                remaining_to_deduct -= deduct_from_lot

        return deduction_plan, None

    except Exception as e:
        logger.error(f"Error calculating deduction plan: {str(e)}")
        return None, str(e)


def _execute_deduction_plan_internal(deduction_plan, item_id):
    """Execute the FIFO deduction plan"""
    try:
        for step in deduction_plan:
            lot = db.session.get(UnifiedInventoryHistory, step['lot_id'])
            if lot:
                lot.remaining_quantity -= step['deduct_quantity']

        return True, None

    except Exception as e:
        logger.error(f"Error executing deduction plan: {str(e)}")
        return False, str(e)


def _record_deduction_plan_internal(item_id, deduction_plan, change_type, notes, created_by=None, **kwargs):
    """Record the deduction in audit trail"""
    try:
        item = db.session.get(InventoryItem, item_id)
        total_deducted = sum(step['deduct_quantity'] for step in deduction_plan)

        history_entry = UnifiedInventoryHistory(
            inventory_item_id=item_id,
            organization_id=item.organization_id,
            change_type=change_type,
            quantity_change=-total_deducted,
            remaining_quantity=0,
            notes=notes,
            created_by=created_by,
            timestamp=TimezoneUtils.utc_now(),
            **kwargs
        )

        db.session.add(history_entry)
        return True

    except Exception as e:
        logger.error(f"Error recording deduction: {str(e)}")
        return False


def calculate_current_fifo_total(item_id):
    """Calculate current FIFO total for validation"""
    fifo_entries = UnifiedInventoryHistory.query.filter(
        and_(
            UnifiedInventoryHistory.inventory_item_id == item_id,
            UnifiedInventoryHistory.remaining_quantity > 0
        )
    ).all()

    return sum(float(entry.remaining_quantity) for entry in fifo_entries)


def credit_specific_lot(lot_id, quantity, notes=None, created_by=None):
    """Credit back to a specific FIFO lot (used for reservation releases)"""
    from app.models import UnifiedInventoryHistory, db

    try:
        entry = UnifiedInventoryHistory.query.get(lot_id)
        if not entry:
            return False, "FIFO lot not found"

        # Add back to the specific lot
        entry.remaining_quantity = float(entry.remaining_quantity) + float(quantity)

        # Update item quantity
        from app.models import InventoryItem
        item = InventoryItem.query.get(entry.inventory_item_id)
        if item:
            item.quantity = float(item.quantity) + float(quantity)

        db.session.commit()
        return True, f"Credited {quantity} back to lot {lot_id}"

    except Exception as e:
        db.session.rollback()
        return False, f"Error crediting lot: {str(e)}"