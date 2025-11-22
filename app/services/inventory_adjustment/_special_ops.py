"""
Special Operations Handler

Handles special inventory operations that don't follow standard FIFO patterns:
- Cost override operations
- Unit conversion operations
"""

import logging
from app.models import db
from app.utils.inventory_event_code_generator import generate_inventory_event_code
from ._fifo_ops import create_new_fifo_lot, deduct_fifo_inventory # Kept for local use within this file and added deduct_fifo_inventory
from sqlalchemy import and_

logger = logging.getLogger(__name__)

def handle_cost_override(item, quantity, change_type, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, customer=None, sale_price=None, order_id=None, target_quantity=None, unit=None, **kwargs):
    """
    Handle cost override operations.

    This updates the cost_per_unit of an inventory item without affecting quantities.
    """
    try:
        if cost_override is None:
            return False, "Cost override operation requires a cost_override value"

        old_cost = item.cost_per_unit or 0.0
        item.cost_per_unit = float(cost_override)

        # Create history entry for audit trail
        from app.models import UnifiedInventoryHistory
        history_entry = UnifiedInventoryHistory(
            inventory_item_id=item.id,
            change_type='cost_override',
            quantity_delta=0.0,  # No quantity change
            quantity_after=item.quantity or 0.0,
            unit=item.unit or 'count',
            cost_per_unit=float(cost_override),
            notes=notes or f"Cost updated from {old_cost} to {cost_override}",
            created_by=created_by
        )

        db.session.add(item)
        db.session.add(history_entry)

        logger.info(f"COST OVERRIDE: Item {item.id} cost updated from {old_cost} to {cost_override}")
        return True, f"Cost updated from {old_cost} to {cost_override} per {item.unit or 'unit'}"

    except Exception as e:
        logger.error(f"COST OVERRIDE ERROR: {str(e)}")
        return False, str(e)

def handle_unit_conversion(item, quantity, change_type, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, customer=None, sale_price=None, order_id=None, target_quantity=None, unit=None, **kwargs):
    """
    Handle unit conversion operations via the canonical ConversionEngine (UUCS).

    Converts the provided quantity from `unit` to the item's base `item.unit` and logs a no-op
    inventory event to document the conversion intent (since conversion itself shouldn't change stock).
    """
    try:
        from app.services.unit_conversion import ConversionEngine
        from app.models import UnifiedInventoryHistory

        if unit is None or unit == item.unit:
            # Nothing to convert
            return True, "No conversion needed"

        # Probe conversion and compute converted value (does not change quantity here)
        conv = ConversionEngine.convert_units(
            amount=float(quantity or 0.0),
            from_unit=unit,
            to_unit=item.unit,
            ingredient_id=item.id,
            density=item.density
        )

        if not conv or conv.get('converted_value') is None:
            return False, f"Cannot convert {unit} to {item.unit}"

        # Log informational event; quantity_change = 0 to preserve stock, record mapping context
        evt = UnifiedInventoryHistory(
            inventory_item_id=item.id,
            change_type='unit_conversion',
            quantity_change=0.0,
            unit=item.unit,
            notes=(notes or f"Unit conversion verified: {quantity} {unit} -> {conv['converted_value']} {item.unit}"),
            created_by=created_by,
            organization_id=item.organization_id
        )
        db.session.add(evt)
        logger.info(f"UNIT CONVERSION: Verified {quantity} {unit} -> {conv['converted_value']} {item.unit} for item {item.id}")
        return True, "Unit conversion verified"

    except Exception as e:
        logger.error(f"UNIT CONVERSION ERROR: {str(e)}")
        return False, str(e)

