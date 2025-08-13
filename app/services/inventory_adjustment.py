# app/services/inventory_adjustment.py

import inspect
import logging
from datetime import datetime

from flask import current_app
from flask_login import current_user
from sqlalchemy import and_, func

from app.models import db, InventoryHistory, InventoryItem
# Import product models for type handling
from app.models.product import ProductSKU, ProductSKUHistory
from app.services.conversion_wrapper import safe_convert
from app.services.unit_conversion import ConversionEngine
# This utility is used in your original file, so we keep it.
from app.utils.fifo_generator import generate_fifo_code

logger = logging.getLogger(__name__)


# --- Main Functions (Preserved and Corrected) ---

def validate_inventory_fifo_sync(item_id, item_type=None):
    """
    (CORRECTED) Validates that inventory quantity matches the sum of ALL FIFO remaining quantities.
    This is the more robust version of the two original functions.
    """
    try:
        item = InventoryItem.query.get(item_id)
        if not item:
            return False, "Item not found", 0, 0

        item_type = item_type or item.type
        history_model = ProductSKUHistory if item_type == 'product' else InventoryHistory
        org_id = item.organization_id

        query = db.session.query(func.sum(history_model.remaining_quantity)).filter(
            history_model.inventory_item_id == item_id,
            history_model.remaining_quantity > 0
        )
        
        # Always add organization scoping
        if org_id:
            query = query.filter(history_model.organization_id == org_id)
            
        fifo_total = query.scalar() or 0.0

        current_qty = float(item.quantity or 0.0)

        if abs(current_qty - fifo_total) > 0.001:
            error_msg = f"SYNC ERROR: {item.name} inventory ({current_qty}) != FIFO total ({fifo_total})"
            return False, error_msg, current_qty, fifo_total

        return True, "Inventory is in sync", current_qty, fifo_total
    except Exception as e:
        logger.error(f"Error in validate_inventory_fifo_sync for item {item_id}: {e}", exc_info=True)
        return False, str(e), 0, 0


def credit_specific_lot(item_id: int, fifo_entry_id: int, qty: float, *, unit: str = None, notes: str = "") -> bool:
    """
    (PRESERVED & FIXED) Credits quantity back to a specific FIFO lot.
    The dependency on the external FIFOService has been removed.
    """
    history_model = ProductSKUHistory # Assuming products can be credited too. Adjust if not.
    fifo_entry = history_model.query.get(fifo_entry_id)
    if not fifo_entry:
        fifo_entry = InventoryHistory.query.get(fifo_entry_id)

    if not fifo_entry or fifo_entry.inventory_item_id != item_id:
        return False

    item = InventoryItem.query.get(item_id)
    if not item: return False

    try:
        credit_amount = abs(float(qty))
        fifo_entry.remaining_quantity = float(fifo_entry.remaining_quantity or 0) + credit_amount
        item.quantity = float(item.quantity or 0) + credit_amount

        # Create a linked audit entry for this credit action
        record_audit_entry(
            item_id=item_id,
            quantity=credit_amount,
            change_type="credit",
            notes=notes or f"Credited {credit_amount} back to lot #{fifo_entry_id}",
            fifo_reference_id=fifo_entry_id
        )
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error crediting lot {fifo_entry_id}: {e}", exc_info=True)
        return False


def record_audit_entry(item_id, quantity, change_type, unit=None, notes=None, created_by=None, **kwargs):
    """
    (CORRECTED) Creates an audit-only history entry with no effect on inventory quantity.
    This is the more robust version of the two original functions.
    """
    try:
        item = InventoryItem.query.get(item_id)
        if not item:
            return

        history_model = ProductSKUHistory if item.type == 'product' else InventoryHistory

        model_kwargs = {
            'inventory_item_id': item_id,
            'change_type': change_type,
            'quantity_change': quantity, # Record the intended quantity for context
            'remaining_quantity': 0.0,   # Does not become a new FIFO lot
            'unit': unit or item.unit,
            'created_by': created_by or (current_user.id if current_user.is_authenticated else None),
            'organization_id': item.organization_id,
            **kwargs
        }
        if history_model == ProductSKUHistory:
            model_kwargs['notes'] = notes
        else:
            model_kwargs['note'] = notes

        history_entry = history_model(**model_kwargs)
        db.session.add(history_entry)
        # The calling function is responsible for the commit.
    except Exception as e:
        logger.error(f"Error creating audit entry for item {item_id}: {e}", exc_info=True)


