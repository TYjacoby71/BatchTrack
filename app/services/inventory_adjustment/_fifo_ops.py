import logging
from datetime import datetime, timedelta
from decimal import Decimal
from app.models import db, InventoryItem, UnifiedInventoryHistory
from app.utils.timezone_utils import TimezoneUtils
from sqlalchemy import and_

logger = logging.getLogger(__name__)


def _internal_add_fifo_entry_enhanced(item_id, quantity, change_type, unit=None, notes=None,
                                    cost_per_unit=None, created_by=None, expiration_date=None,
                                    shelf_life_days=None, **kwargs):
    """Enhanced internal FIFO entry creation with better error handling"""
    try:
        from app.models import db, InventoryItem, UnifiedInventoryHistory
        from datetime import datetime, timedelta
        from app.utils.fifo_generator import generate_fifo_code

        logger.info(f"Creating FIFO entry: item_id={item_id}, quantity={quantity}, change_type={change_type}")

        # Get the inventory item
        item = db.session.get(InventoryItem, item_id)
        if not item:
            error_msg = f"Inventory item {item_id} not found"
            logger.error(error_msg)
            return False, error_msg

        # Use item defaults if not provided
        final_unit = unit or item.unit or 'count'
        final_cost = cost_per_unit if cost_per_unit is not None else (item.cost_per_unit or 0.0)
        final_notes = notes or f"{change_type} operation"

        logger.info(f"FIFO entry details: unit={final_unit}, cost={final_cost}, notes={final_notes}")

        # Handle expiration date calculation
        final_expiration_date = None
        if expiration_date:
            final_expiration_date = expiration_date
        elif shelf_life_days and shelf_life_days > 0:
            final_expiration_date = datetime.now().date() + timedelta(days=shelf_life_days)
        elif item.is_perishable and item.shelf_life_days:
            final_expiration_date = datetime.now().date() + timedelta(days=item.shelf_life_days)

        # Create the FIFO entry
        fifo_entry = UnifiedInventoryHistory(
            inventory_item_id=item_id,
            change_type=change_type,
            quantity_change=quantity,
            remaining_quantity=quantity,
            unit=final_unit,
            unit_cost=final_cost,
            notes=final_notes,
            timestamp=datetime.utcnow(),
            expiration_date=final_expiration_date,
            shelf_life_days=shelf_life_days,
            created_by=created_by,
            fifo_code=generate_fifo_code(change_type, item_id),
            organization_id=item.organization_id
        )

        db.session.add(fifo_entry)
        logger.info(f"FIFO entry created successfully for item {item_id}")
        return True, "FIFO entry created successfully"

    except Exception as e:
        import traceback
        error_msg = f"Error creating FIFO entry: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return False, error_msg


def _handle_deductive_operation_internal(item, quantity, change_type, notes, created_by, **kwargs):
    """
    Standard FIFO deduction handler - consumes from both FIFO entries and lots.

    This is the canonical deduction path that:
    1. Plans FIFO deduction from history entries
    2. Executes the plan on FIFO entries
    3. Records individual audit trail entries for each lot consumed
    4. Updates item quantity
    """
    try:
        item_id = item.id
        abs_quantity = abs(quantity)

        logger.info(f"FIFO DEDUCTION: Starting {change_type} deduction of {abs_quantity} from item {item_id}")

        # Step 1: Plan the deduction
        deduction_plan, error = _calculate_deduction_plan_internal(item_id, abs_quantity, change_type)
        if error:
            logger.error(f"FIFO DEDUCTION: Planning failed for item {item_id}: {error}")
            return False, error

        if not deduction_plan:
            logger.warning(f"FIFO DEDUCTION: No plan generated for item {item_id}")
            return False, "Insufficient inventory"

        logger.info(f"FIFO DEDUCTION: Plan created with {len(deduction_plan)} lots to consume")

        # Step 2: Execute on FIFO entries
        success, error = _execute_deduction_plan_internal(deduction_plan, item_id)
        if not success:
            logger.error(f"FIFO DEDUCTION: Execution failed for item {item_id}: {error}")
            return False, error

        # Step 3: Record individual audit trail entries for each lot consumed
        audit_success = _record_deduction_plan_internal(
            item_id, deduction_plan, change_type, notes, created_by=created_by, **kwargs
        )
        if not audit_success:
            logger.error(f"FIFO DEDUCTION: Audit recording failed for item {item_id}")
            return False, "Failed to record deduction"

        # Step 4: Sync item quantity to FIFO total
        current_fifo_total = calculate_current_fifo_total(item_id)
        item.quantity = current_fifo_total

        # Log summary of what was consumed
        lots_summary = [f"lot {step['lot_id']}: -{step['deduct_quantity']}" for step in deduction_plan]
        logger.info(f"FIFO DEDUCTION: Successfully deducted {abs_quantity} from item {item_id} across {len(deduction_plan)} lots: {', '.join(lots_summary)}")
        
        return True, f"Deducted {abs_quantity} {getattr(item, 'unit', 'units')} from {len(deduction_plan)} lots"

    except Exception as e:
        logger.error(f"FIFO DEDUCTION: Error for item {item.id}: {str(e)}")
        return False, str(e)


def _calculate_deduction_plan_internal(item_id, quantity, change_type):
    """Calculate FIFO deduction plan with detailed lot tracking"""
    try:
        available_lots = UnifiedInventoryHistory.query.filter(
            UnifiedInventoryHistory.inventory_item_id == item_id,
            UnifiedInventoryHistory.remaining_quantity > 0
        ).order_by(UnifiedInventoryHistory.timestamp.asc()).all()

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
            
            lot = db.session.get(UnifiedInventoryHistory, lot_id)
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


def _record_deduction_plan_internal(item_id, deduction_plan, change_type, notes, created_by=None, **kwargs):
    """Record individual deduction records for each lot consumed"""
    try:
        item = db.session.get(InventoryItem, item_id)
        
        # Filter out invalid kwargs for UnifiedInventoryHistory
        valid_kwargs = {}
        valid_fields = {'fifo_reference_id'}
        for key, value in kwargs.items():
            if key in valid_fields:
                valid_kwargs[key] = value

        # Create individual history record for each lot consumed
        for step in deduction_plan:
            lot_id = step['lot_id']
            deduct_quantity = step['deduct_quantity']
            
            # Get the lot being consumed to get its details
            consumed_lot = db.session.get(UnifiedInventoryHistory, lot_id)
            
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
                **valid_kwargs
            )

            db.session.add(history_entry)
            logger.info(f"DEDUCTION RECORD: Created {change_type} record for -{deduct_quantity} from lot {lot_id}")

        return True

    except Exception as e:
        logger.error(f"Error recording deduction plan: {str(e)}")
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