from flask import current_app
from flask_login import current_user
from app.models import db, InventoryItem, InventoryHistory
from datetime import datetime, timedelta
from app.services.conversion_wrapper import safe_convert
from app.services.unit_conversion import ConversionEngine
from sqlalchemy import func, and_
import logging

# Initialize logger
logger = logging.getLogger(__name__)

# FIFO logic moved inline to avoid blueprint imports

def validate_inventory_fifo_sync(inventory_item_id, expected_total=None):
    """
    Validate that FIFO entries sum to inventory total
    Returns (is_valid, details)
    """
    try:
        item = InventoryItem.query.get(inventory_item_id)
        if not item:
            return False, "Inventory item not found"

        # Get current FIFO total
        fifo_total = db.session.query(func.sum(InventoryHistory.remaining_quantity)).filter(
            InventoryHistory.inventory_item_id == inventory_item_id,
            InventoryHistory.remaining_quantity > 0
        ).scalar() or 0

        # Compare with expected or actual inventory quantity
        target_quantity = expected_total if expected_total is not None else item.quantity

        is_valid = abs(float(fifo_total) - float(target_quantity)) < 0.001

        return is_valid, {
            'fifo_total': float(fifo_total),
            'inventory_quantity': float(target_quantity),
            'difference': float(fifo_total) - float(target_quantity),
            'is_valid': is_valid
        }

    except Exception as e:
        logger.error(f"Error validating FIFO sync for item {inventory_item_id}: {e}")
        return False, f"Validation error: {str(e)}"


def validate_inventory_fifo_sync(item_id, item_type=None):
    """
    Validates that inventory quantity matches sum of ALL FIFO remaining quantities (including frozen expired)
    Returns: (is_valid, error_message, inventory_qty, fifo_total)
    """
    # Handle different item types
    if item_type == 'product':
        from app.models.product import ProductSKU, ProductSKUHistory
        # For products, item_id should be inventory_item_id
        item = InventoryItem.query.get(item_id)
        if not item or item.type != 'product':
            return False, "Product inventory item not found", 0, 0

        # Find the SKU that uses this inventory item
        sku = ProductSKU.query.filter_by(inventory_item_id=item_id).first()
        if not sku:
            return False, "Product SKU not found for inventory item", 0, 0

        # Get ALL FIFO entries with remaining quantity (including frozen expired ones)
        from sqlalchemy import and_

        # Ensure we have the correct organization ID
        if current_user and current_user.is_authenticated:
            org_id = current_user.organization_id
        else:
            org_id = item.organization_id

        # Debug organization scoping
        print(f"DEBUG ProductSKU FIFO validation: item_id={item_id}, org_id={org_id}, current_user_org={current_user.organization_id if current_user else 'None'}")

        all_fifo_entries = ProductSKUHistory.query.filter(
            and_(
                ProductSKUHistory.inventory_item_id == item_id,
                ProductSKUHistory.remaining_quantity > 0,
                ProductSKUHistory.organization_id == org_id
            )
        ).all()

        print(f"DEBUG ProductSKU FIFO entries found: {len(all_fifo_entries)} for item {item_id}")

        fifo_total = sum(entry.remaining_quantity for entry in all_fifo_entries)
        current_qty = item.quantity
        item_name = item.name

        # If there are no FIFO entries but there is inventory, allow it for now
        # This handles cases where ProductSKUs exist but haven't had FIFO entries created yet
        if fifo_total == 0 and current_qty > 0:
            print(f"WARNING: Product SKU {item_name} has inventory ({current_qty}) but no FIFO entries - allowing operation to proceed")
            return True, "", current_qty, fifo_total
    else:
        item = InventoryItem.query.get(item_id)
        if not item:
            return False, "Item not found", 0, 0

        # Get ALL InventoryHistory entries with remaining quantity (including frozen expired ones)
        from sqlalchemy import and_

        # Ensure we have the correct organization ID
        if current_user and current_user.is_authenticated:
            org_id = current_user.organization_id
        else:
            org_id = item.organization_id

        # Debug organization scoping
        print(f"DEBUG Ingredient FIFO validation: item_id={item_id}, org_id={org_id}, current_user_org={current_user.organization_id if current_user else 'None'}")

        all_fifo_entries = InventoryHistory.query.filter(
            and_(
                InventoryHistory.inventory_item_id == item_id,
                InventoryHistory.remaining_quantity > 0,
                InventoryHistory.organization_id == org_id
            )
        ).all()

        print(f"DEBUG Ingredient FIFO entries found: {len(all_fifo_entries)} for item {item_id}")

        fifo_total = sum(entry.remaining_quantity for entry in all_fifo_entries)
        current_qty = item.quantity
        item_name = item.name

    # Allow small floating point differences (0.001)
    if abs(current_qty - fifo_total) > 0.001:
        error_msg = f"SYNC ERROR: {item_name} inventory ({current_qty}) != FIFO total ({fifo_total}) [includes frozen expired]"
        return False, error_msg, current_qty, fifo_total

    return True, "", current_qty, fifo_total

