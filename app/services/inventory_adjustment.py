from flask import current_app
from flask_login import current_user
from app.models import db, InventoryItem, InventoryHistory
from datetime import datetime, timedelta
from app.services.conversion_wrapper import safe_convert
from app.services.unit_conversion import ConversionEngine
from sqlalchemy import func, and_
import logging

# Import FIFOService to handle inventory operations
from app.blueprints.fifo.services import FIFOService

# Initialize logger
logger = logging.getLogger(__name__)

# FIFO logic moved inline to avoid blueprint imports

def validate_inventory_fifo_sync(item_id):
    """Validate that inventory quantity matches FIFO totals"""
    from app.models import InventoryItem, InventoryHistory
    from sqlalchemy import and_

    item = InventoryItem.query.get(item_id)
    if not item:
        return False, "Item not found", 0, 0

    # Get sum of remaining quantities from FIFO entries
    fifo_entries = InventoryHistory.query.filter(
        and_(
            InventoryHistory.inventory_item_id == item_id,
            InventoryHistory.remaining_quantity > 0
        )
    ).all()

    fifo_total = sum(float(entry.remaining_quantity) for entry in fifo_entries)
    inventory_qty = float(item.quantity)

    # Allow small floating point differences
    tolerance = 0.001
    is_valid = abs(inventory_qty - fifo_total) < tolerance

    if not is_valid:
        error_msg = f"FIFO sync error: inventory={inventory_qty}, fifo_total={fifo_total}, diff={abs(inventory_qty - fifo_total)}"
        return False, error_msg, inventory_qty, fifo_total

    return True, None, inventory_qty, fifo_total


def _calculate_deduction_plan(item_id, required_quantity, organization_id):
    """Calculate which FIFO entries to deduct from and how much"""
    from app.models import InventoryHistory
    from sqlalchemy import and_

    # Get available FIFO entries ordered by creation (FIFO)
    available_entries = InventoryHistory.query.filter(
        and_(
            InventoryHistory.inventory_item_id == item_id,
            InventoryHistory.remaining_quantity > 0
        )
    ).order_by(InventoryHistory.timestamp.asc()).all()

    deduction_plan = []
    remaining_needed = float(required_quantity)

    for entry in available_entries:
        if remaining_needed <= 0:
            break

        available_qty = float(entry.remaining_quantity)
        deduct_from_entry = min(available_qty, remaining_needed)

        deduction_plan.append({
            'entry_id': entry.id,
            'deduct_quantity': deduct_from_entry,
            'new_remaining': available_qty - deduct_from_entry
        })

        remaining_needed -= deduct_from_entry

    if remaining_needed > 0:
        return None, f"Insufficient inventory: need {required_quantity}, available {required_quantity - remaining_needed}"

    return deduction_plan, None


def _execute_deduction_plan(deduction_plan):
    """Execute the calculated deduction plan"""
    from app.models import InventoryHistory, db

    for step in deduction_plan:
        entry = InventoryHistory.query.get(step['entry_id'])
        if not entry:
            return False, f"FIFO entry {step['entry_id']} not found"

        entry.remaining_quantity = step['new_remaining']
        logging.info(f"Updated InventoryHistory entry {entry.id}: remaining_quantity now {entry.remaining_quantity}")

    try:
        db.session.flush()
        return True, None
    except Exception as e:
        return False, f"Database error during deduction: {str(e)}"


