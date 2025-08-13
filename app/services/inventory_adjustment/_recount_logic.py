
from flask_login import current_user  
from app.models import db, InventoryItem, UnifiedInventoryHistory
from sqlalchemy import and_
import logging

logger = logging.getLogger(__name__)


def handle_recount_adjustment(item_id, target_quantity, notes=None, created_by=None, item_type='ingredient'):
    """
    Recount sets absolute target quantity with proper lot management:

    POSITIVE RECOUNT (increase):
    - Fill existing lots to their full capacity first
    - Create new lot with overflow if needed
    - Log history entry for each lot affected

    NEGATIVE RECOUNT (decrease):
    - Consume from all lots (including expired) oldest-first
    - Log history entry for each lot consumed

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

        # Get ALL FIFO entries with remaining quantity > 0 (including expired)
        entries = UnifiedInventoryHistory.query.filter(
            and_(
                UnifiedInventoryHistory.inventory_item_id == item_id,
                UnifiedInventoryHistory.remaining_quantity > 0,
                UnifiedInventoryHistory.organization_id == org_id
            )
        ).order_by(UnifiedInventoryHistory.timestamp.asc()).all()  # Oldest first

        # Calculate current FIFO total
        current_fifo_total = sum(float(entry.remaining_quantity) for entry in entries)
        print(f"RECOUNT: Current FIFO total: {current_fifo_total}")

        # Check if FIFO is already at target - no changes needed
        if abs(current_fifo_total - target_qty) < 0.001:
            print(f"RECOUNT: FIFO already matches target {target_qty}, no changes needed")
            item.quantity = target_qty
            db.session.commit()
            return True

        # INCREASING quantity: fill existing lots then create overflow
        if delta > 0:
            remaining_to_add = delta
            history_entries = []

            # Fill existing lots to their original capacity first
            for entry in entries:
                if remaining_to_add <= 0:
                    break

                # Calculate how much this lot can still accept (original quantity_change - remaining)
                original_qty = float(getattr(entry, 'quantity_change', 0))
                if original_qty > 0:  # Only fill addition lots, not deduction lots
                    current_remaining = float(entry.remaining_quantity)
                    capacity_available = original_qty - current_remaining

                    if capacity_available > 0:
                        fill_amount = min(remaining_to_add, capacity_available)
                        entry.remaining_quantity = current_remaining + fill_amount
                        remaining_to_add -= fill_amount

                        # Create history entry for this lot fill
                        from app.utils.fifo_generator import generate_fifo_code

                        history = UnifiedInventoryHistory(
                            inventory_item_id=item_id,
                            change_type='recount',
                            quantity_change=fill_amount,
                            remaining_quantity=0.0,  # Recount adjustments don't create new FIFO
                            unit=history_unit,
                            notes=f"{notes or 'Recount fill'} - Added to existing lot {entry.id}",
                            created_by=created_by,
                            organization_id=org_id,
                            fifo_code=generate_fifo_code('recount'),
                            fifo_reference_id=entry.id,
                            unit_cost=getattr(entry, 'unit_cost', item.cost_per_unit)
                        )

                        db.session.add(history)
                        history_entries.append(history)
                        print(f"RECOUNT: Filled lot {entry.id} with {fill_amount}")

            # Create overflow lot if there's still quantity to add
            if remaining_to_add > 0:
                from app.utils.fifo_generator import generate_fifo_code

                overflow_lot = UnifiedInventoryHistory(
                    inventory_item_id=item_id,
                    change_type='recount',
                    quantity_change=remaining_to_add,
                    remaining_quantity=remaining_to_add,  # New lot with full quantity
                    unit=history_unit,
                    notes=f"{notes or 'Recount overflow'} - New lot for overflow",
                    created_by=created_by,
                    organization_id=org_id,
                    fifo_code=generate_fifo_code('recount'),
                    unit_cost=item.cost_per_unit,
                    expiration_date=None,  # Recount lots don't inherit expiration
                    shelf_life_days=None
                )

                db.session.add(overflow_lot)
                history_entries.append(overflow_lot)
                print(f"RECOUNT: Created overflow lot with {remaining_to_add}")

        # DECREASING quantity: consume from all lots oldest-first
        else:
            to_remove = abs(delta)
            remaining = to_remove
            deduction_plan = []

            # Build deduction plan from oldest lots first (including expired)
            for entry in entries:
                if remaining <= 0:
                    break
                take = min(float(entry.remaining_quantity), remaining)
                if take > 0:
                    deduction_plan.append((entry.id, take, getattr(entry, 'unit_cost', None)))
                    remaining -= take

            # Apply deductions to FIFO entries (decrement remaining_quantity)
            for entry_id, qty_to_deduct, unit_cost in deduction_plan:
                entry = UnifiedInventoryHistory.query.get(entry_id)
                if entry:
                    entry.remaining_quantity = float(entry.remaining_quantity) - qty_to_deduct
                    print(f"RECOUNT: Deducted {qty_to_deduct} from lot {entry_id}")

            # Create deduction history entries for audit trail
            if deduction_plan:
                from app.utils.fifo_generator import generate_fifo_code

                for entry_id, qty_deducted, unit_cost in deduction_plan:
                    history = UnifiedInventoryHistory(
                        inventory_item_id=item_id,
                        change_type='recount',
                        quantity_change=-qty_deducted,
                        remaining_quantity=0.0,  # Deductions don't add new FIFO
                        unit=history_unit,
                        notes=f"{notes or 'Recount deduction'} - Consumed from lot {entry_id}",
                        created_by=created_by,
                        organization_id=org_id,
                        fifo_code=generate_fifo_code('recount'),
                        fifo_reference_id=entry_id,
                        unit_cost=unit_cost
                    )
                    db.session.add(history)

        # Set item to target quantity (absolute sync)
        item.quantity = target_qty
        db.session.commit()

        # Validate final sync state
        final_entries = UnifiedInventoryHistory.query.filter(
            and_(
                UnifiedInventoryHistory.inventory_item_id == item_id,
                UnifiedInventoryHistory.remaining_quantity > 0,
                UnifiedInventoryHistory.organization_id == org_id
            )
        ).all()

        final_fifo_total = sum(float(entry.remaining_quantity) for entry in final_entries)

        print(f"RECOUNT FINAL: inventory={item.quantity}, fifo_total={final_fifo_total}")

        if abs(item.quantity - final_fifo_total) > 0.001:
            raise ValueError(f"CRITICAL: FIFO sync failed after recount - inventory={item.quantity}, fifo_total={final_fifo_total}")

        return True

    except Exception as e:
        db.session.rollback()
        print(f"RECOUNT ERROR: {str(e)}")
        raise e
