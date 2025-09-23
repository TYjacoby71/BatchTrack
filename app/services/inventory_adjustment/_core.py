import logging
from app.models import db, InventoryItem, UnifiedInventoryHistory
from app.services.unit_conversion import ConversionEngine
from ._validation import validate_inventory_fifo_sync
from app.services.costing_engine import weighted_average_cost_for_item

# Import operation modules directly
from ._additive_ops import _universal_additive_handler, ADDITIVE_OPERATION_GROUPS
from ._deductive_ops import _handle_deductive_operation, DEDUCTIVE_OPERATION_GROUPS
from ._special_ops import handle_cost_override, handle_unit_conversion, handle_recount
from app.services.event_emitter import EventEmitter

logger = logging.getLogger(__name__)

def process_inventory_adjustment(item_id, change_type, quantity, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, customer=None, sale_price=None, order_id=None, target_quantity=None, unit=None, batch_id=None, defer_commit=False):
    """
    CENTRAL DELEGATOR - The single entry point for ALL inventory adjustments.

    Flow:
    1. Receive request with change_type
    2. Delegate to appropriate operation module
    3. Collect results (quantity_delta, messages)
    4. Apply quantity change (ONLY place that modifies item.quantity)
    5. Validate FIFO sync
    6. Return consolidated result
    """
    logger.info(f"CENTRAL DELEGATOR: item_id={item_id}, qty={quantity}, type={change_type}")

    item = db.session.get(InventoryItem, item_id)
    if not item:
        return False, "Inventory item not found."

    # Store original quantity for logging
    original_quantity = float(item.quantity)

    # Check if this is the first entry for this item
    is_initial_stock = UnifiedInventoryHistory.query.filter_by(inventory_item_id=item.id).count() == 0

    # Route to initial_stock handler ONLY if it's the first entry and the quantity is positive (additive)
    # Otherwise, preserve the original change_type to avoid creating negative lots
    try:
        qty_float = float(quantity)
    except Exception:
        qty_float = 0.0
    effective_change_type = 'initial_stock' if (is_initial_stock and qty_float > 0) else change_type

    try:
        # Normalize quantity to the item's canonical unit if a different unit was provided
        normalized_quantity = quantity
        if unit and item.unit and unit != item.unit:
            try:
                conv = ConversionEngine.convert_units(
                    amount=float(quantity),
                    from_unit=unit,
                    to_unit=item.unit,
                    ingredient_id=item.id,
                    density=item.density
                )
                if conv and conv.get('converted_value') is not None:
                    normalized_quantity = conv['converted_value']
                    logger.info(f"UNIT NORMALIZATION: {quantity} {unit} -> {normalized_quantity} {item.unit} for item {item.id}")
                else:
                    db.session.rollback()
                    logger.error(f"Unit conversion returned None for item {item.id}: {unit} -> {item.unit}")
                    return False, f"Cannot convert {unit} to {item.unit}. Please check unit compatibility or use the item's default unit ({item.unit})."
            except Exception as e:
                db.session.rollback()
                logger.error(f"Unit conversion failed for item {item.id}: {e}")
                return False, f"Unit conversion failed: {str(e)}"

        # CENTRAL DELEGATION - Route to appropriate operation module
        result = _delegate_to_operation_module(
            effective_change_type=effective_change_type,
            original_change_type=change_type,
            item=item,
            quantity=normalized_quantity,
            notes=notes,
            created_by=created_by,
            cost_override=cost_override,
            custom_expiration_date=custom_expiration_date,
            custom_shelf_life_days=custom_shelf_life_days,
            customer=customer,
            sale_price=sale_price,
            order_id=order_id,
            target_quantity=target_quantity,
            unit=item.unit or unit,
            batch_id=batch_id
        )

        # Handle different return formats for backwards compatibility
        if len(result) == 2:
            success, message = result
            quantity_delta = None
        elif len(result) == 3:
            success, message, quantity_delta = result
        else:
            logger.error(f"Operation returned unexpected format: {result}")
            return False, "Operation returned invalid response format"

        if not success:
            db.session.rollback()
            logger.error(f"DELEGATION FAILED: {change_type} operation failed for item {item.id}: {message}")
            return False, message

        # CENTRAL QUANTITY CONTROL - Only this core function modifies item.quantity
        if quantity_delta is not None:
            current_quantity = float(item.quantity)
            new_quantity = current_quantity + quantity_delta
            item.quantity = new_quantity

            # Log the operation correctly for readability
            if quantity_delta >= 0:
                logger.info(f"QUANTITY UPDATE: Item {item.id} quantity {current_quantity} + {quantity_delta} = {new_quantity}")
            else:
                logger.info(f"QUANTITY UPDATE: Item {item.id} quantity {current_quantity} - {abs(quantity_delta)} = {new_quantity}")
        elif change_type == 'recount' and target_quantity is not None:
            # Special case for recount - set absolute quantity
            logger.info(f"RECOUNT: Item {item.id} quantity {item.quantity} -> {target_quantity}")
            item.quantity = float(target_quantity)

        # Validate FIFO sync before commit
        try:
            is_valid, error_msg, inv_qty, fifo_total = validate_inventory_fifo_sync(item_id)

            if not is_valid:
                logger.error(f"FIFO VALIDATION FAILED before commit for item {item_id}: {error_msg}")
                db.session.rollback()
                return False, f"FIFO validation failed: {error_msg}"

        except Exception as e:
            logger.error(f"FIFO VALIDATION ERROR for item {item_id}: {str(e)}")
            db.session.rollback()
            return False, f"FIFO validation error: {str(e)}"

        # Update master item's moving average cost (WAC) based on active lots regardless of FIFO or Average toggle
        try:
            new_wac = weighted_average_cost_for_item(item.id)
            # Only update if it materially changed to avoid noisy writes
            try:
                current = float(item.cost_per_unit or 0.0)
            except Exception:
                current = 0.0
            if abs((new_wac or 0.0) - current) > 1e-9:
                item.cost_per_unit = float(new_wac or 0.0)
        except Exception:
            # Do not fail the adjustment because of WAC recompute issues
            pass

        # Commit database changes unless caller defers commit for an outer transaction
        try:
            if defer_commit:
                logger.info(f"SUCCESS (DEFERRED): {change_type} prepared for item {item.id} (FIFO validated)")
                return True, message
            else:
                db.session.commit()
                logger.info(f"SUCCESS: {change_type} completed for item {item.id} (FIFO validated)")

                # Emit domain event (non-blocking best-effort; don't fail the operation on emitter errors)
                try:
                    EventEmitter.emit(
                        event_name='inventory_adjusted',
                        properties={
                            'change_type': change_type,
                            'quantity_delta': quantity_delta if quantity_delta is not None else (target_quantity - original_quantity if change_type == 'recount' and target_quantity is not None else None),
                            'unit': item.unit,
                            'notes': notes,
                            'cost_override': cost_override,
                            'original_quantity': original_quantity,
                            'new_quantity': float(item.quantity),
                            'item_name': item.name,
                            'item_type': item.type,
                            'batch_id': batch_id,
                            'is_initial_stock': is_initial_stock,
                        },
                        organization_id=item.organization_id,
                        user_id=created_by,
                        entity_type='inventory_item',
                        entity_id=item.id,
                        auto_commit=False
                    )
                except Exception:
                    pass

                return True, message

        except Exception as e:
            logger.error(f"FAILED: Database commit failed for item {item_id}: {str(e)}")
            db.session.rollback()
            return False, f"Database error: {str(e)}"

    except Exception as e:
        db.session.rollback()
        logger.error(f"Central delegation error for {change_type} on item {item.id}: {e}", exc_info=True)
        return False, "A critical internal error occurred."


