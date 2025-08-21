
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from app.models import db, InventoryItem, UnifiedInventoryHistory
from app.utils.timezone_utils import TimezoneUtils

logger = logging.getLogger(__name__)


# ========== SPECIALIST HANDLER FUNCTIONS ==========

def handle_restock(item, quantity, notes=None, created_by=None, cost_override=None, **kwargs):
    """Handle restocking inventory - adds new FIFO lot"""
    try:
        cost_per_unit = cost_override if cost_override is not None else item.cost_per_unit
        
        success, error = _internal_add_fifo_entry_enhanced(
            item_id=item.id,
            quantity=quantity,
            change_type='restock',
            unit=getattr(item, 'unit', 'count'),
            notes=notes,
            cost_per_unit=cost_per_unit,
            created_by=created_by,
            **kwargs
        )
        
        if success:
            return True, f"Restocked {quantity} {getattr(item, 'unit', 'units')}"
        return False, error
        
    except Exception as e:
        logger.error(f"Error in handle_restock: {str(e)}")
        return False, str(e)


def handle_manual_addition(item, quantity, notes=None, created_by=None, **kwargs):
    """Handle manual inventory addition"""
    try:
        success, error = _internal_add_fifo_entry_enhanced(
            item_id=item.id,
            quantity=quantity,
            change_type='manual_addition',
            unit=getattr(item, 'unit', 'count'),
            notes=notes,
            cost_per_unit=item.cost_per_unit,
            created_by=created_by,
            **kwargs
        )
        
        if success:
            return True, f"Added {quantity} {getattr(item, 'unit', 'units')} manually"
        return False, error
        
    except Exception as e:
        logger.error(f"Error in handle_manual_addition: {str(e)}")
        return False, str(e)


def handle_returned(item, quantity, notes=None, created_by=None, **kwargs):
    """Handle returned inventory"""
    try:
        success, error = _internal_add_fifo_entry_enhanced(
            item_id=item.id,
            quantity=quantity,
            change_type='returned',
            unit=getattr(item, 'unit', 'count'),
            notes=notes,
            cost_per_unit=item.cost_per_unit,
            created_by=created_by,
            **kwargs
        )
        
        if success:
            return True, f"Returned {quantity} {getattr(item, 'unit', 'units')}"
        return False, error
        
    except Exception as e:
        logger.error(f"Error in handle_returned: {str(e)}")
        return False, str(e)


def handle_refunded(item, quantity, notes=None, created_by=None, **kwargs):
    """Handle refunded inventory"""
    try:
        success, error = _internal_add_fifo_entry_enhanced(
            item_id=item.id,
            quantity=quantity,
            change_type='refunded',
            unit=getattr(item, 'unit', 'count'),
            notes=notes,
            cost_per_unit=item.cost_per_unit,
            created_by=created_by,
            **kwargs
        )
        
        if success:
            return True, f"Refunded {quantity} {getattr(item, 'unit', 'units')}"
        return False, error
        
    except Exception as e:
        logger.error(f"Error in handle_refunded: {str(e)}")
        return False, str(e)


def handle_finished_batch(item, quantity, notes=None, created_by=None, batch_id=None, **kwargs):
    """Handle finished batch addition"""
    try:
        success, error = _internal_add_fifo_entry_enhanced(
            item_id=item.id,
            quantity=quantity,
            change_type='finished_batch',
            unit=getattr(item, 'unit', 'count'),
            notes=notes,
            cost_per_unit=item.cost_per_unit,
            created_by=created_by,
            batch_id=batch_id,
            **kwargs
        )
        
        if success:
            return True, f"Added {quantity} {getattr(item, 'unit', 'units')} from finished batch"
        return False, error
        
    except Exception as e:
        logger.error(f"Error in handle_finished_batch: {str(e)}")
        return False, str(e)


