from flask import current_app
from flask_login import current_user
from app.models import db, InventoryItem, UnifiedInventoryHistory
from datetime import datetime, timedelta
from app.services.conversion_wrapper import safe_convert
from app.services.unit_conversion import ConversionEngine
from sqlalchemy import func, and_
import logging
import inspect

# Import internal helpers - using relative imports within package
from ._validation import validate_inventory_fifo_sync
from ._fifo_ops import (_calculate_deduction_plan_internal, _execute_deduction_plan_internal,
                       _record_deduction_plan_internal, _internal_add_fifo_entry_enhanced)
from ._recount_logic import handle_recount_adjustment
from ._audit import record_audit_entry

# Initialize logger
logger = logging.getLogger(__name__)


def process_inventory_adjustment(
    item_id: int,
    quantity: float,
    change_type: str,
    unit: str = None,
    notes: str = None,
    created_by: int = None,
    cost_override: float = None,
    custom_expiration_date = None,
    custom_shelf_life_days: int = None
) -> bool:
    """
    Central function for all inventory adjustments with FIFO tracking.

    This is the single entry point for ALL inventory quantity changes in BatchTrack.
    It handles FIFO tracking, cost calculations, expiration management, and maintains
    complete audit trails through the UnifiedInventoryHistory system.

    Supported change types:
    - Additive: 'restock', 'manual_addition', 'returned', 'refunded'
    - Deductive: 'use', 'spoil', 'trash', 'expired', 'sold', 'batch', etc.
    - Special: 'recount' (absolute quantity), 'cost_override' (cost change only)

    Args:
        item_id (int): ID of the inventory item to adjust
        quantity (float): Amount to adjust. For deductive operations, use positive
                         values (the function will make them negative automatically)
        change_type (str): Type of change - must be a valid adjustment type
        unit (str, optional): Unit of measurement. Defaults to item's unit
        notes (str, optional): Description of the adjustment for audit trail
        created_by (int, optional): ID of user making the adjustment
        cost_override (float, optional): Override cost per unit for this entry
        custom_expiration_date (datetime, optional): Custom expiration for perishables
        custom_shelf_life_days (int, optional): Custom shelf life for perishables

    Returns:
        bool: True if adjustment was successful and FIFO sync is maintained,
              False if validation failed or database operation failed

    Raises:
        Exception: May raise exceptions for database errors or validation failures

    Examples:
        # Add new stock
        process_inventory_adjustment(123, 50, 'restock', 'kg', 'New shipment')

        # Use ingredients for production
        process_inventory_adjustment(123, 10, 'batch', 'kg', 'Batch #456')

        # Set absolute quantity
        process_inventory_adjustment(123, 75, 'recount', 'kg', 'Physical count')
    """
    from app.models.inventory import InventoryItem

    if custom_shelf_life_days is None:
        custom_shelf_life_days = kwargs.get("custom_shelf_life_days")

    # Extract optional metadata used downstream
    batch_id = kwargs.get("batch_id")
    order_id = kwargs.get("order_id")
    customer = kwargs.get("customer")
    sale_price = kwargs.get("sale_price")

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

    if quantity == 0 and change_type != 'recount':
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
        if current_user and current_user.is_authenticated and current_user.organization_id:
            if item.organization_id and item.organization_id != current_user.organization_id:
                raise ValueError("Access denied: Item does not belong to your organization")

        # Add unit fallback for when unit is None
        if unit is None:
            unit = getattr(item, "unit", None)

        # Convert units if needed
        # only attempt conversion when there's something to convert
        if item_type != "product" and getattr(item, "type", None) != "container" and unit and unit != item.unit:
            conversion = safe_convert(quantity, unit, item.unit, ingredient_id=item.id)
            if not conversion["ok"]:
                raise ValueError(conversion["error"])
            quantity = conversion["value"]

        # Determine quantity change and special handling
        current_quantity = item.quantity

        if change_type == 'recount':
            # Recount is special - handle independently from FIFO sync validation
            logger.info(f"RECOUNT: Processing recount from {current_quantity} to {quantity}")
            return handle_recount_adjustment(item_id, quantity, notes, created_by, item_type)
        elif change_type in ['spoil', 'trash', 'sold', 'sale', 'gift', 'sample', 'tester', 'quality_fail', 'damaged', 'expired', 'use', 'batch']:
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

        # Track whether we already applied the quantity mutation inside FIFO helpers
        qty_applied_in_fifo = False

        # Handle inventory changes using internal FIFO methods
        if qty_change < 0:
            # Deductions - calculate plan first
            deduction_plan, error_msg = _calculate_deduction_plan_internal(
                item_id, abs(qty_change), change_type
            )

            if not deduction_plan:
                raise ValueError(error_msg or "Insufficient inventory")

            # Handle reservations specially - create reservations FIRST before any FIFO changes
            if change_type == 'reserved':
                # Only products can be reserved
                if item.type != 'product':
                    raise ValueError("Only products can be reserved, not raw inventory")

                # Create reservation tracking with FIFO lot details BEFORE executing deductions
                from app.services.reservation_service import ReservationService

                reservations_created = []
                try:
                    for fifo_entry_id, qty_deducted, cost_per_unit_from_plan in deduction_plan:
                        reservation, error = ReservationService.create_reservation(
                            inventory_item_id=item_id,
                            quantity=qty_deducted,
                            order_id=order_id,
                            source_fifo_id=fifo_entry_id,
                            unit_cost=cost_per_unit_from_plan,
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

            # Execute the deduction plan ONLY after reservations are created successfully
            success, error_msg = _execute_deduction_plan_internal(deduction_plan, item_id)
            if not success:
                raise ValueError(error_msg or "Failed to execute deduction plan")

            # Record deduction history
            success = _record_deduction_plan_internal(
                item_id,
                deduction_plan,
                change_type,
                notes,
                batch_id=batch_id,
                created_by=created_by,
                customer=customer,
                sale_price=sale_price,
                order_id=order_id,
            )
            if not success:
                raise ValueError("Failed to record deduction history")
        elif qty_change > 0:
            # Additions - use internal FIFO methods
            if change_type == 'refunded' and batch_id:
                # TODO: Handle refund credits - for now use standard addition
                pass

            # Determine the correct unit for the history entry
            history_unit = 'count' if getattr(item, 'type', None) == 'container' else item.unit

            # Use the FIFO helper which creates both the history record and updates quantity
            success, error_msg = _internal_add_fifo_entry_enhanced(
                item_id=item_id,
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
                custom_expiration_date=expiration_date,
                custom_shelf_life_days=shelf_life_to_use
            )

            if not success:
                raise ValueError(error_msg or "Failed to add FIFO entry")

            qty_applied_in_fifo = True

        # For batch completions, ensure the inventory item inherits perishable settings
        if change_type == 'finished_batch' and batch_id:
            from ..models import Batch
            batch = Batch.query.get(batch_id)
            if batch and batch.is_perishable:
                # Set perishable data at inventory_item level
                item.is_perishable = True
                item.shelf_life_days = batch.shelf_life_days
                current_app.logger.info(f"Set inventory item {item.name} as perishable with {batch.shelf_life_days} day shelf life from batch {batch_id}")

        # Update inventory quantity with rounding only if not applied inside FIFO helper
        if not qty_applied_in_fifo:
            rounded_qty_change = ConversionEngine.round_value(qty_change, 3)
            item.quantity = ConversionEngine.round_value(item.quantity + rounded_qty_change, 3)
            logger.info(f"CORE: Updated inventory item {item_id} quantity directly: {item.quantity - rounded_qty_change} → {item.quantity}")

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