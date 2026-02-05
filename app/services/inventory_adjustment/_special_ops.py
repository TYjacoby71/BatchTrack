"""Special inventory operation handlers.

Synopsis:
Handle cost overrides, unit conversions, and recount adjustments.

Glossary:
- Cost override: Update cost without changing quantity.
- Recount: Set inventory to a target quantity and re-sync lots.
"""

import logging
from app.models import db
from app.services.quantity_base import from_base_quantity, to_base_quantity, sync_lot_quantities_from_base
from app.utils.inventory_event_code_generator import generate_inventory_event_code
from ._fifo_ops import create_new_fifo_lot, deduct_fifo_inventory # Kept for local use within this file and added deduct_fifo_inventory
from sqlalchemy import and_

logger = logging.getLogger(__name__)

def handle_cost_override(item, quantity, quantity_base=None, change_type=None, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, customer=None, sale_price=None, order_id=None, target_quantity=None, unit=None, **kwargs):
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
            quantity_change_base=0,
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

def handle_unit_conversion(item, quantity, quantity_base=None, change_type=None, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, customer=None, sale_price=None, order_id=None, target_quantity=None, unit=None, **kwargs):
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
            quantity_change_base=0,
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

def handle_recount(item, quantity, quantity_base=None, change_type=None, notes=None, created_by=None, target_quantity=None, target_quantity_base=None, **kwargs):
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

        current_quantity_base = int(getattr(item, "quantity_base", 0) or 0)
        if target_quantity_base is None:
            target_quantity_base = to_base_quantity(
                amount=target_quantity,
                unit_name=item.unit,
                ingredient_id=item.id,
                density=item.density,
            )
        target_qty = from_base_quantity(
            base_amount=target_quantity_base,
            unit_name=item.unit,
            ingredient_id=item.id,
            density=item.density,
        )
        if target_qty < 0:
            return False, "Recount target quantity must be zero or greater"

        # Use FIFO totals for reconciliation to handle desyncs
        active_lots = InventoryLot.query.filter(
            and_(
                InventoryLot.inventory_item_id == item.id,
                InventoryLot.organization_id == item.organization_id,
                InventoryLot.remaining_quantity_base > 0
            )
        ).order_by(InventoryLot.received_date.asc()).all()
        fifo_total_base = sum(int(lot.remaining_quantity_base or 0) for lot in active_lots)
        delta_base = target_quantity_base - fifo_total_base
        if delta_base == 0:
            delta = 0.0
        else:
            delta = from_base_quantity(
                base_amount=delta_base,
                unit_name=item.unit,
                ingredient_id=item.id,
                density=item.density,
            )

        current_quantity = from_base_quantity(
            base_amount=current_quantity_base,
            unit_name=item.unit,
            ingredient_id=item.id,
            density=item.density,
        )
        fifo_total = from_base_quantity(
            base_amount=fifo_total_base,
            unit_name=item.unit,
            ingredient_id=item.id,
            density=item.density,
        )
        logger.info(
            f"RECOUNT: Item {item.id} current={current_quantity}, fifo_total={fifo_total}, target={target_qty}, delta={delta}"
        )

        recount_notes = f"Inventory recount: {current_quantity} -> {target_qty}"
        if notes:
            recount_notes += f" | {notes}"

        if delta_base == 0:
            # No change needed - just sync verification
            logger.info(f"RECOUNT: No adjustment needed for item {item.id}")
            return True, f"Inventory verified at {target_qty}"

        elif delta_base < 0:
            # SCENARIO 1: RECOUNT TO ZERO OR DEDUCTIVE RECOUNT
            # Manually drain FIFO lots using recount event codes (not delegating to deduct_fifo_inventory)
            abs_delta_base = abs(int(delta_base))
            abs_delta = from_base_quantity(
                base_amount=abs_delta_base,
                unit_name=item.unit,
                ingredient_id=item.id,
                density=item.density,
            )
            logger.info(f"RECOUNT: Deducting {abs_delta} using recount-specific FIFO drainage")

            # Calculate total available quantity (FIFO total already computed)
            total_available = fifo_total
            
            if fifo_total_base < abs_delta_base:
                return False, f"Cannot recount: need to deduct {abs_delta}, but only {total_available} available"

            # Drain lots using FIFO order with recount-specific event codes
            remaining_to_deduct_base = abs_delta_base
            lots_affected = 0

            for lot in active_lots:
                if remaining_to_deduct_base <= 0:
                    break

                # Calculate how much to deduct from this lot
                lot_remaining_base = int(lot.remaining_quantity_base or 0)
                deduct_from_lot_base = min(lot_remaining_base, remaining_to_deduct_base)
                deduct_from_lot = from_base_quantity(
                    base_amount=deduct_from_lot_base,
                    unit_name=lot.unit,
                    ingredient_id=item.id,
                    density=item.density,
                )

                # Update the lot's remaining quantity
                lot.remaining_quantity_base = lot_remaining_base - deduct_from_lot_base
                sync_lot_quantities_from_base(lot, item)
                db.session.add(lot)

                # Create RECOUNT-SPECIFIC event history with RCN-xxx code
                event_code = generate_inventory_event_code(change_type, item_id=item.id, code_type="event")
                
                deduction_history = UnifiedInventoryHistory(
                    inventory_item_id=item.id,
                    change_type=change_type,  # 'recount'
                    quantity_change=-deduct_from_lot,
                    quantity_change_base=-deduct_from_lot_base,
                    unit=lot.unit,
                    unit_cost=lot.unit_cost,
                    notes=f"RECOUNT: Deducted {deduct_from_lot} from lot {lot.fifo_code}" + (f" | {notes}" if notes else ""),
                    created_by=created_by,
                    organization_id=item.organization_id,
                    affected_lot_id=lot.id,  # ALWAYS reference the affected lot
                    fifo_code=event_code  # RECOUNT's own event code (RCN-xxx)
                )
                db.session.add(deduction_history)

                remaining_to_deduct_base -= deduct_from_lot_base
                lots_affected += 1

                logger.info(f"RECOUNT DEDUCT: Consumed {deduct_from_lot} from lot {lot.id} ({lot.fifo_code})")

            logger.info(f"RECOUNT DEDUCT SUCCESS: Affected {lots_affected} lots")

        else:
            # SCENARIOS 2 & 3: ADDITIVE RECOUNT - refill existing lots + handle overflow
            logger.info(f"RECOUNT: Adding {delta} - checking for refillable lots vs overflow")

            # Get existing lots that can be refilled (depleted lots first, then partial lots)
            existing_lots = get_item_lots(item.id, active_only=False, order='desc')  # Newest first
            refillable_lots = [
                lot for lot in existing_lots
                if int(lot.remaining_quantity_base or 0) < int(lot.original_quantity_base or 0)
            ]
            
            remaining_to_add_base = int(delta_base)
            refilled_lots = 0

            # SCENARIO 2: Try to refill existing lots to their capacity (newest first for recount)
            for lot in refillable_lots:
                if remaining_to_add_base <= 0:
                    break

                # Calculate how much we can add to this lot (up to its original capacity)
                available_capacity_base = int(lot.original_quantity_base or 0) - int(lot.remaining_quantity_base or 0)
                refill_amount_base = min(remaining_to_add_base, available_capacity_base)
                refill_amount = from_base_quantity(
                    base_amount=refill_amount_base,
                    unit_name=lot.unit,
                    ingredient_id=item.id,
                    density=item.density,
                )

                if refill_amount_base > 0:
                    # Refill the lot
                    lot.remaining_quantity_base = int(lot.remaining_quantity_base or 0) + int(refill_amount_base)
                    sync_lot_quantities_from_base(lot, item)
                    db.session.add(lot)

                    # Create recount event history for this refill with RCN-xxx code
                    event_code = generate_inventory_event_code(change_type, item_id=item.id, code_type="event")
                    
                    refill_history = UnifiedInventoryHistory(
                        inventory_item_id=item.id,
                        change_type=change_type,  # 'recount'
                        quantity_change=refill_amount,
                        quantity_change_base=refill_amount_base,
                        unit=lot.unit,
                        unit_cost=lot.unit_cost,
                        notes=f"RECOUNT: Refilled {refill_amount} to lot {lot.fifo_code}" + (f" | {notes}" if notes else ""),
                        created_by=created_by,
                        organization_id=item.organization_id,
                        affected_lot_id=lot.id,  # ALWAYS reference the affected lot
                        fifo_code=event_code  # RECOUNT's own event code (RCN-xxx)
                    )
                    db.session.add(refill_history)

                    remaining_to_add_base -= refill_amount_base
                    refilled_lots += 1
                    
                    logger.info(f"RECOUNT: Refilled {refill_amount} to lot {lot.id} ({lot.fifo_code})")

            # SCENARIO 3: Handle overflow if there's still quantity to add
            if remaining_to_add_base > 0:
                remaining_to_add = from_base_quantity(
                    base_amount=remaining_to_add_base,
                    unit_name=item.unit,
                    ingredient_id=item.id,
                    density=item.density,
                )
                logger.info(f"RECOUNT: Creating overflow lot for remaining {remaining_to_add}")

                # Create new lot for overflow - this will create its own LOT-xxx code
                success, message, overflow_lot_id = create_new_fifo_lot(
                    item_id=item.id,
                    quantity=remaining_to_add,
                    quantity_base=remaining_to_add_base,
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
            if remaining_to_add_base > 0:
                summary_parts.append(f"created overflow lot")
            
            summary_msg = " and ".join(summary_parts) if summary_parts else f"processed {delta} inventory"
            logger.info(f"RECOUNT SUCCESS: {summary_msg}")

        # Return success - core will set the absolute quantity using target_quantity
        logger.info(f"RECOUNT COMPLETE: Item {item.id} FIFO reconciled for target {target_qty}")
        return True, f"Inventory recounted to {target_qty}"

    except Exception as e:
        logger.error(f"Error in recount operation: {str(e)}")
        return False, f"Recount failed: {str(e)}"