def handle_use(item, quantity, notes=None, created_by=None, **kwargs):
    """Handle using inventory (generic deduction)"""
    try:
        success = _handle_deductive_operation(
            item, quantity, 'use', notes, created_by, **kwargs
        )
        
        if success:
            return True, f"Used {quantity} {getattr(item, 'unit', 'units')}"
        return False, "Insufficient inventory"
        
    except Exception as e:
        logger.error(f"Error in handle_use: {str(e)}")
        return False, str(e)


def handle_batch(item, quantity, notes=None, created_by=None, batch_id=None, **kwargs):
    """Handle batch consumption"""
    try:
        success = _handle_deductive_operation(
            item, quantity, 'batch', notes, created_by, batch_id=batch_id, **kwargs
        )
        
        if success:
            return True, f"Used {quantity} {getattr(item, 'unit', 'units')} in batch"
        return False, "Insufficient inventory"
        
    except Exception as e:
        logger.error(f"Error in handle_batch: {str(e)}")
        return False, str(e)


def handle_sale(item, quantity, notes=None, created_by=None, sale_price=None, customer=None, order_id=None, **kwargs):
    """Handle sale deduction"""
    try:
        success = _handle_deductive_operation(
            item, quantity, 'sale', notes, created_by, 
            sale_price=sale_price, customer=customer, order_id=order_id, **kwargs
        )
        
        if success:
            return True, f"Sold {quantity} {getattr(item, 'unit', 'units')}"
        return False, "Insufficient inventory"
        
    except Exception as e:
        logger.error(f"Error in handle_sale: {str(e)}")
        return False, str(e)


def handle_spoil(item, quantity, notes=None, created_by=None, **kwargs):
    """Handle spoilage deduction"""
    try:
        success = _handle_deductive_operation(
            item, quantity, 'spoil', notes, created_by, **kwargs
        )
        
        if success:
            return True, f"Marked {quantity} {getattr(item, 'unit', 'units')} as spoiled"
        return False, "Insufficient inventory"
        
    except Exception as e:
        logger.error(f"Error in handle_spoil: {str(e)}")
        return False, str(e)


def handle_trash(item, quantity, notes=None, created_by=None, **kwargs):
    """Handle trash deduction"""
    try:
        success = _handle_deductive_operation(
            item, quantity, 'trash', notes, created_by, **kwargs
        )
        
        if success:
            return True, f"Trashed {quantity} {getattr(item, 'unit', 'units')}"
        return False, "Insufficient inventory"
        
    except Exception as e:
        logger.error(f"Error in handle_trash: {str(e)}")
        return False, str(e)


def handle_expired(item, quantity, notes=None, created_by=None, **kwargs):
    """Handle expired inventory deduction"""
    try:
        success = _handle_deductive_operation(
            item, quantity, 'expired', notes, created_by, **kwargs
        )
        
        if success:
            return True, f"Removed {quantity} {getattr(item, 'unit', 'units')} (expired)"
        return False, "Insufficient inventory"
        
    except Exception as e:
        logger.error(f"Error in handle_expired: {str(e)}")
        return False, str(e)


def handle_damaged(item, quantity, notes=None, created_by=None, **kwargs):
    """Handle damaged inventory deduction"""
    try:
        success = _handle_deductive_operation(
            item, quantity, 'damaged', notes, created_by, **kwargs
        )
        
        if success:
            return True, f"Removed {quantity} {getattr(item, 'unit', 'units')} (damaged)"
        return False, "Insufficient inventory"
        
    except Exception as e:
        logger.error(f"Error in handle_damaged: {str(e)}")
        return False, str(e)


def handle_quality_fail(item, quantity, notes=None, created_by=None, **kwargs):
    """Handle quality failure deduction"""
    try:
        success = _handle_deductive_operation(
            item, quantity, 'quality_fail', notes, created_by, **kwargs
        )
        
        if success:
            return True, f"Removed {quantity} {getattr(item, 'unit', 'units')} (quality fail)"
        return False, "Insufficient inventory"
        
    except Exception as e:
        logger.error(f"Error in handle_quality_fail: {str(e)}")
        return False, str(e)


