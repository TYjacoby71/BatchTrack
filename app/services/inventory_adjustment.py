import inspect
import logging
from datetime import datetime

from flask import current_app
from flask_login import current_user
from sqlalchemy import and_, func

from app.models import db, InventoryHistory, InventoryItem
from app.models.product import ProductSKUHistory

logger = logging.getLogger(__name__)


# --- Core FIFO and Validation Logic (Internal Helpers) ---

def _get_fifo_entries(item_id, org_id, item_type):
    """Internal helper to fetch all active FIFO lots for an item, sorted oldest first."""
    model = ProductSKUHistory if item_type == 'product' else InventoryHistory
    return model.query.filter(
        and_(
            model.inventory_item_id == item_id,
            model.remaining_quantity > 0,
            model.organization_id == org_id
        )
    ).order_by(model.timestamp.asc()).all()


def validate_inventory_fifo_sync(item_id: int, item_type: str = None):
    """
    Validates that the InventoryItem's quantity matches the sum of all its FIFO lots.
    This is a critical health check before and after any adjustment.

    Returns:
        (is_valid, error_message, inventory_qty, fifo_total)
    """
    try:
        item = InventoryItem.query.get(item_id)
        if not item:
            return False, "Item not found", 0, 0

        # Determine item_type if not provided
        item_type = item_type or item.type

        org_id = item.organization_id
        fifo_entries = _get_fifo_entries(item_id, org_id, item_type)
        fifo_total = sum(float(entry.remaining_quantity) for entry in fifo_entries)
        inventory_quantity = float(item.quantity)

        if abs(inventory_quantity - fifo_total) > 0.001:
            error_msg = f"SYNC ERROR: Inventory quantity ({inventory_quantity}) does not match FIFO total ({fifo_total})."
            return False, error_msg, inventory_quantity, fifo_total

        return True, "Sync is valid.", inventory_quantity, fifo_total

    except Exception as e:
        logger.error(f"Error in validate_inventory_fifo_sync for item {item_id}: {e}", exc_info=True)
        return False, str(e), 0, 0


def record_audit_entry(item_id: int, change_type: str, notes: str, created_by: int = None, item_type: str = None, fifo_reference_id: int = None):
    """
    Creates a history entry for audit purposes ONLY (e.g., logging a recount step).
    It has no effect on quantity or FIFO lots (remaining_quantity is 0).
    """
    item = InventoryItem.query.get(item_id)
    if not item:
        logger.warning(f"Attempted to record audit entry for non-existent item_id {item_id}")
        return

    item_type = item_type or item.type
    history_cls = ProductSKUHistory if item_type == 'product' else InventoryHistory

    # Handle different attribute names between models ('note' vs 'notes')
    kwargs = {
        'inventory_item_id': item_id,
        'change_type': change_type,
        'quantity_change': 0.0,
        'remaining_quantity': 0.0,
        'unit': item.unit,
        'created_by': created_by,
        'organization_id': item.organization_id,
        'fifo_reference_id': fifo_reference_id
    }
    if history_cls == ProductSKUHistory:
        kwargs['notes'] = notes
    else:
        kwargs['note'] = notes

    audit_entry = history_cls(**kwargs)
    db.session.add(audit_entry)
    # The commit will be handled by the calling function.


# --- The Recount Handler (Rewritten & Corrected) ---

def handle_recount_adjustment(item_id: int, target_quantity: float, notes: str, created_by: int, item_type: str):
    """
    Sets an item's quantity to an absolute value and syncs FIFO lots accordingly.
    This is the rewritten, correct implementation based on your business rules.
    """
    item = InventoryItem.query.get(item_id)
    org_id = item.organization_id
    current_qty = float(item.quantity or 0.0)
    target_qty = float(target_quantity or 0.0)
    delta = target_qty - current_qty

    if abs(delta) < 0.001:
        logger.info(f"Recount for item '{item.name}' has no change. Skipping.")
        return

    logger.info(f"RECOUNT START: Item '{item.name}' from {current_qty} to {target_qty} (Delta: {delta})")
    all_lots = _get_fifo_entries(item_id, org_id, item_type)

    # POSITIVE RECOUNT (INCREASE)
    if delta > 0:
        remaining_to_add = delta
        # Use a real 'restock' transaction to create a new lot for the increase.
        # This is cleaner and more consistent than creating a special 'recount' lot.
        logger.info(f"Recount: Creating new 'restock' lot with {remaining_to_add} for recount delta.")
        process_inventory_adjustment(item_id, remaining_to_add, 'restock', notes=f"Recount Adjustment. {notes or ''}", created_by=created_by, item_type=item_type)

    # NEGATIVE RECOUNT (DECREASE)
    else:  # delta < 0
        to_remove = abs(delta)
        logger.info(f"Recount: Removing {to_remove} from lots for item '{item.name}'")
        for lot in all_lots:  # These are already sorted oldest-first
            if to_remove <= 0: break
            deduct_amount = min(to_remove, float(lot.remaining_quantity))
            if deduct_amount > 0:
                lot.remaining_quantity -= deduct_amount
                to_remove -= deduct_amount
                record_audit_entry(item_id, 'recount', f"Deducted {deduct_amount} from lot #{lot.id}. {notes or ''}", created_by, item_type, fifo_reference_id=lot.id)
                logger.info(f"Recount: Deducted {deduct_amount} from lot {lot.id}")

    # ABSOLUTE SYNC: Set the master quantity. The additions/deductions above updated the lots.
    item.quantity = target_qty


