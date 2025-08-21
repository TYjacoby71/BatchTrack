import logging
from datetime import datetime, timedelta
from decimal import Decimal
from app.models import db, InventoryItem, UnifiedInventoryHistory
from app.utils.timezone_utils import TimezoneUtils
from sqlalchemy import and_

logger = logging.getLogger(__name__)


def _internal_add_fifo_entry_enhanced(
    item_id: int,
    quantity: float,
    change_type: str,
    unit: str = None,
    notes: str = None,
    cost_per_unit: float = None,
    created_by: int = None,
    expiration_date=None,
    shelf_life_days: int = None,
    **kwargs
) -> tuple:
    """
    Enhanced FIFO entry creation with comprehensive field support.
    """
    try:
        # Get item for validation and defaults
        item = db.session.get(InventoryItem, item_id)
        if not item:
            return False, f"Item {item_id} not found"

        # Use item's unit if not provided - ensure we always have a unit
        if not unit:
            unit = item.unit if item.unit else 'count'

        # Use item's cost if not provided
        if cost_per_unit is None:
            cost_per_unit = item.cost_per_unit or 0.0

        # For additive operations, remaining_quantity = quantity_change
        remaining_qty = quantity
        
        # Generate FIFO code with enhanced logic for recount operations
        from app.utils.fifo_generator import get_fifo_prefix
        fifo_prefix = get_fifo_prefix(change_type, remaining_qty > 0)
        
        # Filter out invalid kwargs for UnifiedInventoryHistory
        valid_kwargs = {}
        valid_fields = {'expiration_date', 'shelf_life_days', 'fifo_reference_id'}
        for key, value in kwargs.items():
            if key in valid_fields:
                valid_kwargs[key] = value

        # Create the FIFO history entry
        fifo_entry = UnifiedInventoryHistory(
            inventory_item_id=item_id,
            timestamp=datetime.utcnow(),
            change_type=change_type,  # Always use the actual change_type for audit trail
            quantity_change=quantity,
            unit=unit,
            unit_cost=cost_per_unit,
            remaining_quantity=remaining_qty,
            notes=notes or 'FIFO entry',
            created_by=created_by,
            quantity_used=0.0,
            organization_id=item.organization_id,
            **valid_kwargs
        )

        # Handle expiration if applicable
        if expiration_date:
            fifo_entry.expiration_date = expiration_date
        elif shelf_life_days and shelf_life_days > 0:
            fifo_entry.shelf_life_days = shelf_life_days
            fifo_entry.expiration_date = TimezoneUtils.utc_now() + timedelta(days=shelf_life_days)

        db.session.add(fifo_entry)

        # Update item quantity
        item.quantity += quantity

        logger.info(f"FIFO: Added {quantity} {unit} to item {item_id}, new total: {item.quantity}")

        return True, f"Added {quantity} {unit}"

    except Exception as e:
        logger.error(f"Error in _internal_add_fifo_entry_enhanced: {str(e)}")
        return False, str(e)


def _handle_deductive_operation_internal(item, quantity, change_type, notes, created_by, **kwargs):
    """Handle deductive operations using FIFO logic"""
    try:
        # Get deduction plan from FIFO service
        deduction_plan, error = _calculate_deduction_plan_internal(
            item.id, abs(quantity), change_type
        )

        if error:
            logger.error(f"Deduction planning failed: {error}")
            return False, error

        if not deduction_plan:
            logger.warning(f"No deduction plan generated for {item.id}")
            return False, "Insufficient inventory"

        # Execute deduction plan
        success, error = _execute_deduction_plan_internal(deduction_plan, item.id)
        if not success:
            logger.error(f"Deduction execution failed: {error}")
            return False, error

        # Record audit trail
        success = _record_deduction_plan_internal(
            item.id, deduction_plan, change_type, notes, 
            created_by=created_by, **kwargs
        )
        if not success:
            logger.error(f"Deduction recording failed")
            return False, "Failed to record deduction"

        # Sync item quantity to FIFO total
        current_fifo_total = calculate_current_fifo_total(item.id)
        item.quantity = current_fifo_total

        return True, f"Deducted {quantity} {getattr(item, 'unit', 'units')}"

    except Exception as e:
        logger.error(f"Error in deductive operation: {str(e)}")
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

        # Filter out invalid kwargs for UnifiedInventoryHistory
        valid_kwargs = {}
        valid_fields = {'unit', 'unit_cost', 'expiration_date', 'shelf_life_days', 'fifo_reference_id'}
        for key, value in kwargs.items():
            if key in valid_fields:
                valid_kwargs[key] = value

        history_entry = UnifiedInventoryHistory(
            inventory_item_id=item_id,
            organization_id=item.organization_id,
            change_type=change_type,
            quantity_change=-total_deducted,
            remaining_quantity=0,
            notes=notes,
            created_by=created_by,
            timestamp=TimezoneUtils.utc_now(),
            unit=item.unit if item.unit else 'count',
            unit_cost=item.cost_per_unit or 0.0,
            **valid_kwargs
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
    try:
        entry = UnifiedInventoryHistory.query.get(lot_id)
        if not entry:
            return False, "FIFO lot not found"

        # Add back to the specific lot
        entry.remaining_quantity = float(entry.remaining_quantity) + float(quantity)

        # Update item quantity
        item = InventoryItem.query.get(entry.inventory_item_id)
        if item:
            item.quantity = float(item.quantity) + float(quantity)

        db.session.commit()
        return True, f"Credited {quantity} back to lot {lot_id}"

    except Exception as e:
        db.session.rollback()
        return False, f"Error crediting lot: {str(e)}"