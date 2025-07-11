from flask import current_app
from flask_login import current_user
from app.models import db, InventoryItem, InventoryHistory
from datetime import datetime, timedelta
from app.services.conversion_wrapper import safe_convert
from app.services.unit_conversion import ConversionEngine
from app.blueprints.fifo.services import FIFOService

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
        all_fifo_entries = ProductSKUHistory.query.filter(
            and_(
                ProductSKUHistory.inventory_item_id == item_id,
                ProductSKUHistory.remaining_quantity > 0,
                ProductSKUHistory.organization_id == current_user.organization_id if current_user and current_user.is_authenticated else None
            )
        ).all()

        fifo_total = sum(entry.remaining_quantity for entry in all_fifo_entries)
        current_qty = item.quantity
        item_name = item.name
    else:
        item = InventoryItem.query.get(item_id)
        if not item:
            return False, "Item not found", 0, 0

        # Get ALL InventoryHistory entries with remaining quantity (including frozen expired ones)
        from sqlalchemy import and_
        all_fifo_entries = InventoryHistory.query.filter(
            and_(
                InventoryHistory.inventory_item_id == item_id,
                InventoryHistory.remaining_quantity > 0,
                InventoryHistory.organization_id == current_user.organization_id if current_user and current_user.is_authenticated else None
            )
        ).all()

        fifo_total = sum(entry.remaining_quantity for entry in all_fifo_entries)
        current_qty = item.quantity
        item_name = item.name

    # Allow small floating point differences (0.001)
    if abs(current_qty - fifo_total) > 0.001:
        error_msg = f"SYNC ERROR: {item_name} inventory ({current_qty}) != FIFO total ({fifo_total}) [includes frozen expired]"
        return False, error_msg, current_qty, fifo_total

    return True, "", current_qty, fifo_total

def process_inventory_adjustment(item_id, quantity, change_type, unit=None, notes=None, 
                                 created_by=None, batch_id=None, cost_override=None,
                                 custom_expiration_date=None, custom_shelf_life_days=None,
                                 item_type='ingredient', customer=None, sale_price=None, order_id=None):
    """
    Centralized inventory adjustment service that handles both ingredients and products
    with proper FIFO tracking and expiration management
    """
    try:
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
        elif change_type in ['spoil', 'trash', 'sold', 'sale', 'gift', 'sample', 'tester', 'quality_fail', 'expired_disposal', 'damaged', 'expired']:
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

        if custom_expiration_date:
            expiration_date = custom_expiration_date
            shelf_life_to_use = custom_shelf_life_days
        elif change_type == 'restock' and item.is_perishable and item.shelf_life_days:
            expiration_date = ExpirationService.calculate_expiration_date(
                datetime.utcnow(), item.shelf_life_days
            )
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
                FIFOService.add_fifo_entry(
                    inventory_item_id=item_id,
                    quantity=qty_change,
                    change_type=change_type,
                    unit=item.unit,
                    notes=notes,
                    cost_per_unit=cost_per_unit,
                    expiration_date=expiration_date,
                    shelf_life_days=shelf_life_to_use,
                    batch_id=batch_id,
                    created_by=created_by,
                    customer=customer,
                    sale_price=sale_price,
                    order_id=order_id
                )

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

        return True

    except Exception as e:
        db.session.rollback()
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
        history_unit = 'count' if item.type == 'container' else item.unit

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
                    fillable_entries = ProductSKUHistory.query.filter(
                        ProductSKUHistory.inventory_item_id == item_id,
                        ProductSKUHistory.quantity_change > 0,  # Only positive additions can be filled
                        ProductSKUHistory.organization_id == current_user.organization_id if current_user and current_user.is_authenticated else item.organization_id
                    ).order_by(ProductSKUHistory.timestamp.desc()).all()  # Fill newest first
                else:
                    fillable_entries = InventoryHistory.query.filter(
                        InventoryHistory.inventory_item_id == item_id,
                        InventoryHistory.quantity_change > 0,  # Only positive additions can be filled
                        InventoryHistory.organization_id == current_user.organization_id if current_user and current_user.is_authenticated else item.organization_id
                    ).order_by(InventoryHistory.timestamp.desc()).all()  # Fill newest first

                remaining_to_add = addition_needed

                # Fill existing lots with remaining capacity
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

                # Create new lot for any remaining quantity
                if remaining_to_add > 0:
                    print(f"RECOUNT: Creating new lot for remaining {remaining_to_add}")
                    FIFOService.add_fifo_entry(
                        inventory_item_id=item_id,
                        quantity=remaining_to_add,
                        change_type='recount',
                        unit=history_unit,
                        notes=f"New stock from recount: {notes or 'Physical count adjustment'}",
                        cost_per_unit=item.cost_per_unit,
                        created_by=created_by
                    )

        # Update inventory quantity to match target
        item.quantity = target_quantity

        # Don't create any summary entries - all recount events are handled by:
        # 1. FIFOService.create_deduction_history() for deductions (already creates proper FIFO entries)
        # 2. FIFOService.add_fifo_entry() for new lots (already creates proper FIFO entries)
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