def _delegate_to_operation_module(effective_change_type, original_change_type, item, quantity, notes, created_by, cost_override, custom_expiration_date, custom_shelf_life_days, customer, sale_price, order_id, target_quantity, unit, batch_id):
    """
    DELEGATION LOGIC - Routes to appropriate operation module based on change type
    """
    logger.info(f"DELEGATING: {effective_change_type} -> routing to operation module")

    # Check if it's an additive operation
    for group_name, group_config in ADDITIVE_OPERATION_GROUPS.items():
        if effective_change_type in group_config['operations']:
            logger.info(f"ROUTING: {effective_change_type} -> ADDITIVE ({group_name})")
            return _universal_additive_handler(
                item=item,
                quantity=quantity,
                change_type=original_change_type,  # Preserve original intent
                notes=notes,
                created_by=created_by,
                cost_override=cost_override,
                custom_expiration_date=custom_expiration_date,
                custom_shelf_life_days=custom_shelf_life_days,
                unit=unit,
                batch_id=batch_id
            )

    # Check if it's a deductive operation
    for group_name, group_config in DEDUCTIVE_OPERATION_GROUPS.items():
        if effective_change_type in group_config['operations']:
            logger.info(f"ROUTING: {effective_change_type} -> DEDUCTIVE ({group_name})")
            return _handle_deductive_operation(
                item=item,
                quantity=quantity,
                change_type=original_change_type,
                notes=notes,
                created_by=created_by,
                customer=customer,
                sale_price=sale_price,
                order_id=order_id,
                batch_id=batch_id
            )

    # Check for special operations
    if effective_change_type == 'recount':
        logger.info(f"ROUTING: {effective_change_type} -> RECOUNT (special)")
        return handle_recount(
            item=item,
            quantity=quantity,
            change_type=original_change_type,
            notes=notes,
            created_by=created_by,
            target_quantity=target_quantity,
            unit=unit,
            batch_id=batch_id
        )
    elif effective_change_type == 'cost_override':
        logger.info(f"ROUTING: {effective_change_type} -> COST_OVERRIDE (special)")
        return handle_cost_override(
            item=item,
            quantity=quantity,
            change_type=original_change_type,
            notes=notes,
            created_by=created_by,
            cost_override=cost_override,
            unit=unit,
            batch_id=batch_id
        )
    elif effective_change_type == 'unit_conversion':
        logger.info(f"ROUTING: {effective_change_type} -> UNIT_CONVERSION (special)")
        return handle_unit_conversion(
            item=item,
            quantity=quantity,
            change_type=original_change_type,
            notes=notes,
            created_by=created_by,
            unit=unit,
            batch_id=batch_id
        )

    # Handle initial_stock as special additive case
    if effective_change_type == 'initial_stock':
        logger.info(f"ROUTING: {effective_change_type} -> INITIAL_STOCK (additive special case)")
        return _universal_additive_handler(
            item=item,
            quantity=quantity,
            change_type='restock',  # Treat as restock for processing
            notes=notes or "Initial stock entry",
            created_by=created_by,
            cost_override=cost_override,
            custom_expiration_date=custom_expiration_date,
            custom_shelf_life_days=custom_shelf_life_days,
            unit=unit,
            batch_id=batch_id
        )

    # Unknown operation type
    logger.error(f"ROUTING ERROR: Unknown change type '{effective_change_type}'")
    return False, f"Unknown inventory change type: '{effective_change_type}'"