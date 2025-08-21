import logging
from datetime import datetime, timedelta
from decimal import Decimal
from app.models import db, InventoryItem, UnifiedInventoryHistory
from app.utils.timezone_utils import TimezoneUtils
from sqlalchemy import and_

logger = logging.getLogger(__name__)


def _internal_add_fifo_entry_enhanced(item_id, quantity, change_type, unit, notes=None, cost_per_unit=None, created_by=None, custom_expiration_date=None, custom_shelf_life_days=None, **kwargs):
    """
    Enhanced FIFO entry creation with proper lot tracking
    """
    try:
        from app.models import InventoryItem
        from app.models.inventory_lot import InventoryLot
        from app.utils.fifo_generator import generate_fifo_code

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

        # Calculate expiration if needed - lots MUST inherit perishable status
        final_expiration_date = None
        final_shelf_life_days = None
        is_perishable = item.is_perishable  # Always inherit from item

        if custom_expiration_date:
            final_expiration_date = custom_expiration_date
            is_perishable = True  # If expiration is set, it's perishable
        elif item.is_perishable and item.shelf_life_days:
            final_expiration_date = TimezoneUtils.utc_now() + timedelta(days=item.shelf_life_days)
            final_shelf_life_days = item.shelf_life_days
        elif custom_shelf_life_days and item.is_perishable:
            final_expiration_date = TimezoneUtils.utc_now() + timedelta(days=custom_shelf_life_days)
            final_shelf_life_days = custom_shelf_life_days

        # If item is perishable, shelf_life_days should be set
        if item.is_perishable:
            final_shelf_life_days = final_shelf_life_days or item.shelf_life_days or custom_shelf_life_days

        # Get batch_id from kwargs if provided
        batch_id = kwargs.get('batch_id')
        fifo_code = generate_fifo_code(change_type, item_id)


        # Create new lot - ALWAYS inherit perishable status from item
        # The InventoryLot IS the inventory record, no need for duplicate history entry
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
            fifo_code=fifo_code,
            batch_id=batch_id, # Store batch_id in lot
            organization_id=item.organization_id
        )

        db.session.add(lot)
        db.session.flush()  # Get the lot ID

        # For restock operations, the InventoryLot IS the history record
        # We don't create a duplicate history entry - the lot serves as both the inventory 
        # record and the historical event record

        logger.info(f"FIFO: Created lot {lot.fifo_code} with {quantity} {unit} for item {item_id} (perishable: {is_perishable})")
        # Return lot id for callers that want to create a corresponding history event
        return True, f"Added {quantity} {unit} to inventory", lot.id

    except Exception as e:
        logger.error(f"FIFO: Error creating lot for item {item_id}: {str(e)}")
        db.session.rollback()
        return False, f"Error creating inventory lot: {str(e)}", None


def _handle_deductive_operation_internal(item_id, quantity_to_deduct, change_type, notes=None, created_by=None, batch_id=None):
    """
    Handle deductive operations using FIFO (First In, First Out) logic with lots
    """
    try:
        from app.models import InventoryItem
        from app.models.inventory_lot import InventoryLot

        # Get all available lots for this item (oldest first - FIFO)
        available_lots = InventoryLot.query.filter(
            and_(
                InventoryLot.inventory_item_id == item_id,
                InventoryLot.remaining_quantity > 0
            )
        ).order_by(InventoryLot.received_date.asc()).all()

        if not available_lots:
            logger.warning(f"FIFO: No available lots for deduction from item {item_id}")
            return True, "No inventory to deduct from"

        remaining_to_deduct = abs(float(quantity_to_deduct))
        deductions = []

        for lot in available_lots:
            if remaining_to_deduct <= 0:
                break

            available_qty = lot.remaining_quantity
            deduct_from_lot = min(remaining_to_deduct, available_qty)

            # Update remaining quantity in the lot
            lot.remaining_quantity -= deduct_from_lot
            remaining_to_deduct -= deduct_from_lot

            # Create deduction record in unified history
            deduction_entry = UnifiedInventoryHistory(
                inventory_item_id=item_id,
                change_type=change_type,
                quantity_change=-deduct_from_lot,
                remaining_quantity=0,  # Deductions don't have remaining quantity
                unit=lot.unit,
                unit_cost=lot.unit_cost,
                fifo_code=lot.fifo_code,
                notes=notes,
                created_by=created_by,
                batch_id=batch_id,
                is_perishable=lot.expiration_date is not None,  # Inherit perishable from lot
                shelf_life_days=lot.shelf_life_days,
                expiration_date=lot.expiration_date,
                affected_lot_id=lot.id,  # Link to the affected lot
                organization_id=lot.organization_id
            )

            db.session.add(deduction_entry)
            deductions.append({
                'lot_id': lot.id,
                'fifo_code': lot.fifo_code,
                'amount': deduct_from_lot,
                'unit': lot.unit
            })

            logger.info(f"FIFO: Deducted {deduct_from_lot} {lot.unit} from lot {lot.fifo_code} (ID: {lot.id})")

        if remaining_to_deduct > 0:
            logger.warning(f"FIFO: Could not deduct full amount. {remaining_to_deduct} units remaining")
            return False, f"Insufficient inventory. {remaining_to_deduct} units could not be deducted"

        return True, f"Deducted from {len(deductions)} lots"

    except Exception as e:
        logger.error(f"FIFO: Error in deductive operation for item {item_id}: {str(e)}")
        db.session.rollback()
        return False, f"Error processing deduction: {str(e)}"