def handle_recount(item, quantity, change_type, notes=None, created_by=None, target_quantity=None, **kwargs):
    """
    Handle inventory recount with complete FIFO reconciliation.
    
    RECOUNT RULES:
    1. Recount to ZERO: Drain all FIFO lots to zero and sync
    2. Recount to OTHER: Adjust inventory and FIFO accordingly
    3. OVERFLOW: First fill existing lots to capacity, then create new lots
    4. EVENT CODES: Always use recount's own RCN-xxx event codes
    5. LOT REFERENCES: Always reference affected lot ID in credited/debited column
    """
    try:
        from ._fifo_ops import get_item_lots, create_new_fifo_lot
        from app.models import UnifiedInventoryHistory
        from app.models.inventory_lot import InventoryLot

        # For recounts, the target_quantity is the desired final quantity
        if target_quantity is None:
            target_quantity = quantity

        current_quantity = float(item.quantity)
        target_qty = float(target_quantity)
        delta = target_qty - current_quantity

        logger.info(f"RECOUNT: Item {item.id} current={current_quantity}, target={target_qty}, delta={delta}")

        recount_notes = f"Inventory recount: {current_quantity} -> {target_qty}"
        if notes:
            recount_notes += f" | {notes}"

        if delta == 0:
            # No change needed - just sync verification
            logger.info(f"RECOUNT: No adjustment needed for item {item.id}")
            return True, f"Inventory verified at {target_qty}"

        elif delta < 0:
            # SCENARIO 1: RECOUNT TO ZERO OR DEDUCTIVE RECOUNT
            # Manually drain FIFO lots using recount event codes (not delegating to deduct_fifo_inventory)
            abs_delta = abs(delta)
            logger.info(f"RECOUNT: Deducting {abs_delta} using recount-specific FIFO drainage")

            # Get active lots ordered by FIFO (oldest first)
            active_lots = InventoryLot.query.filter(
                and_(
                    InventoryLot.inventory_item_id == item.id,
                    InventoryLot.organization_id == item.organization_id,
                    InventoryLot.remaining_quantity > 0
                )
            ).order_by(InventoryLot.received_date.asc()).all()

            # Calculate total available quantity
            total_available = sum(float(lot.remaining_quantity) for lot in active_lots)
            
            if total_available < abs_delta:
                return False, f"Cannot recount: need to deduct {abs_delta}, but only {total_available} available"

            # Drain lots using FIFO order with recount-specific event codes
            remaining_to_deduct = abs_delta
            lots_affected = 0

            for lot in active_lots:
                if remaining_to_deduct <= 0:
                    break

                # Calculate how much to deduct from this lot
                deduct_from_lot = min(float(lot.remaining_quantity), remaining_to_deduct)

                # Update the lot's remaining quantity
                lot.remaining_quantity = float(lot.remaining_quantity) - deduct_from_lot
                db.session.add(lot)

                # Create RECOUNT-SPECIFIC event history with RCN-xxx code
                event_code = generate_inventory_event_code(change_type, item_id=item.id, code_type="event")
                
                deduction_history = UnifiedInventoryHistory(
                    inventory_item_id=item.id,
                    change_type=change_type,  # 'recount'
                    quantity_change=-deduct_from_lot,
                    unit=lot.unit,
                    unit_cost=lot.unit_cost,
                    notes=f"RECOUNT: Deducted {deduct_from_lot} from lot {lot.fifo_code}" + (f" | {notes}" if notes else ""),
                    created_by=created_by,
                    organization_id=item.organization_id,
                    affected_lot_id=lot.id,  # ALWAYS reference the affected lot
                    fifo_code=event_code  # RECOUNT's own event code (RCN-xxx)
                )
                db.session.add(deduction_history)

                remaining_to_deduct -= deduct_from_lot
                lots_affected += 1

                logger.info(f"RECOUNT DEDUCT: Consumed {deduct_from_lot} from lot {lot.id} ({lot.fifo_code})")

            logger.info(f"RECOUNT DEDUCT SUCCESS: Affected {lots_affected} lots")

        else:
            # SCENARIOS 2 & 3: ADDITIVE RECOUNT - refill existing lots + handle overflow
            logger.info(f"RECOUNT: Adding {delta} - checking for refillable lots vs overflow")

            # Get existing lots that can be refilled (depleted lots first, then partial lots)
            existing_lots = get_item_lots(item.id, active_only=False, order='desc')  # Newest first
            refillable_lots = [lot for lot in existing_lots if lot.remaining_quantity < lot.original_quantity]
            
            remaining_to_add = delta
            refilled_lots = 0

            # SCENARIO 2: Try to refill existing lots to their capacity (newest first for recount)
            for lot in refillable_lots:
                if remaining_to_add <= 0:
                    break

                # Calculate how much we can add to this lot (up to its original capacity)
                available_capacity = lot.original_quantity - lot.remaining_quantity
                refill_amount = min(remaining_to_add, available_capacity)

                if refill_amount > 0:
                    # Refill the lot
                    lot.remaining_quantity += refill_amount
                    db.session.add(lot)

                    # Create recount event history for this refill with RCN-xxx code
                    event_code = generate_inventory_event_code(change_type, item_id=item.id, code_type="event")
                    
                    refill_history = UnifiedInventoryHistory(
                        inventory_item_id=item.id,
                        change_type=change_type,  # 'recount'
                        quantity_change=refill_amount,
                        unit=lot.unit,
                        unit_cost=lot.unit_cost,
                        notes=f"RECOUNT: Refilled {refill_amount} to lot {lot.fifo_code}" + (f" | {notes}" if notes else ""),
                        created_by=created_by,
                        organization_id=item.organization_id,
                        affected_lot_id=lot.id,  # ALWAYS reference the affected lot
                        fifo_code=event_code  # RECOUNT's own event code (RCN-xxx)
                    )
                    db.session.add(refill_history)

                    remaining_to_add -= refill_amount
                    refilled_lots += 1
                    
                    logger.info(f"RECOUNT: Refilled {refill_amount} to lot {lot.id} ({lot.fifo_code})")

            # SCENARIO 3: Handle overflow if there's still quantity to add
            if remaining_to_add > 0:
                logger.info(f"RECOUNT: Creating overflow lot for remaining {remaining_to_add}")

                # Create new lot for overflow - this will create its own LOT-xxx code
                success, message, overflow_lot_id = create_new_fifo_lot(
                    item_id=item.id,
                    quantity=remaining_to_add,
                    change_type=change_type,  # 'recount' - but create_new_fifo_lot handles lot creation properly
                    unit=item.unit or 'count',
                    notes=f"RECOUNT overflow: {remaining_to_add}" + (f" | {notes}" if notes else ""),
                    cost_per_unit=item.cost_per_unit or 0.0,
                    created_by=created_by
                )

                if not success:
                    return False, f"Failed to create recount overflow lot: {message}"

            # Log summary
            summary_parts = []
            if refilled_lots > 0:
                summary_parts.append(f"refilled {refilled_lots} lots")
            if remaining_to_add > 0:
                summary_parts.append(f"created overflow lot")
            
            summary_msg = " and ".join(summary_parts) if summary_parts else f"processed {delta} inventory"
            logger.info(f"RECOUNT SUCCESS: {summary_msg}")

        # Return success - core will set the absolute quantity using target_quantity
        logger.info(f"RECOUNT COMPLETE: Item {item.id} FIFO reconciled for target {target_qty}")
        return True, f"Inventory recounted to {target_qty}"

    except Exception as e:
        logger.error(f"Error in recount operation: {str(e)}")
        return False, f"Recount failed: {str(e)}"