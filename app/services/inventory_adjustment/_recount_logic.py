
import logging
from app.models import db, UnifiedInventoryHistory
from ._fifo_ops import calculate_current_fifo_total, _internal_add_fifo_entry_enhanced
from sqlalchemy import and_

logger = logging.getLogger(__name__)


def handle_recount(item, quantity, notes=None, created_by=None, **kwargs):
    """
    SOPHISTICATED recount handler that:
    1. First fills existing FIFO lots with remaining capacity
    2. Then creates new lots for any overflow
    3. Creates separate history entries for each operation
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

        if delta > 0:
            # Need to add inventory - use sophisticated filling logic
            return _handle_recount_increase(item, delta, notes, created_by, **kwargs)
        else:
            # Need to deduct inventory - use standard deductive logic
            from ._fifo_ops import _handle_deductive_operation_internal
            success = _handle_deductive_operation_internal(
                item=item,
                quantity=abs(delta),
                change_type='recount',
                notes=notes or f'Recount adjustment: -{abs(delta)}',
                created_by=created_by
            )

            if success:
                return True, f"Recount removed {abs(delta)} {getattr(item, 'unit', 'units')}"
            else:
                return False, "Insufficient inventory for recount adjustment"

    except Exception as e:
        logger.error(f"RECOUNT ERROR: {str(e)}")
        return False, str(e)


def _handle_recount_increase(item, delta_needed, notes, created_by, **kwargs):
    """
    Handle recount increase by:
    1. First filling existing lots with remaining capacity
    2. Then creating new lots for overflow
    """
    try:
        # Find existing lots with remaining capacity - fill newest first (front to back)
        existing_lots = UnifiedInventoryHistory.query.filter(
            and_(
                UnifiedInventoryHistory.inventory_item_id == item.id,
                UnifiedInventoryHistory.remaining_quantity > 0,
                UnifiedInventoryHistory.change_type.in_(['restock', 'initial_stock', 'manual_addition', 'finished_batch', 'recount'])
            )
        ).order_by(UnifiedInventoryHistory.timestamp.desc()).all()

        # Calculate total remaining capacity in existing lots
        total_capacity = sum(
            (lot.quantity_change - lot.remaining_quantity) 
            for lot in existing_lots 
            if lot.quantity_change > lot.remaining_quantity
        )
        
        logger.info(f"RECOUNT INCREASE: Need {delta_needed}, found {len(existing_lots)} existing lots with {total_capacity} total capacity")

        remaining_to_add = delta_needed
        entries_created = 0

        # Phase 1: Fill existing lots that have capacity
        for lot in existing_lots:
            if remaining_to_add <= 0:
                break
                
            # Check if this lot has capacity (original quantity > current remaining)
            original_quantity = lot.quantity_change
            current_remaining = lot.remaining_quantity
            
            # Only lots that were partially consumed have capacity
            if original_quantity > current_remaining:
                capacity = original_quantity - current_remaining
                fill_amount = min(capacity, remaining_to_add)
                
                if fill_amount > 0:
                    # Add back to this specific lot
                    lot.remaining_quantity += fill_amount
                    remaining_to_add -= fill_amount
                    
                    # Create a history entry for this refill
                    refill_entry = UnifiedInventoryHistory(
                        inventory_item_id=item.id,
                        organization_id=item.organization_id,
                        change_type='recount',
                        quantity_change=fill_amount,
                        unit=getattr(item, 'unit', 'count'),
                        unit_cost=item.cost_per_unit,
                        remaining_quantity=0,  # This is a consumption record, not a lot
                        fifo_reference_id=lot.id,  # Reference the lot being refilled
                        notes=f'Recount refill to existing lot #{lot.id}: +{fill_amount}',
                        created_by=created_by
                    )
                    
                    # Generate RCN code for recount operations that don't create lots
                    from app.utils.fifo_generator import generate_fifo_code
                    refill_entry.fifo_code = generate_fifo_code('recount', 0)  # 0 remaining = RCN prefix
                    
                    db.session.add(refill_entry)
                    entries_created += 1
                    
                    logger.info(f"RECOUNT: Filled {fill_amount} into existing lot #{lot.id}")

        # Phase 2: Create new lot for any remaining overflow
        if remaining_to_add > 0:
            success, error = _internal_add_fifo_entry_enhanced(
                item_id=item.id,
                quantity=remaining_to_add,
                change_type='recount',
                unit=getattr(item, 'unit', 'count'),
                notes=f'Recount overflow - new lot: +{remaining_to_add}',
                cost_per_unit=item.cost_per_unit,
                created_by=created_by,
                **kwargs
            )
            
            if not success:
                return False, f"Failed to create overflow lot: {error}"
                
            entries_created += 1
            logger.info(f"RECOUNT: Created new lot with {remaining_to_add} units")

        # Update item quantity
        item.quantity += delta_needed

        return True, f"Recount added {delta_needed} {getattr(item, 'unit', 'units')} across {entries_created} operations"

    except Exception as e:
        logger.error(f"Error in recount increase: {str(e)}")
        return False, str(e)