def credit_specific_lot(item_id: int, fifo_entry_id: int, qty: float, *, unit: str | None = None, notes: str = "") -> bool:
    """
    Public seam: credit quantity back to a specific FIFO lot.
    Keeps all mutations inside the canonical service.
    """
    from app.models.inventory import InventoryHistory
    from app.utils.fifo_generator import generate_fifo_code

    fifo_entry = InventoryHistory.query.get(fifo_entry_id)
    if not fifo_entry or fifo_entry.inventory_item_id != item_id:
        return False

    # mutate the lot here (allowed—inside canonical service)
    fifo_entry.remaining_quantity = float(fifo_entry.remaining_quantity or 0) + float(abs(qty))

    # write a linked history entry (reference the lot we credited)
    FIFOService.add_fifo_entry(
        inventory_item_id=item_id,
        quantity=abs(qty),                 # addition
        change_type="unreserved",          # or "credit"
        unit=unit or fifo_entry.unit,
        notes=notes or f"Credited back to lot #{fifo_entry_id}",
        fifo_reference_id=fifo_entry_id,
        fifo_code=generate_fifo_code("unreserved"),
        quantity_used=0.0,                 # credits don't consume inventory
    )
    db.session.commit()
    return True


def record_audit_entry(
    *,
    item_id: int,
    change_type: str = "audit",
    notes: str = "",
    unit: str | None = None,
    fifo_reference_id: int | None = None,
    source: str | None = None,
) -> None:
    """
    Public seam: write an audit-only history entry (no FIFO delta).
    Keeps routes/services from crafting raw history rows.
    """
    from app.utils.fifo_generator import generate_fifo_code

    FIFOService.add_fifo_entry(
        inventory_item_id=item_id,
        quantity=0.0,                      # no effect on available FIFO
        change_type=change_type,
        unit=unit,
        notes=notes,
        fifo_reference_id=fifo_reference_id,
        source=source,
        remaining_quantity=0.0,            # explicit for clarity
        quantity_used=0.0,
        fifo_code=generate_fifo_code(change_type),
    )
    db.session.commit()


