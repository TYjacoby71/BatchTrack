
from flask_login import current_user  
from app.models import db, InventoryItem, UnifiedInventoryHistory
from sqlalchemy import and_
import logging

logger = logging.getLogger(__name__)


def handle_recount_adjustment(item_id, target_quantity, notes=None, created_by=None, item_type='ingredient'):
    """
    Recount sets absolute target quantity using FIFO service for lot management:

    POSITIVE RECOUNT (increase):
    - Use FIFO service to get refillable lots and fill them first
    - Create new lot with overflow if needed
    - Log history entry for each lot affected

    NEGATIVE RECOUNT (decrease):
    - Use FIFO service to calculate deduction plan from all lots
    - Execute deduction plan through FIFO service
    - Log history entries for audit trail

    ALWAYS: Sync item.quantity with sum of all remaining_quantity values
    """
    try:
        # Get the item
        item = InventoryItem.query.get(item_id)
        if not item:
            raise ValueError(f"Inventory item not found for ID: {item_id}")

        # Organization scoping check
        if current_user and current_user.is_authenticated and current_user.organization_id:
            if item.organization_id and item.organization_id != current_user.organization_id:
                raise ValueError("Access denied: Item does not belong to your organization")
            org_id = current_user.organization_id
        else:
            org_id = item.organization_id

        current_qty = float(item.quantity or 0.0)
        target_qty = float(target_quantity or 0.0)

        if abs(current_qty - target_qty) < 0.001:
            return True  # No change needed

        delta = target_qty - current_qty
        history_unit = 'count' if getattr(item, 'type', None) == 'container' else item.unit

        print(f"RECOUNT: {item.name} from {current_qty} to {target_qty} (delta: {delta})")

        # Import FIFO service functions
        from ._fifo_ops import (
            identify_lots, _calculate_addition_plan_internal, 
            _execute_addition_plan_internal, _record_addition_plan_internal,
            _calculate_deduction_plan_internal, _execute_deduction_plan_internal,
            _record_deduction_plan_internal, _internal_add_fifo_entry_enhanced
        )

        # INCREASING quantity: use FIFO service for lot refilling
        if delta > 0:
            print(f"RECOUNT: Increasing by {delta}")
            
            # Get addition plan from FIFO service
            addition_plan, remaining_overflow = _calculate_addition_plan_internal(
                item_id, delta, 'recount'
            )
            
            # Execute the addition plan
            if addition_plan:
                _execute_addition_plan_internal(addition_plan, item_id)
                _record_addition_plan_internal(
                    item_id, addition_plan, 'recount', 
                    notes or 'Recount refill', created_by=created_by
                )
                print(f"RECOUNT: Refilled {len(addition_plan)} existing lots")

            # Create overflow lot if needed
            if remaining_overflow > 0:
                success, error = _internal_add_fifo_entry_enhanced(
                    item_id=item_id,
                    quantity=remaining_overflow,
                    change_type='recount',
                    unit=history_unit,
                    notes=f"{notes or 'Recount overflow'} - New lot for overflow",
                    cost_per_unit=item.cost_per_unit,
                    created_by=created_by
                )
                if not success:
                    raise ValueError(f"Failed to create overflow lot: {error}")
                print(f"RECOUNT: Created overflow lot with {remaining_overflow}")

        # DECREASING quantity: use FIFO service for deduction planning
        else:
            to_remove = abs(delta)
            print(f"RECOUNT: Decreasing by {to_remove}")
            
            # Get deduction plan from FIFO service
            deduction_plan, error = _calculate_deduction_plan_internal(
                item_id, to_remove, 'recount'
            )
            
            if error:
                raise ValueError(f"Cannot complete recount: {error}")

            # Execute the deduction plan
            if deduction_plan:
                _execute_deduction_plan_internal(deduction_plan, item_id)
                _record_deduction_plan_internal(
                    item_id, deduction_plan, 'recount',
                    notes or 'Recount deduction', created_by=created_by
                )
                print(f"RECOUNT: Deducted from {len(deduction_plan)} lots")

        # Set item to target quantity (absolute sync)
        item.quantity = target_qty
        db.session.commit()

        # Validate final sync state using FIFO service
        current_lots = identify_lots(item_id)
        final_fifo_total = sum(float(lot.remaining_quantity) for lot in current_lots)

        print(f"RECOUNT FINAL: inventory={item.quantity}, fifo_total={final_fifo_total}")

        if abs(item.quantity - final_fifo_total) > 0.001:
            raise ValueError(f"CRITICAL: FIFO sync failed after recount - inventory={item.quantity}, fifo_total={final_fifo_total}")

        return True

    except Exception as e:
        db.session.rollback()
        print(f"RECOUNT ERROR: {str(e)}")
        raise e