def _get_fifo_entries(item_id, org_id, item_type):
    """Helper function to get FIFO entries for an item"""
    history_model = ProductSKUHistory if item_type == 'product' else InventoryHistory
    
    query = history_model.query.filter(
        history_model.inventory_item_id == item_id,
        history_model.remaining_quantity > 0
    )
    
    # Always add organization scoping
    if org_id:
        query = query.filter(history_model.organization_id == org_id)
    
    return query.order_by(history_model.timestamp.asc()).all()

def handle_recount_adjustment(item_id, target_quantity, notes, created_by, item_type):
    """
    (PRESERVED & FIXED) Sets an absolute target quantity and syncs FIFO lots.
    This implements the user's specific business rules.
    """
    item = InventoryItem.query.get(item_id)
    if not item:
        raise ValueError(f"Item {item_id} not found")
        
    # Ensure we have the organization_id for proper scoping
    org_id = item.organization_id
    if not org_id:
        logger.warning(f"Item {item_id} has no organization_id - this could cause scoping issues")
    
    current_qty = float(item.quantity or 0.0)
    target_qty = float(target_quantity or 0.0)
    delta = target_qty - current_qty

    if abs(delta) < 0.001:
        logger.info(f"Recount for item '{item.name}' has no change needed.")
        # Still validate and fix any sync issues
        all_lots = _get_fifo_entries(item_id, org_id, item_type)
        fifo_total = sum(float(lot.remaining_quantity) for lot in all_lots)
        if abs(target_qty - fifo_total) > 0.001:
            logger.warning(f"SYNC REPAIR: Item quantity {target_qty} doesn't match FIFO total {fifo_total}. Forcing sync.")
            item.quantity = fifo_total
            record_audit_entry(item_id, 0, 'recount', f"Auto-sync repair: Fixed quantity from {target_qty} to {fifo_total}. {notes or ''}", created_by=created_by)
        else:
            item.quantity = target_qty
        return

    logger.info(f"RECOUNT: Item '{item.name}' (org: {org_id}) from {current_qty} to {target_qty} (Delta: {delta})")
    all_lots = _get_fifo_entries(item_id, org_id, item_type)

    if delta > 0: # Increase
        process_inventory_adjustment(item.id, delta, 'restock', notes=f"Recount increase. {notes or ''}", created_by=created_by, item_type=item_type)
    else: # Decrease
        to_remove = abs(delta)
        for lot in all_lots:
            if to_remove <= 0: break
            deduct_amount = min(to_remove, float(lot.remaining_quantity))
            if deduct_amount > 0:
                lot.remaining_quantity -= deduct_amount
                # Ensure FIFO lot never goes below 0
                if lot.remaining_quantity < 0:
                    lot.remaining_quantity = 0.0
                to_remove -= deduct_amount
                record_audit_entry(item.id, -deduct_amount, 'recount', notes=f"Deducted from lot #{lot.id}. {notes or ''}", created_by=created_by, fifo_reference_id=lot.id)

    # Ensure item quantity never goes below 0
    if target_qty < 0:
        logger.warning(f"Recount target quantity {target_qty} is negative. Setting to 0.")
        target_qty = 0.0
    item.quantity = target_qty # Set the absolute final quantity


