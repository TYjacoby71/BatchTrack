
import logging
from app.models import db
from ._fifo_ops import calculate_current_fifo_total, _internal_add_fifo_entry_enhanced, _handle_deductive_operation_internal

logger = logging.getLogger(__name__)


def handle_recount(item, quantity, notes=None, created_by=None, **kwargs):
    """
    CLEAN recount handler that works ONLY through FIFO operations.
    
    This ensures FIFO is the single source of truth for history entries.
    """
    try:
        # Get current FIFO total for comparison
        current_fifo_total = calculate_current_fifo_total(item.id)
        target_quantity = float(quantity)
        delta = target_quantity - current_fifo_total

        logger.info(f"RECOUNT: {item.name} - FIFO total: {current_fifo_total}, target: {target_quantity}, delta: {delta}")

        # No change needed
        if abs(delta) < 0.001:
            # Sync item.quantity to FIFO total for consistency
            item.quantity = current_fifo_total
            return True, f"Inventory already at target quantity: {target_quantity}"

        # Apply the delta using ONLY FIFO operations
        if delta > 0:
            # Need to add inventory - call FIFO additive operation
            success, error = _internal_add_fifo_entry_enhanced(
                item_id=item.id,
                quantity=delta,
                change_type='recount_addition',
                unit=getattr(item, 'unit', 'count'),
                notes=notes or f'Recount increase: +{delta}',
                cost_per_unit=item.cost_per_unit,
                created_by=created_by,
                **kwargs
            )
            
            if success:
                return True, f"Recount added {delta} {getattr(item, 'unit', 'units')}"
            else:
                return False, error
                
        else:
            # Need to deduct inventory - call FIFO deductive operation
            success = _handle_deductive_operation_internal(
                item=item,
                quantity=abs(delta),
                change_type='recount_deduction',
                notes=notes or f'Recount decrease: -{abs(delta)}',
                created_by=created_by,
                **kwargs
            )
            
            if success:
                return True, f"Recount removed {abs(delta)} {getattr(item, 'unit', 'units')}"
            else:
                return False, "Insufficient inventory for recount adjustment"

    except Exception as e:
        logger.error(f"RECOUNT ERROR: {str(e)}")
        return False, str(e)