def process_inventory_adjustment(
    item_id: int,
    quantity: float,
    change_type: str,
    unit: str | None = None,
    notes: str = "",
    batch_id: int | None = None,
    container_id: int | None = None,
    source: str | None = None,
    container_type: str | None = None,
    container_size: float | None = None,
    expiration_date=None,
    cost_per_unit: float | None = None,
    fifo_lot_reference: str | None = None
) -> bool:
    """
    CANONICAL ENTRY POINT for all inventory adjustments.

    This function ensures consistent processing of all inventory changes
    including FIFO ordering, organization scoping, and audit trails.

    Args:
        item_id: InventoryItem.id to adjust
        quantity: Amount to adjust (positive=add, negative=deduct)
        change_type: Type of change ('batch_production', 'restock', etc.)
        unit: Unit of measurement (optional, uses item default)
        notes: Description of the change
        created_by: User.id making the change
        batch_id: Associated Batch.id if applicable
        custom_expiration_date: Override expiration date
        item_type: Force item type routing ('ingredient', 'product', 'container')
        cost_override: Override cost per unit for this adjustment
        order_id: Associated Order.id if applicable (for reservations)
        customer: Customer information (for reservations)
        sale_price: Sale price per unit (for reservations)
        custom_shelf_life_days: Override shelf life in days

    Returns:
        bool: True if adjustment succeeded, False otherwise
    """
    import inspect

    # Log canonical entry point usage for audit
    caller_frame = inspect.currentframe().f_back
    caller_file = caller_frame.f_code.co_filename
    caller_function = caller_frame.f_code.co_name

    logger.info(f"CANONICAL INVENTORY ADJUSTMENT: item_id={item_id}, quantity={quantity}, "
               f"change_type={change_type}, caller={caller_file}:{caller_function}")

    # Validate required parameters
    if not item_id:
        logger.error("CANONICAL ENTRY: item_id is required")
        return False

    if quantity == 0:
        logger.warning("CANONICAL ENTRY: zero quantity adjustment requested")
        return True  # No-op but not an error
    # Start a transaction with explicit rollback protection
    try:
        # Pre-validate FIFO sync BEFORE starting any inventory changes (skip for recount)
        if change_type != 'recount':
            is_valid, error_msg, inv_qty, fifo_total = validate_inventory_fifo_sync(item_id, item_type)
            if not is_valid:
                raise ValueError(f"Pre-adjustment validation failed - FIFO sync error: {error_msg}")

        # Get the item - treat item_id as inventory_item_id for unified handling
        item = InventoryItem.query.get(item_id)

        if not item:
            raise ValueError(f"Inventory item not found for ID: {item_id}")

        # Organization scoping check
        if current_user and current_user.is_authenticated:
            if item.organization_id != current_user.organization_id:
                raise ValueError("Access denied: Item does not belong to your organization")

        # Convert units if needed (except for containers and products)
        if item_type != 'product' and getattr(item, 'type', None) != 'container' and unit != item.unit:
            conversion = safe_convert(quantity, unit, item.unit, ingredient_id=item.id)
            if not conversion['ok']:
                raise ValueError(conversion['error'])
            quantity = conversion['result']['converted_value']

        # Determine quantity change and special handling
        current_quantity = item.quantity

        if change_type == 'recount':
            # Recount is special - handle independently from FIFO sync validation
            return handle_recount_adjustment(item_id, quantity, notes, created_by, item_type)
        elif change_type in ['spoil', 'trash', 'sold', 'sale', 'gift', 'sample', 'tester', 'quality_fail', 'damaged', 'expired']:
            qty_change = -abs(quantity)
        elif change_type == 'reserved':
            # Handle reservation creation - deduct from available inventory
            qty_change = -abs(quantity)
        elif change_type == 'unreserved':
            # Unreserved operations should only be handled by ReservationService.release_reservation()
            # This should not be called directly through inventory adjustment
            raise ValueError("Unreserved operations must use ReservationService.release_reservation()")
        elif change_type == 'returned':
            qty_change = quantity
        else:
            qty_change = quantity

        # Handle expiration using ExpirationService
        from app.blueprints.expiration.services import ExpirationService

        expiration_date = None
        shelf_life_to_use = None

        is_perishable_override = expiration_date is not None or custom_shelf_life_days is not None

        if is_perishable_override:
            if expiration_date:
                expiration_date = expiration_date
            elif custom_shelf_life_days:
                expiration_date = ExpirationService.calculate_expiration_date(datetime.utcnow(), custom_shelf_life_days)
            shelf_life_to_use = custom_shelf_life_days
        elif item.is_perishable and item.shelf_life_days:
            # Use ExpirationService to get proper expiration date considering batch hierarchy
            expiration_date = ExpirationService.get_expiration_date_for_new_entry(item_id, batch_id)
            shelf_life_to_use = item.shelf_life_days

        # Handle cost calculations
        if change_type in ['spoil', 'trash']:
            cost_per_unit = None
        elif change_type in ['restock', 'finished_batch'] and qty_change > 0:
            # Calculate weighted average
            current_value = item.quantity * item.cost_per_unit
            new_value = qty_change * (cost_override or item.cost_per_unit)
            total_quantity = item.quantity + qty_change

            if total_quantity > 0:
                weighted_avg_cost = (current_value + new_value) / total_quantity
                item.cost_per_unit = weighted_avg_cost
            else: # If adding to zero quantity, use the new cost
                item.cost_per_unit = cost_override or item.cost_per_unit

            cost_per_unit = cost_override or item.cost_per_unit
        elif cost_override is not None and change_type == 'cost_override':
            cost_per_unit = cost_override
            item.cost_per_unit = cost_override
        else:
            cost_per_unit = item.cost_per_unit

        # Handle inventory changes using FIFO service
        if qty_change < 0:
            # Deductions - use FIFO service
            success, deduction_plan, available_qty = FIFOService.calculate_deduction_plan(
                item_id, abs(qty_change), change_type
            )

            if not success:
                raise ValueError("Insufficient fresh FIFO stock (expired lots frozen)")

            # Handle reservations specially - create reservations FIRST before any FIFO changes
            if change_type == 'reserved':
                # Only products can be reserved
                if item.type != 'product':
                    raise ValueError("Only products can be reserved, not raw inventory")

                # Create reservation tracking with FIFO lot details BEFORE executing deductions
                from app.services.reservation_service import ReservationService
                reservations_created = []
                try:
                    for fifo_entry_id, qty_deducted, cost_per_unit in deduction_plan:
                        reservation, error = ReservationService.create_reservation(
                            inventory_item_id=item_id,
                            quantity=qty_deducted,
                            order_id=order_id,
                            source_fifo_id=fifo_entry_id,
                            unit_cost=cost_per_unit,
                            customer=customer,
                            sale_price=sale_price,
                            notes=notes or f"Reserved for order {order_id}"
                        )
                        if error:
                            raise ValueError(f"Failed to create reservation: {error}")
                        reservations_created.append(reservation)
                except Exception as e:
                    # If reservation creation fails, don't execute FIFO deductions
                    raise ValueError(f"Reservation creation failed, no inventory changes made: {str(e)}")

            # Execute the deduction plan using FIFO service ONLY after reservations are created successfully
            FIFOService.execute_deduction_plan(deduction_plan, item_id)

            # Use FIFO service for all deductions - it routes to the correct history table
            FIFOService.create_deduction_history(
                item_id, deduction_plan, change_type, notes,
                batch_id=batch_id, created_by=created_by,
                customer=customer, sale_price=sale_price, order_id=order_id
            )
        elif qty_change > 0:
            # Additions - use FIFO service
            if change_type == 'refunded' and batch_id:
                # Handle refund credits using FIFO service
                FIFOService.handle_refund_credits(
                    item_id, qty_change, batch_id, notes, created_by, cost_per_unit
                )

            else:
                # Use FIFO service for all additions - it routes to the correct history table
                # Handle expiration data
                timestamp = datetime.utcnow()

                # Determine the correct unit for the history entry
                history_unit = 'count' if getattr(item, 'type', None) == 'container' else item.unit

                FIFOService._internal_add_fifo_entry(
                    inventory_item_id=item_id,
                    quantity=qty_change,
                    change_type=change_type,
                    unit=history_unit,
                    notes=notes,
                    cost_per_unit=cost_per_unit,
                    expiration_date=expiration_date,
                    shelf_life_days=shelf_life_to_use,
                    batch_id=batch_id,
                    created_by=created_by,
                    customer=customer,
                    sale_price=sale_price,
                    order_id=order_id,
                    custom_expiration_date=expiration_date, # Using the determined expiration_date here
                    custom_shelf_life_days=shelf_life_to_use # Using the determined shelf_life_to_use here
                )

        # For batch completions, ensure the inventory item inherits perishable settings
        if change_type == 'finished_batch' and batch_id:
            from ..models import Batch
            batch = Batch.query.get(batch_id)
            if batch and batch.is_perishable:
                # Set perishable data at inventory_item level
                item.is_perishable = True
                item.shelf_life_days = batch.shelf_life_days
                current_app.logger.info(f"Set inventory item {item.name} as perishable with {batch.shelf_life_days} day shelf life from batch {batch_id}")

        # Update inventory quantity with rounding
        rounded_qty_change = ConversionEngine.round_value(qty_change, 3)
        item.quantity = ConversionEngine.round_value(item.quantity + rounded_qty_change, 3)

        db.session.commit()

        # Validate inventory/FIFO sync after adjustment
        is_valid, error_msg, inv_qty, fifo_total = validate_inventory_fifo_sync(item_id, item_type)
        if not is_valid:
            # Rollback the transaction
            db.session.rollback()
            raise ValueError(f"Inventory adjustment failed validation: {error_msg}")

        # Final validation after all changes are complete but before commit
        final_is_valid, final_error_msg, final_inv_qty, final_fifo_total = validate_inventory_fifo_sync(item_id, item_type)
        if not final_is_valid:
            # Rollback the transaction
            db.session.rollback()
            raise ValueError(f"Post-adjustment validation failed - FIFO sync error: {final_error_msg}")

        # Commit only if everything validates
        db.session.commit()
        return True

    except Exception as e:
        # Ensure rollback on any error
        try:
            db.session.rollback()
        except Exception as rollback_error:
            # Log rollback error but don't mask original error
            print(f"WARNING: Failed to rollback transaction: {rollback_error}")
        raise e