def _internal_add_fifo_entry(item_id, quantity, unit, cost_per_unit, change_type, notes, created_by, custom_expiration_date=None, custom_shelf_life_days=None):
    """Add a new FIFO entry for inventory additions"""
    from app.models import InventoryHistory, InventoryItem, db
    from datetime import datetime, timedelta

    item = InventoryItem.query.get(item_id)
    if not item:
        return False, "Item not found"

    # Calculate expiration data
    expiration_date = None
    shelf_life_days = None
    is_perishable = False

    if item.is_perishable:
        is_perishable = True
        if custom_expiration_date:
            expiration_date = custom_expiration_date
        elif custom_shelf_life_days and custom_shelf_life_days > 0:
            shelf_life_days = custom_shelf_life_days
            expiration_date = datetime.utcnow().date() + timedelta(days=shelf_life_days)
        elif item.shelf_life_days and item.shelf_life_days > 0:
            shelf_life_days = item.shelf_life_days
            expiration_date = datetime.utcnow().date() + timedelta(days=shelf_life_days)

    # Create FIFO entry
    history_entry = InventoryHistory(
        inventory_item_id=item_id,
        change_type=change_type,
        quantity_change=quantity,
        unit=unit,
        unit_cost=cost_per_unit,
        note=notes,
        created_by=created_by,
        remaining_quantity=quantity,  # New additions start with full quantity remaining
        is_perishable=is_perishable,
        shelf_life_days=shelf_life_days,
        expiration_date=expiration_date,
        quantity_used=0.0  # New entries haven't been used yet
    )

    try:
        db.session.add(history_entry)
        db.session.flush()
        return True, None
    except Exception as e:
        return False, f"Error creating FIFO entry: {str(e)}"


def update_inventory_item(item_id, form_data):
    """Handle all inventory item updates through the canonical service"""
    from app.models import InventoryItem, InventoryHistory, IngredientCategory, db
    from flask import session
    from flask_login import current_user
    from sqlalchemy import and_

    try:
        item = InventoryItem.query.get_or_404(item_id)

        # Handle unit changes with conversion confirmation
        if item.type != 'container':
            new_unit = form_data.get('unit')
            if new_unit != item.unit:
                history_count = InventoryHistory.query.filter_by(inventory_item_id=item_id).count()
                if history_count > 0:
                    confirm_unit_change = form_data.get('confirm_unit_change') == 'true'
                    convert_inventory = form_data.get('convert_inventory') == 'true'

                    if not confirm_unit_change:
                        session['pending_unit_change'] = {
                            'item_id': item_id,
                            'old_unit': item.unit,
                            'new_unit': new_unit,
                            'current_quantity': item.quantity
                        }
                        return False, f'Unit change requires confirmation. Item has {history_count} transaction history entries.'

                    if convert_inventory and item.quantity > 0:
                        try:
                            from app.services.unit_conversion import convert_unit
                            converted_quantity = convert_unit(item.quantity, item.unit, new_unit, item.density)
                            item.quantity = converted_quantity

                            history = InventoryHistory(
                                inventory_item_id=item.id,
                                change_type='unit_conversion',
                                quantity_change=0,
                                unit=new_unit,
                                note=f'Unit converted from {item.unit} to {new_unit}',
                                created_by=current_user.id,
                                quantity_used=0.0
                            )
                            db.session.add(history)
                        except Exception as e:
                            return False, f'Could not convert inventory to new unit: {str(e)}'

                    session.pop('pending_unit_change', None)

        # Update basic fields
        item.name = form_data.get('name')
        new_quantity = float(form_data.get('quantity'))

        # Handle perishable status changes
        is_perishable = form_data.get('is_perishable') == 'on'
        was_perishable = item.is_perishable
        old_shelf_life = item.shelf_life_days
        item.is_perishable = is_perishable

        if is_perishable:
            shelf_life_days = int(form_data.get('shelf_life_days', 0))
            item.shelf_life_days = shelf_life_days
            from datetime import datetime, timedelta
            if shelf_life_days > 0:
                item.expiration_date = datetime.utcnow().date() + timedelta(days=shelf_life_days)

                if not was_perishable or old_shelf_life != shelf_life_days:
                    from app.blueprints.expiration.services import ExpirationService
                    ExpirationService.update_fifo_expiration_data(item.id, shelf_life_days)
        else:
            if was_perishable:
                item.shelf_life_days = None
                item.expiration_date = None

                fifo_entries = InventoryHistory.query.filter(
                    and_(
                        InventoryHistory.inventory_item_id == item.id,
                        InventoryHistory.remaining_quantity > 0
                    )
                ).all()

                for entry in fifo_entries:
                    entry.is_perishable = False
                    entry.shelf_life_days = None
                    entry.expiration_date = None

        # Handle quantity recount
        if new_quantity != item.quantity:
            success = process_inventory_adjustment(
                item_id=item.id,
                quantity=new_quantity,
                change_type='recount',
                unit=item.unit,
                notes="Manual quantity update via inventory edit",
                created_by=current_user.id
            )
            if not success:
                return False, 'Error updating quantity'

        # Handle cost override
        new_cost = float(form_data.get('cost_per_unit', 0))
        if form_data.get('override_cost') and new_cost != item.cost_per_unit:
            history = InventoryHistory(
                inventory_item_id=item.id,
                change_type='cost_override',
                quantity_change=0,
                unit=item.unit,
                unit_cost=new_cost,
                note=f'Cost manually overridden from {item.cost_per_unit} to {new_cost}',
                created_by=current_user.id,
                quantity_used=0.0
            )
            db.session.add(history)
            item.cost_per_unit = new_cost

        # Type-specific updates
        if item.type == 'container':
            item.storage_amount = float(form_data.get('storage_amount'))
            item.storage_unit = form_data.get('storage_unit')
        else:
            item.unit = form_data.get('unit')
            category_id = form_data.get('category_id')
            item.category_id = None if not category_id or category_id == '' else int(category_id)
            if not item.category_id:
                item.density = float(form_data.get('density', 1.0))
            else:
                category = IngredientCategory.query.get(item.category_id)
                if category and category.default_density:
                    item.density = category.default_density
                else:
                    item.density = None

        db.session.commit()
        return True, f'{item.type.title()} updated successfully.'

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating inventory item {item_id}: {str(e)}")
        return False, f'Error saving changes: {str(e)}'