def process_inventory_adjustment(
    item_id: int, quantity: float, change_type: str,
    unit: str = None, notes: str = None, created_by: int = None,
    item_type: str = None, **kwargs
) -> bool:
    """
    (PRESERVED & FIXED) The main canonical service for all inventory adjustments.
    """
    try:
        item = InventoryItem.query.get(item_id)
        if not item: raise ValueError(f"Inventory item not found for ID: {item_id}")

        item_type = item_type or item.type
        created_by = created_by or (current_user.id if current_user.is_authenticated else None)

        if change_type == 'recount':
            handle_recount_adjustment(item_id, quantity, notes, created_by, item_type)
        else:
            # --- CONSOLIDATED CHANGE TYPE LOGIC ---
            ADDITIVE_TYPES = {'restock', 'manual_addition', 'returned', 'refunded', 'finished_batch'}
            DEDUCTIVE_TYPES = {'spoil', 'trash', 'expired', 'gift', 'sample', 'tester', 'quality_fail', 'damaged', 'sold', 'sale', 'use', 'batch', 'reserved'}

            if change_type in ADDITIVE_TYPES:
                qty_change = abs(quantity)
                history_model = ProductSKUHistory if item_type == 'product' else InventoryHistory
                model_kwargs = {'inventory_item_id': item.id, 'quantity_change': qty_change, 'remaining_quantity': qty_change, 'change_type': change_type, 'unit': unit or item.unit, 'created_by': created_by, 'organization_id': item.organization_id}
                if history_model == ProductSKUHistory: model_kwargs['notes'] = notes
                else: model_kwargs['note'] = notes
                db.session.add(history_model(**model_kwargs))
                item.quantity = float(item.quantity or 0) + qty_change

            elif change_type in DEDUCTIVE_TYPES:
                qty_change = -abs(quantity)
                to_remove = abs(quantity)
                
                # Ensure we have organization_id for proper scoping
                org_id = item.organization_id
                if not org_id:
                    logger.warning(f"Item {item_id} has no organization_id - this could cause scoping issues")
                
                all_lots = _get_fifo_entries(item_id, org_id, item_type)
                available = sum(float(l.remaining_quantity) for l in all_lots)
                
                if to_remove > available: 
                    raise ValueError(f"Insufficient stock for item {item_id} (org: {org_id}). Required: {to_remove}, Available: {available}")

                logger.info(f"FIFO DEDUCTION: Removing {to_remove} from {len(all_lots)} lots for item {item_id} (org: {org_id})")
                
                for lot in all_lots:
                    if to_remove <= 0: 
                        break
                    
                    current_remaining = float(lot.remaining_quantity)
                    deduct = min(to_remove, current_remaining)
                    
                    if deduct > 0:
                        lot.remaining_quantity = max(0.0, current_remaining - deduct)
                        to_remove -= deduct
                        logger.info(f"  Deducted {deduct} from lot #{lot.id}, remaining: {lot.remaining_quantity}")
                        
                        # Add the lot to the session so changes are tracked
                        db.session.add(lot)
                
                # Update item quantity
                new_item_qty = float(item.quantity or 0) + qty_change
                if new_item_qty < 0:
                    logger.warning(f"Item {item_id} quantity would go negative ({new_item_qty}). Setting to 0.")
                    item.quantity = 0.0
                else:
                    item.quantity = new_item_qty
                    
                record_audit_entry(item_id, qty_change, change_type, notes=notes, created_by=created_by)

            else:
                raise ValueError(f"Invalid or unsupported change_type: '{change_type}'")

        db.session.commit()

        # Final validation after commit
        is_valid, error_msg, _, _ = validate_inventory_fifo_sync(item_id, item_type)
        if not is_valid:
            logger.critical(f"POST-COMMIT SYNC ERROR on item {item_id}: {error_msg}")
            # In a real-world scenario, you would trigger an external alert here.
            # We can't rollback, but we must know about the data integrity issue.

        return True

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in process_inventory_adjustment for item {item_id}: {e}", exc_info=True)
        # Re-raise the exception so the calling route can handle it
        raise e


# --- Backwards Compatibility Shim ---

class InventoryAdjustmentService:
    """
    (PRESERVED) Backwards compatibility shim for tests and legacy code.
    New code should call the functions in this module directly.
    """
    @staticmethod
    def process_inventory_adjustment(*args, **kwargs):
        return process_inventory_adjustment(*args, **kwargs)

    @staticmethod
    def validate_inventory_fifo_sync(*args, **kwargs):
        return validate_inventory_fifo_sync(*args, **kwargs)

    @staticmethod
    def record_audit_entry(*args, **kwargs):
        return record_audit_entry(*args, **kwargs)