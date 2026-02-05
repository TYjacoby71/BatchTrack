"""FIFO inventory operations.

Synopsis:
Provides FIFO lot creation, deductions, and cost estimation.

Glossary:
- FIFO lot: Inventory lot consumed in first-in-first-out order.
- Issue: Inventory deduction event.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from app.models import db, InventoryItem, UnifiedInventoryHistory
from app.utils.timezone_utils import TimezoneUtils
from app.utils.inventory_event_code_generator import generate_inventory_event_code
from sqlalchemy import and_

logger = logging.getLogger(__name__)


# Service 1: Fetch FIFO lots for an item.
def get_item_lots(item_id: int, active_only: bool = False, order: str = 'desc'):
    """
    Retrieve lots for an inventory item using the proper InventoryLot model.
    This replaces any legacy history-based lot queries.

    Args:
        item_id: ID of the inventory item
        active_only: If True, only return lots with remaining_quantity > 0
        order: 'asc' for FIFO order (oldest first), 'desc' for newest first
    """
    from app.models.inventory_lot import InventoryLot
    from app.models import InventoryItem

    # Get the item for organization scoping
    item = db.session.get(InventoryItem, item_id)
    if not item:
        logger.warning(f"FIFO: Item {item_id} not found when retrieving lots")
        return []

    # Build query with proper organization scoping
    query = InventoryLot.query.filter(
        and_(
            InventoryLot.inventory_item_id == item_id,
            InventoryLot.organization_id == item.organization_id
        )
    )

    # Filter to active lots only if requested
    if active_only:
        query = query.filter(InventoryLot.remaining_quantity > 0)

    # Apply ordering - FIFO uses received_date ascending
    if order == 'asc':
        query = query.order_by(InventoryLot.received_date.asc())
    else:
        query = query.order_by(InventoryLot.created_at.desc())

    lots = query.all()

    logger.info(f"FIFO: Retrieved {len(lots)} lots for item {item_id} (active_only={active_only})")

    return lots


# Service 2: Create a new FIFO lot and history entry.
def create_new_fifo_lot(item_id, quantity, change_type, unit=None, notes=None, cost_per_unit=None, created_by=None, custom_expiration_date=None, custom_shelf_life_days=None, **kwargs):
    """
    Create a new FIFO lot with complete tracking and audit trail.
    This is the primary function for creating new inventory lots.
    """
    try:
        from app.models import InventoryItem
        from app.models.inventory_lot import InventoryLot
        from flask_login import current_user # Import current_user

        # Get the inventory item
        item = db.session.get(InventoryItem, item_id)
        if not item:
            logger.error(f"Inventory item {item_id} not found")
            return False, "Inventory item not found"

        # Use item's unit if not specified
        if unit is None:
            unit = item.unit

        if cost_per_unit is None:
            cost_per_unit = item.cost_per_unit or 0.0

        # Calculate expiration - lots inherit shelf life from item only (no custom per-lot shelf life)
        final_expiration_date = None
        final_shelf_life_days = None
        is_perishable = item.is_perishable  # Always inherit from item

        if custom_expiration_date:
            # Only allow custom expiration date, but shelf life still comes from item
            final_expiration_date = custom_expiration_date
            is_perishable = True  # If expiration is set, it's perishable
        elif item.is_perishable and item.shelf_life_days:
            # Standard case - use item's shelf life to calculate expiration
            final_expiration_date = TimezoneUtils.utc_now() + timedelta(days=item.shelf_life_days)

        # Lots always inherit shelf_life_days from the item (immutable once created)
        if item.is_perishable:
            final_shelf_life_days = item.shelf_life_days

        # Get batch_id from kwargs if provided
        batch_id = kwargs.get('batch_id')

        batch_lineage_id = None
        batch = None
        # For finished_batch operations, use batch-specific label if batch_id exists
        if change_type == 'finished_batch' and batch_id:
            from app.models import Batch
            batch = db.session.get(Batch, batch_id)
            if batch and batch.label_code:
                fifo_code = batch.label_code
                batch_lineage_id = batch.lineage_id
            else:
                fifo_code = generate_inventory_event_code(change_type, item_id=item_id, code_type="lot")
        else:
            # For lot creation, this always creates an actual lot
            fifo_code = generate_inventory_event_code(change_type, item_id=item_id, code_type="lot")
            if batch_id and not batch:
                try:
                    from app.models import Batch
                    batch = db.session.get(Batch, batch_id)
                except Exception:
                    batch = None
            if batch:
                batch_lineage_id = batch.lineage_id

        # Create new lot - ALWAYS inherit perishable status from item
        lot = InventoryLot(
            inventory_item_id=item_id,
            remaining_quantity=float(quantity),
            original_quantity=float(quantity),
            unit=unit,
            unit_cost=float(cost_per_unit),
            received_date=TimezoneUtils.utc_now(),
            expiration_date=final_expiration_date,
            shelf_life_days=final_shelf_life_days,
            source_type=change_type,
            source_notes=notes,
            created_by=created_by,
            fifo_code=fifo_code,  # Use the shared FIFO code
            batch_id=batch_id if change_type == 'finished_batch' else None,  # Only link batch for finished_batch
            organization_id=item.organization_id
        )

        db.session.add(lot)
        db.session.flush()  # Get the lot ID

        # Create history record that SHARES the same FIFO code
        # The history entry shows the lot creation event with the SAME fifo_code
        history_record = UnifiedInventoryHistory(
            inventory_item_id=item.id,
            change_type=change_type,
            quantity_change=quantity,
            unit=unit,
            unit_cost=cost_per_unit,
            notes=notes,
            created_by=(getattr(current_user, 'id', None) if getattr(current_user, 'is_authenticated', False) else created_by),
            organization_id=item.organization_id,
            is_perishable=item.is_perishable,
            shelf_life_days=item.shelf_life_days,
            expiration_date=final_expiration_date,
            affected_lot_id=lot.id,  # Link to the actual lot
            batch_id=batch_id,
            lineage_id=batch_lineage_id,
            fifo_code=fifo_code,  # USE THE SAME FIFO CODE AS THE LOT
            remaining_quantity=None,  # Only the lot object holds remaining quantity, not history events
        )
        db.session.add(history_record)

        logger.info(f"FIFO: Created lot {lot.fifo_code} with {quantity} {unit} for item {item_id} (perishable: {is_perishable})")
        # Return lot id for callers that want to create a corresponding history event
        return True, f"Added {quantity} {unit} to inventory", lot.id

    except Exception as e:
        logger.error(f"FIFO: Error creating lot for item {item_id}: {str(e)}")
        db.session.rollback()
        return False, f"Error creating inventory lot: {str(e)}", None


# Service 3: Deduct inventory using FIFO ordering.
def deduct_fifo_inventory(item_id, quantity_to_deduct, change_type, notes=None, created_by=None, batch_id=None):
    """
    CONSOLIDATED: Single function to handle FIFO deduction using proper InventoryLot model.
    This function now properly uses the lot-based system instead of history entries.
    """
    try:
        from app.models.inventory_lot import InventoryLot

        # Get the inventory item for validation
        item = db.session.get(InventoryItem, item_id)
        if not item:
            return False, "Inventory item not found"

        # Determine valuation method for this deduction event
        valuation_method = None
        try:
            op = str(change_type).lower() if change_type else ''
            # For commerce operations on products, always use average (WAC)
            if op in {'sale', 'pos_sale', 'pos_return_neg'} and getattr(item, 'type', None) == 'product':
                valuation_method = 'average'
            # For batch deductions, honor the batch-locked method
            elif op == 'batch' and batch_id:
                from app.models import Batch
                b = db.session.get(Batch, batch_id)
                if b and getattr(b, 'cost_method', None):
                    valuation_method = b.cost_method
            # Otherwise fall back to organization setting
            if not valuation_method:
                org = getattr(item, 'organization', None)
                org_method = getattr(org, 'inventory_cost_method', None) if org else None
                valuation_method = org_method or 'fifo'
            if valuation_method not in ('fifo', 'average'):
                valuation_method = 'fifo'
        except Exception:
            valuation_method = 'fifo'

        # Get active lots ordered by FIFO (oldest received first)
        query = InventoryLot.query.filter(
            and_(
                InventoryLot.inventory_item_id == item_id,
                InventoryLot.organization_id == item.organization_id,
                InventoryLot.remaining_quantity > 0
            )
        )

        # For consumption operations, exclude expired lots if the item is perishable
        consumption_ops = {'use', 'sale', 'sample', 'tester', 'gift', 'batch', 'pos_sale', 'pos_return_neg'}
        if item.is_perishable and (str(change_type).lower() in consumption_ops):
            now_utc = TimezoneUtils.utc_now()
            query = query.filter(
                (InventoryLot.expiration_date == None) | (InventoryLot.expiration_date >= now_utc)
            )

        active_lots = query.order_by(InventoryLot.received_date.asc()).all()

        # Calculate total available quantity from actual lots
        total_available = sum(float(lot.remaining_quantity) for lot in active_lots)
        quantity_needed = abs(float(quantity_to_deduct))

        logger.info(f"FIFO DEDUCT: Need {quantity_needed}, have {total_available} from {len(active_lots)} active lots")

        if total_available < quantity_needed:
            return False, f"Insufficient inventory: need {quantity_needed}, have {total_available}"

        # Execute deduction across lots using FIFO order
        remaining_to_deduct = quantity_needed
        lots_affected = 0

        for lot in active_lots:
            if remaining_to_deduct <= 0:
                break

            # Calculate how much to deduct from this lot
            deduct_from_lot = min(float(lot.remaining_quantity), remaining_to_deduct)

            # Update the lot's remaining quantity
            lot.remaining_quantity = float(lot.remaining_quantity) - deduct_from_lot

            # Generate appropriate event code for this deduction event; prefer batch label when available
            batch_lineage_id = None
            if change_type == 'batch' and batch_id:
                try:
                    from app.models import Batch
                    batch = db.session.get(Batch, batch_id)
                    deduction_event_code = (
                        batch.label_code
                        if batch and batch.label_code
                        else generate_inventory_event_code(change_type, item_id=item_id, code_type="event")
                    )
                    if batch:
                        batch_lineage_id = batch.lineage_id
                except Exception:
                    deduction_event_code = generate_inventory_event_code(change_type, item_id=item_id, code_type="event")
            else:
                deduction_event_code = generate_inventory_event_code(change_type, item_id=item_id, code_type="event")

            # Choose unit cost according to valuation method
            event_unit_cost = float(item.cost_per_unit or 0.0) if valuation_method == 'average' else float(lot.unit_cost or 0.0)

            history_record = UnifiedInventoryHistory(
                inventory_item_id=item_id,
                change_type=change_type,
                quantity_change=-deduct_from_lot,
                remaining_quantity=None,  # N/A - this is an event record
                unit=lot.unit,
                unit_cost=event_unit_cost,
                notes=f"FIFO deduction: -{deduct_from_lot} from lot {lot.fifo_code}" + (f" | {notes}" if notes else ""),
                created_by=created_by,
                organization_id=item.organization_id,
                affected_lot_id=lot.id,  # Link to the specific lot that was affected
                batch_id=batch_id,
                lineage_id=batch_lineage_id,
                fifo_code=deduction_event_code,  # RCN-xxx for recount, other prefixes for other operations
                valuation_method=valuation_method

            )
            db.session.add(history_record)

            remaining_to_deduct -= deduct_from_lot
            lots_affected += 1

            logger.info(f"FIFO DEDUCT: Consumed {deduct_from_lot} from lot {lot.id} ({lot.fifo_code}), remaining: {lot.remaining_quantity}")

        logger.info(f"FIFO DEDUCT SUCCESS: Affected {lots_affected} lots")
        return True, f"Deducted from {lots_affected} lots using FIFO order"

    except Exception as e:
        logger.error(f"FIFO: Error in lot-based deduction for item {item_id}: {str(e)}")
        db.session.rollback()
        return False, f"Error processing FIFO deduction: {str(e)}"


# Service 4: Calculate total available inventory across lots.
def calculate_total_available_inventory(item_id):
    """
    Calculate total available inventory from all active lots for an item.
    This now properly uses the InventoryLot model for accurate FIFO calculations.
    """
    from app.models.inventory_lot import InventoryLot
    from app.models import InventoryItem

    # Get the item for organization scoping
    item = db.session.get(InventoryItem, item_id)
    if not item:
        return 0.0

    # Query active lots with proper organization scoping
    active_lots = InventoryLot.query.filter(
        and_(
            InventoryLot.inventory_item_id == item_id,
            InventoryLot.organization_id == item.organization_id,
            InventoryLot.remaining_quantity > 0
        )
    ).all()

    total_available = sum(float(lot.remaining_quantity) for lot in active_lots)

    logger.info(f"FIFO CALC: Item {item_id} has {total_available} units available across {len(active_lots)} active lots")

    return total_available


# Service 5: Estimate unit cost for FIFO deduction.
def estimate_fifo_issue_unit_cost(item_id: int, quantity_to_deduct: float, change_type: str | None = None) -> float:
    """
    Estimate the weighted average unit cost for a prospective FIFO deduction without mutating state.

    Uses the same lot selection filters as deduct_fifo_inventory (including skipping expired for consumption ops).
    Returns 0.0 if no quantity or no active lots.
    """
    try:
        from app.models.inventory_lot import InventoryLot

        item = db.session.get(InventoryItem, item_id)
        if not item:
            return 0.0

        query = InventoryLot.query.filter(
            and_(
                InventoryLot.inventory_item_id == item_id,
                InventoryLot.organization_id == item.organization_id,
                InventoryLot.remaining_quantity > 0
            )
        )

        consumption_ops = {'use', 'sale', 'sample', 'tester', 'gift', 'batch', 'pos_sale', 'pos_return_neg'}
        if item.is_perishable and (str(change_type).lower() in consumption_ops if change_type else True):
            now_utc = TimezoneUtils.utc_now()
            query = query.filter(
                (InventoryLot.expiration_date == None) | (InventoryLot.expiration_date >= now_utc)
            )

        active_lots = query.order_by(InventoryLot.received_date.asc()).all()

        remaining = max(0.0, float(quantity_to_deduct or 0.0))
        if remaining <= 0 or not active_lots:
            return float(item.cost_per_unit or 0.0)  # reasonable fallback

        cost_sum = 0.0
        qty_sum = 0.0
        for lot in active_lots:
            if remaining <= 0:
                break
            take = min(float(lot.remaining_quantity), remaining)
            cost_sum += take * float(lot.unit_cost or 0.0)
            qty_sum += take
            remaining -= take

        return (cost_sum / qty_sum) if qty_sum > 0 else float(item.cost_per_unit or 0.0)
    except Exception:
        return 0.0


# Service 6: Credit inventory back to a specific lot.
def credit_specific_lot(lot_id, quantity, notes=None, created_by=None):
    """
    Credit inventory back to a specific FIFO lot.
    This is the canonical function used by all inventory adjustment operations.
    Used for reservation releases, returns, and corrections.
    """
    try:
        from app.models.inventory_lot import InventoryLot

        lot = db.session.get(InventoryLot, lot_id)
        if not lot:
            return False, "FIFO lot not found"

        # Add back to the specific lot
        lot.remaining_quantity = float(lot.remaining_quantity) + float(quantity)

        # Update item quantity
        item = db.session.get(InventoryItem, lot.inventory_item_id)
        if item:
            item.quantity = float(item.quantity) + float(quantity)

        db.session.commit()
        return True, f"Credited {quantity} back to lot {lot_id}"

    except Exception as e:
        db.session.rollback()
        return False, f"Error crediting lot: {str(e)}"