def handle_sample(item, quantity, notes=None, created_by=None, **kwargs):
    """Handle sample deduction"""
    try:
        success = _handle_deductive_operation(
            item, quantity, 'sample', notes, created_by, **kwargs
        )
        
        if success:
            return True, f"Used {quantity} {getattr(item, 'unit', 'units')} for sample"
        return False, "Insufficient inventory"
        
    except Exception as e:
        logger.error(f"Error in handle_sample: {str(e)}")
        return False, str(e)


def handle_tester(item, quantity, notes=None, created_by=None, **kwargs):
    """Handle tester deduction"""
    try:
        success = _handle_deductive_operation(
            item, quantity, 'tester', notes, created_by, **kwargs
        )
        
        if success:
            return True, f"Used {quantity} {getattr(item, 'unit', 'units')} for tester"
        return False, "Insufficient inventory"
        
    except Exception as e:
        logger.error(f"Error in handle_tester: {str(e)}")
        return False, str(e)


def handle_gift(item, quantity, notes=None, created_by=None, **kwargs):
    """Handle gift deduction"""
    try:
        success = _handle_deductive_operation(
            item, quantity, 'gift', notes, created_by, **kwargs
        )
        
        if success:
            return True, f"Gave {quantity} {getattr(item, 'unit', 'units')} as gift"
        return False, "Insufficient inventory"
        
    except Exception as e:
        logger.error(f"Error in handle_gift: {str(e)}")
        return False, str(e)


def handle_reserved(item, quantity, notes=None, created_by=None, order_id=None, **kwargs):
    """Handle reservation deduction"""
    try:
        success = _handle_deductive_operation(
            item, quantity, 'reserved', notes, created_by, order_id=order_id, **kwargs
        )
        
        if success:
            return True, f"Reserved {quantity} {getattr(item, 'unit', 'units')}"
        return False, "Insufficient inventory"
        
    except Exception as e:
        logger.error(f"Error in handle_reserved: {str(e)}")
        return False, str(e)


def handle_unreserved(item, quantity, notes=None, created_by=None, **kwargs):
    """Handle unreservation (additive)"""
    try:
        success, error = _internal_add_fifo_entry_enhanced(
            item_id=item.id,
            quantity=quantity,
            change_type='unreserved',
            unit=getattr(item, 'unit', 'count'),
            notes=notes,
            cost_per_unit=item.cost_per_unit,
            created_by=created_by,
            **kwargs
        )
        
        if success:
            return True, f"Unreserved {quantity} {getattr(item, 'unit', 'units')}"
        return False, error
        
    except Exception as e:
        logger.error(f"Error in handle_unreserved: {str(e)}")
        return False, str(e)


def handle_cost_override(item, quantity, notes=None, created_by=None, cost_override=None, **kwargs):
    """Handle cost override (no quantity change)"""
    try:
        if cost_override is not None:
            item.cost_per_unit = cost_override
            db.session.commit()
            return True, f"Updated cost to {cost_override}"
        return False, "No cost override provided"
        
    except Exception as e:
        logger.error(f"Error in handle_cost_override: {str(e)}")
        return False, str(e)


# ========== INTERNAL HELPER FUNCTIONS ==========

def _handle_deductive_operation(item, quantity, change_type, notes, created_by, **kwargs):
    """Handle all deductive operations using FIFO service"""
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


# ========== EXISTING FIFO HELPER FUNCTIONS ==========
# (Keep all the existing helper functions like _internal_add_fifo_entry_enhanced, etc.)

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
    """Calculate current total from FIFO lots"""
    try:
        total = db.session.query(
            db.func.sum(UnifiedInventoryHistory.remaining_quantity)
        ).filter(
            UnifiedInventoryHistory.inventory_item_id == item_id,
            UnifiedInventoryHistory.remaining_quantity > 0
        ).scalar() or 0.0
        
        return float(total)
        
    except Exception as e:
        logger.error(f"Error calculating FIFO total: {str(e)}")
        return 0.0