def handle_recount_adjustment(item_id, target_quantity, notes=None, created_by=None, item_type='ingredient'):
    """
    Comprehensive recount handler that implements all recount business rules:
    1. Positive changes fill existing lots with capacity first, then create new lots
    2. Deductions take from available lots but never go negative
    3. Handles sync discrepancies by reconciling inventory vs FIFO totals
    4. Creates appropriate history entries for audit trail
    """
    try:
        # Get the item
        item = InventoryItem.query.get(item_id)
        if not item:
            raise ValueError(f"Inventory item not found for ID: {item_id}")

        # Organization scoping check
        if current_user and current_user.is_authenticated:
            if item.organization_id != current_user.organization_id:
                raise ValueError("Access denied: Item does not belong to your organization")

        # Get ALL FIFO entries (including expired) since recount counts physical inventory
        all_fifo_entries = FIFOService.get_all_fifo_entries(item_id)
        current_fifo_total = sum(entry.remaining_quantity for entry in all_fifo_entries)
        current_inventory_qty = item.quantity

        # Calculate what changes are needed
        inventory_change = target_quantity - current_inventory_qty
        fifo_change = target_quantity - current_fifo_total

        print(f"RECOUNT ANALYSIS:")
        print(f"  Target: {target_quantity}")
        print(f"  Current Inventory: {current_inventory_qty} (change: {inventory_change})")
        print(f"  Current FIFO Total: {current_fifo_total} (change: {fifo_change})")

        # Use same unit logic as other adjustments
        history_unit = 'count' if getattr(item, 'type', None) == 'container' else item.unit

        # Handle FIFO adjustments first
        if fifo_change != 0:
            if fifo_change < 0:
                # Need to reduce FIFO - deduct from existing lots
                deduction_needed = abs(fifo_change)

                # Protect against going negative - can't deduct more than we have
                if deduction_needed > current_fifo_total:
                    print(f"RECOUNT: Capping deduction at available FIFO total ({current_fifo_total})")
                    deduction_needed = current_fifo_total

                if deduction_needed > 0:
                    # Calculate deduction plan using oldest first (standard FIFO)
                    success, deduction_plan, _ = FIFOService.calculate_deduction_plan(
                        item_id, deduction_needed, 'recount'
                    )

                    if success:
                        # Execute deductions
                        FIFOService.execute_deduction_plan(deduction_plan, item_id)

                        # Create deduction history entries
                        FIFOService.create_deduction_history(
                            item_id, deduction_plan, 'recount', notes or "Recount deduction",
                            created_by=created_by
                        )
                        print(f"RECOUNT: Deducted {deduction_needed} from FIFO lots")
                    else:
                        print(f"RECOUNT: Could not calculate deduction plan")
            else:
                # Need to increase FIFO - fill existing lots first, then create new ones
                addition_needed = fifo_change

                # Get entries that can be filled (have remaining capacity)
                if item.type == 'product':
                    from app.models.product import ProductSKUHistory

                    # Ensure we have the correct organization ID
                    if current_user and current_user.is_authenticated:
                        org_id = current_user.organization_id
                    else:
                        org_id = item.organization_id

                    fillable_entries = ProductSKUHistory.query.filter(
                        ProductSKUHistory.inventory_item_id == item_id,
                        ProductSKUHistory.quantity_change > 0,  # Only positive additions can be filled
                        ProductSKUHistory.organization_id == org_id
                    ).order_by(ProductSKUHistory.timestamp.desc()).all()  # Fill newest first
                else:
                    # Ensure we have the correct organization ID
                    if current_user and current_user.is_authenticated:
                        org_id = current_user.organization_id
                    else:
                        org_id = item.organization_id

                    fillable_entries = InventoryHistory.query.filter(
                        InventoryHistory.inventory_item_id == item_id,
                        InventoryHistory.quantity_change > 0,  # Only positive additions can be filled
                        InventoryHistory.organization_id == org_id
                    ).order_by(InventoryHistory.timestamp.desc()).all()  # Fill newest first

                remaining_to_add = addition_needed

                # Fill existing lots with remaining capacity and log as recount additions
                for entry in fillable_entries:
                    if remaining_to_add <= 0:
                        break

                    available_capacity = entry.quantity_change - entry.remaining_quantity
                    fill_amount = min(available_capacity, remaining_to_add)

                    if fill_amount > 0:
                        old_remaining = entry.remaining_quantity
                        entry.remaining_quantity += fill_amount
                        remaining_to_add -= fill_amount

                        print(f"RECOUNT: Filled entry {entry.id} with {fill_amount} (from {old_remaining} to {entry.remaining_quantity})")

                        # Create a FIFO history entry for the positive recount addition
                        FIFOService._internal_add_fifo_entry(
                            inventory_item_id=item_id,
                            quantity=fill_amount,
                            change_type='recount',
                            unit=history_unit,
                            notes=f"Recount addition: {notes or 'Physical count adjustment'}",
                            cost_per_unit=item.cost_per_unit,
                            created_by=created_by
                        )

                # Create new lot for any remaining quantity
                if remaining_to_add > 0:
                    print(f"RECOUNT: Creating new lot for remaining {remaining_to_add}")
                    FIFOService._internal_add_fifo_entry(
                        inventory_item_id=item_id,
                        quantity=remaining_to_add,
                        change_type='recount',
                        unit=history_unit,
                        notes=f"Recount addition - new lot: {notes or 'Physical count adjustment'}",
                        cost_per_unit=item.cost_per_unit,
                        created_by=created_by
                    )

        # Update inventory quantity to match target
        item.quantity = target_quantity

        # Don't create any summary entries - all recount events are handled by:
        # 1. FIFOService.create_deduction_history() for deductions (already creates proper FIFO entries)
        # 2. FIFOService._internal_add_fifo_entry() for new lots (already creates proper FIFO entries)
        # 3. Direct FIFO entry updates for filling existing lots
        #
        # No additional summary entries are needed as all actions are properly logged
        # in their respective FIFO history tables with appropriate FIFO codes

        db.session.commit()

        # Validate final state
        final_fifo_entries = FIFOService.get_all_fifo_entries(item_id)
        final_fifo_total = sum(entry.remaining_quantity for entry in final_fifo_entries)

        print(f"RECOUNT FINAL STATE:")
        print(f"  Inventory: {item.quantity}")
        print(f"  FIFO Total: {final_fifo_total}")
        print(f"  Sync Status: {'✓' if abs(item.quantity - final_fifo_total) < 0.001 else '✗'}")

        return True

    except Exception as e:
        db.session.rollback()
        print(f"RECOUNT ERROR: {str(e)}")
        raise e