# --- The Canonical Entry Point (Restored & Robust) ---

def process_inventory_adjustment(
    item_id: int,
    quantity: float,
    change_type: str,
    unit: str = None,
    notes: str = None,
    created_by: int = None,
    item_type: str = None,
    **kwargs,
) -> bool:
    """
    The single, canonical service for ALL inventory adjustments.
    This function now contains the core logic for all change types.
    """
    caller_frame = inspect.currentframe().f_back
    caller_info = f"{caller_frame.f_code.co_filename}:{caller_frame.f_code.co_name}"
    logger.info(f"CANONICAL ADJUSTMENT: item_id={item_id}, qty={quantity}, type='{change_type}', caller='{caller_info}'")

    if not all([item_id, quantity, change_type]):
        raise ValueError("item_id, quantity, and change_type are required.")

    try:
        item = InventoryItem.query.get(item_id)
        if not item:
            raise ValueError(f"Inventory item not found for ID: {item_id}")

        item_type = item_type or item.type

        # Recounts are a special case that sets an absolute value.
        if change_type == 'recount':
            handle_recount_adjustment(item_id, quantity, notes, created_by, item_type)
        else:
            # All other types are relative changes (additive or deductive).
            qty_change = 0.0
            if change_type in ['restock', 'manual_addition', 'returned', 'refunded', 'finished_batch']:
                qty_change = abs(quantity)
            elif change_type in ['spoil', 'trash', 'expired', 'gift', 'sample', 'tester', 'quality_fail', 'damaged', 'sold', 'sale', 'use', 'batch', 'reserved']:
                qty_change = -abs(quantity)
            else:
                raise ValueError(f"Unsupported change_type: '{change_type}'")

            # --- Handle ADDITIONS (Creating new FIFO lots) ---
            if qty_change > 0:
                history_cls = ProductSKUHistory if item_type == 'product' else InventoryHistory
                kwargs = {
                    'inventory_item_id': item.id,
                    'quantity_change': qty_change,
                    'remaining_quantity': qty_change,
                    'change_type': change_type,
                    'unit': unit or item.unit,
                    'created_by': created_by,
                    'organization_id': item.organization_id,
                    'unit_cost': item.cost_per_unit
                }
                if history_cls == ProductSKUHistory: kwargs['notes'] = notes
                else: kwargs['note'] = notes

                new_lot = history_cls(**kwargs)
                db.session.add(new_lot)
                item.quantity += qty_change
                logger.info(f"ADDITION: Created new lot for item '{item.name}' with quantity {qty_change}")

            # --- Handle DEDUCTIONS (Consuming from existing FIFO lots) ---
            elif qty_change < 0:
                to_remove = abs(qty_change)
                all_lots = _get_fifo_entries(item_id, item.organization_id, item_type)
                available_qty = sum(float(lot.remaining_quantity) for lot in all_lots)

                if to_remove > available_qty:
                    raise ValueError(f"Insufficient stock for item '{item.name}'. Required: {to_remove}, Available: {available_qty}")

                for lot in all_lots:
                    if to_remove <= 0: break
                    deduct_amount = min(to_remove, float(lot.remaining_quantity))
                    if deduct_amount > 0:
                        lot.remaining_quantity -= deduct_amount
                        to_remove -= deduct_amount
                        record_audit_entry(item_id, change_type, f"Deducted {deduct_amount} from lot #{lot.id}. {notes or ''}", created_by, item_type, fifo_reference_id=lot.id)

                item.quantity += qty_change
                logger.info(f"DEDUCTION: Consumed {abs(qty_change)} from lots for item '{item.name}'")

        # Commit the entire transaction
        db.session.commit()

        # Final validation to ensure data integrity
        is_valid, error_msg, _, _ = validate_inventory_fifo_sync(item_id, item_type)
        if not is_valid:
            # This is a critical failure. Unfortunately, we can't rollback here as the commit is done.
            # This points to a need for more robust, pre-commit validation.
            # For now, we log a critical error.
            logger.critical(f"POST-COMMIT SYNC FAILURE for item {item_id}: {error_msg}")
            raise Exception("Inventory out of sync after commit.")

        return True

    except Exception as e:
        db.session.rollback()
        logger.error(f"Transaction failed in process_inventory_adjustment: {str(e)}", exc_info=True)
        raise e


# --- Backwards Compatibility Shim ---

class InventoryAdjustmentService:
    """
    A backwards-compatibility shim. New code should call the functions
    in this module directly. This will be removed in a future refactor (PR4).
    """
    @staticmethod
    def process_inventory_adjustment(*args, **kwargs):
        # TODO: Add a deprecation warning here in PR3
        return process_inventory_adjustment(*args, **kwargs)

    @staticmethod
    def validate_inventory_fifo_sync(*args, **kwargs):
        # TODO: Add a deprecation warning here in PR3
        return validate_inventory_fifo_sync(*args, **kwargs)