def process_inventory_adjustment(
    item_id: int,
    quantity: float,
    change_type: str,
    unit: str | None = None,
    notes: str | None = None,
    created_by: int | None = None,
    cost_override: float | None = None,
    item_type: str | None = None,
    custom_shelf_life_days: int | None = None,
    **kwargs,
) -> bool:
    """
    Process inventory adjustments through a centralized, canonical service.
    """
    from app.models.inventory import InventoryItem

    if custom_shelf_life_days is None:
        custom_shelf_life_days = kwargs.get("custom_shelf_life_days")
    import inspect

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
            FIFOService.record_deduction_plan(
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
                    custom_expiration_date=expiration_date, # Using the determined expiration_date here
                    custom_shelf_life_days=shelf_life_to_use # Using the determined shelf_life_to_use here
                )
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
        if current_user and current_user.is_authenticated:
            if item.organization_id != current_user.organization_id:
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
        if item.type == 'product':
            from app.models.product import ProductSKUHistory
            from sqlalchemy import and_

            entries = ProductSKUHistory.query.filter(
                and_(
                    ProductSKUHistory.inventory_item_id == item_id,
                    ProductSKUHistory.remaining_quantity > 0,
                    ProductSKUHistory.organization_id == org_id
                )
            ).order_by(ProductSKUHistory.timestamp.asc()).all()  # Oldest first
        else:
            from sqlalchemy import and_

            entries = InventoryHistory.query.filter(
                and_(
                    InventoryHistory.inventory_item_id == item_id,
                    InventoryHistory.remaining_quantity > 0,
                    InventoryHistory.organization_id == org_id
                )
            ).order_by(InventoryHistory.timestamp.asc()).all()  # Oldest first

        # Calculate current FIFO total
        current_fifo_total = sum(float(entry.remaining_quantity) for entry in entries)
        print(f"RECOUNT: Current FIFO total: {current_fifo_total}")

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
                        if item.type == 'product':
                            from app.models.product import ProductSKUHistory
                            from app.utils.fifo_generator import generate_fifo_code

                            history = ProductSKUHistory(
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
                        else:
                            from app.utils.fifo_generator import generate_fifo_code

                            history = InventoryHistory(
                                inventory_item_id=item_id,
                                change_type='recount',
                                quantity_change=fill_amount,
                                remaining_quantity=0.0,  # Recount adjustments don't create new FIFO
                                unit=history_unit,
                                note=f"{notes or 'Recount fill'} - Added to existing lot {entry.id}",
                                created_by=created_by,
                                quantity_used=0.0,
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
                if item.type == 'product':
                    from app.models.product import ProductSKUHistory
                    from app.utils.fifo_generator import generate_fifo_code

                    overflow_lot = ProductSKUHistory(
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
                else:
                    from app.utils.fifo_generator import generate_fifo_code

                    overflow_lot = InventoryHistory(
                        inventory_item_id=item_id,
                        change_type='recount',
                        quantity_change=remaining_to_add,
                        remaining_quantity=remaining_to_add,  # New lot with full quantity
                        unit=history_unit,
                        note=f"{notes or 'Recount overflow'} - New lot for overflow",
                        created_by=created_by,
                        quantity_used=0.0,
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
                if item.type == 'product':
                    from app.models.product import ProductSKUHistory
                    entry = ProductSKUHistory.query.get(entry_id)
                else:
                    entry = InventoryHistory.query.get(entry_id)

                if entry:
                    entry.remaining_quantity = float(entry.remaining_quantity) - qty_to_deduct
                    print(f"RECOUNT: Deducted {qty_to_deduct} from lot {entry_id}")

            # Create deduction history entries for audit trail
            if deduction_plan:
                if item.type == 'product':
                    from app.models.product import ProductSKUHistory
                    from app.utils.fifo_generator import generate_fifo_code

                    for entry_id, qty_deducted, unit_cost in deduction_plan:
                        history = ProductSKUHistory(
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
                else:
                    from app.utils.fifo_generator import generate_fifo_code

                    for entry_id, qty_deducted, unit_cost in deduction_plan:
                        history = InventoryHistory(
                            inventory_item_id=item_id,
                            change_type='recount',
                            quantity_change=-qty_deducted,
                            remaining_quantity=0.0,  # Deductions don't add new FIFO
                            unit=history_unit,
                            note=f"{notes or 'Recount deduction'} - Consumed from lot {entry_id}",
                            created_by=created_by,
                            quantity_used=0.0,
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
        if item.type == 'product':
            from app.models.product import ProductSKUHistory
            final_entries = ProductSKUHistory.query.filter(
                and_(
                    ProductSKUHistory.inventory_item_id == item_id,
                    ProductSKUHistory.remaining_quantity > 0,
                    ProductSKUHistory.organization_id == org_id
                )
            ).all()
        else:
            final_entries = InventoryHistory.query.filter(
                and_(
                    InventoryHistory.inventory_item_id == item_id,
                    InventoryHistory.remaining_quantity > 0,
                    InventoryHistory.organization_id == org_id
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


def audit_event(
    item_id: int,
    change_type: str,
    notes: str = "",
    created_by: int = None,
    item_type: str = "ingredient",
    fifo_reference_id: int = None,
    unit: str = None,
    unit_cost: float = None,
) -> bool:
    """
    Sanctioned audit-only history entry (no inventory change).
    Uses the same internal helpers so nothing writes outside this module.
    """
    from app.utils.fifo_generator import generate_fifo_code

    try:
        item = InventoryItem.query.get(item_id)
        if not item:
            return False

        fifo_code = generate_fifo_code(change_type, 0)

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
                fifo_code=fifo_code,
                fifo_reference_id=fifo_reference_id,
                unit_cost=unit_cost
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
                fifo_code=fifo_code,
                fifo_reference_id=fifo_reference_id,
                unit_cost=unit_cost
            )

        db.session.add(history)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating audit entry: {str(e)}")
        return False


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