def _calculate_deduction_plan_internal(item_id, quantity, change_type):
    """Calculate FIFO deduction plan with detailed lot tracking - item-scoped only"""
    try:
        from app.models.inventory_lot import InventoryLot

        # Use proper InventoryLot table for FIFO calculations
        available_lots = InventoryLot.query.filter(
            and_(
                InventoryLot.inventory_item_id == item_id,
                InventoryLot.remaining_quantity > 0
            )
        ).order_by(InventoryLot.received_date.asc()).all()

        total_available = sum(lot.remaining_quantity for lot in available_lots)

        logger.info(f"DEDUCTION PLAN: Found {len(available_lots)} available lots with total {total_available}, need {quantity}")

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
                    'lot_remaining_before': lot.remaining_quantity,
                    'lot_remaining_after': lot.remaining_quantity - deduct_from_lot,
                    'lot_change_type': lot.change_type,
                    'lot_timestamp': lot.timestamp
                })
                remaining_to_deduct -= deduct_from_lot
                logger.info(f"DEDUCTION PLAN: Will consume {deduct_from_lot} from lot {lot.id} ({lot.change_type}, {lot.timestamp})")

        logger.info(f"DEDUCTION PLAN: Created plan consuming from {len(deduction_plan)} lots")
        return deduction_plan, None

    except Exception as e:
        logger.error(f"Error calculating deduction plan: {str(e)}")
        return None, str(e)


def _execute_deduction_plan_internal(deduction_plan, item_id):
    """Execute the FIFO deduction plan with detailed tracking"""
    try:
        for step in deduction_plan:
            lot_id = step['lot_id']
            deduct_quantity = step['deduct_quantity']

            lot = db.session.get(InventoryLot, lot_id) # Changed to InventoryLot
            if lot:
                old_remaining = lot.remaining_quantity
                lot.remaining_quantity -= deduct_quantity
                logger.info(f"DEDUCTION EXECUTE: Lot {lot_id} remaining: {old_remaining} -> {lot.remaining_quantity}")
            else:
                logger.error(f"DEDUCTION EXECUTE: Lot {lot_id} not found!")
                return False, f"Lot {lot_id} not found during execution"

        return True, None

    except Exception as e:
        logger.error(f"Error executing deduction plan: {str(e)}")
        return False, str(e)


def _record_deduction_plan_internal(item_id, deduction_plan, change_type, notes, created_by=None, fifo_reference_id=None):
    """Record individual deduction records for each lot consumed"""
    try:
        item = db.session.get(InventoryItem, item_id)

        # Handle fifo_reference_id explicitly
        reference_kwargs = {}
        if fifo_reference_id is not None:
            reference_kwargs['fifo_reference_id'] = fifo_reference_id

        # Create individual history record for each lot consumed
        for step in deduction_plan:
            lot_id = step['lot_id']
            deduct_quantity = step['deduct_quantity']

            # Get the lot being consumed to get its details
            consumed_lot = db.session.get(InventoryLot, lot_id) # Changed to InventoryLot

            history_entry = UnifiedInventoryHistory(
                inventory_item_id=item_id,
                organization_id=item.organization_id,
                change_type=change_type,
                quantity_change=-deduct_quantity,  # Individual lot deduction amount
                remaining_quantity=0,  # This is a deduction record, not a lot
                notes=f"{notes} (from lot {lot_id}: -{deduct_quantity})",
                created_by=created_by,
                timestamp=TimezoneUtils.utc_now(),
                unit=item.unit if item.unit else 'count',
                unit_cost=consumed_lot.unit_cost if consumed_lot else (item.cost_per_unit or 0.0),
                affected_lot_id=lot_id,  # This is the "credited/debited to" field
                fifo_reference_id=lot_id,  # Reference to the lot being consumed
                **reference_kwargs
            )

            db.session.add(history_entry)
            logger.info(f"DEDUCTION RECORD: Created {change_type} record for -{deduct_quantity} from lot {lot_id}")

        return True

    except Exception as e:
        logger.error(f"Error recording deduction plan: {str(e)}")
        return False


def calculate_current_fifo_total(item_id):
    """Calculate current FIFO total for validation - item-scoped only"""
    from app.models.inventory_lot import InventoryLot

    # Use InventoryLot instead of deprecated UnifiedInventoryHistory remaining_quantity
    lots = InventoryLot.query.filter(
        and_(
            InventoryLot.inventory_item_id == item_id,
            InventoryLot.remaining_quantity > 0
        )
    ).all()

    return sum(float(lot.remaining_quantity) for lot in lots)


def credit_specific_lot(lot_id, quantity, notes=None, created_by=None):
    """Credit back to a specific FIFO lot (used for reservation releases)"""
    try:
        entry = db.session.get(InventoryLot, lot_id) # Changed to InventoryLot
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