def record_audit_entry(item_id, quantity, change_type, unit=None, notes=None, created_by=None, **kwargs):
    """
    Public helper for audit-only records (remaining_quantity=0, no inventory change)
    Used for tracking reservations, conversions, etc. without affecting FIFO
    """
    try:
        item = InventoryItem.query.get(item_id)
        if not item:
            return False

        # Route to correct history table based on item type
        if item.type == 'product':
            from app.models.product import ProductSKUHistory
            history = ProductSKUHistory(
                inventory_item_id=item_id,
                change_type=change_type,
                quantity_change=0.0,  # Audit entries don't change quantity
                remaining_quantity=0.0,  # Audit entries have no FIFO impact
                unit=unit or item.unit,
                notes=notes,
                created_by=created_by,
                organization_id=current_user.organization_id if current_user.is_authenticated else item.organization_id,
                **kwargs
            )
        else:
            history = InventoryHistory(
                inventory_item_id=item_id,
                change_type=change_type,
                quantity_change=0.0,  # Audit entries don't change quantity
                remaining_quantity=0.0,  # Audit entries have no FIFO impact
                unit=unit or item.unit,
                note=notes,
                created_by=created_by,
                quantity_used=0.0,
                organization_id=current_user.organization_id if current_user.is_authenticated else item.organization_id,
                **kwargs
            )

        db.session.add(history)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating audit entry: {str(e)}")
        return False


class InventoryAdjustmentService:
    """Backwards compatibility shim for tests and legacy code"""

    @staticmethod
    def adjust_inventory(*args, **kwargs):
        """Legacy method - use process_inventory_adjustment instead"""
        return process_inventory_adjustment(*args, **kwargs)

    @staticmethod
    def process_inventory_adjustment(*args, **kwargs):
        return process_inventory_adjustment(*args, **kwargs)

    @staticmethod
    def validate_inventory_fifo_sync(*args, **kwargs):
        return validate_inventory_fifo_sync(*args, **kwargs)

    @staticmethod
    def record_audit_entry(*args, **kwargs):
        return record_audit_entry(*args, **kwargs)