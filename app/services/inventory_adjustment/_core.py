"""Inventory adjustment core delegator.

Synopsis:
Normalize inventory adjustments, delegate to handlers, and sync FIFO.

Glossary:
- Adjustment: Inventory change event (add, deduct, recount).
- Delegator: Central entry point for inventory changes.
"""

import logging
from typing import Any, Dict, Optional

from app.models import InventoryItem, UnifiedInventoryHistory, db
from app.services.analytics_tracking_service import AnalyticsTrackingService
from app.services.costing_engine import weighted_average_cost_for_item
from app.services.inventory_tracking_policy import (
    org_allows_inventory_quantity_tracking,
)
from app.services.quantity_base import (
    from_base_quantity,
    sync_item_quantity_from_base,
    to_base_quantity,
)
from app.services.unit_conversion import ConversionEngine

# Import operation modules directly
from ._additive_ops import ADDITIVE_OPERATION_GROUPS, _universal_additive_handler
from ._deductive_ops import DEDUCTIVE_OPERATION_GROUPS, _handle_deductive_operation
from ._special_ops import handle_cost_override, handle_recount, handle_unit_conversion
from ._validation import validate_inventory_fifo_sync

logger = logging.getLogger(__name__)

ADDITIVE_OPERATIONS = set()
for group in ADDITIVE_OPERATION_GROUPS.values():
    ADDITIVE_OPERATIONS.update(group.get("operations", []))


# --- Inventory adjustment ---
# Purpose: Central entry point for inventory adjustments.
# Inputs: Item/change metadata, optional costing/context fields, and commit mode flags.
# Outputs: Tuple of (success, message[, event_payload]) describing adjustment result.
def process_inventory_adjustment(
    item_id,
    change_type,
    quantity,
    notes=None,
    created_by=None,
    cost_override=None,
    custom_expiration_date=None,
    custom_shelf_life_days=None,
    customer=None,
    sale_price=None,
    order_id=None,
    target_quantity=None,
    unit=None,
    batch_id=None,
    defer_commit=False,
    include_event_payload: bool = False,
):
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
    logger.info(
        f"CENTRAL DELEGATOR: item_id={item_id}, qty={quantity}, type={change_type}"
    )

    def _response(
        success: bool, message: str, payload: Optional[Dict[str, Any]] = None
    ):
        if include_event_payload:
            return success, message, payload
        return success, message

    item = db.session.get(InventoryItem, item_id)
    if not item:
        return _response(False, "Inventory item not found.")

    if getattr(item, "quantity_base", None) is None:
        item.quantity_base = to_base_quantity(
            amount=item.quantity or 0.0,
            unit_name=item.unit,
            ingredient_id=item.id,
            density=item.density,
        )
        sync_item_quantity_from_base(item)

    # Store original quantity for logging (derived from base)
    original_quantity = from_base_quantity(
        base_amount=getattr(item, "quantity_base", 0),
        unit_name=item.unit,
        ingredient_id=item.id,
        density=item.density,
    )

    # Check if this is the first entry for this item
    is_initial_stock = (
        UnifiedInventoryHistory.query.filter_by(inventory_item_id=item.id).count() == 0
    )

    # Route to initial_stock handler ONLY if it's the first entry and the quantity is positive (additive)
    # Otherwise, preserve the original change_type to avoid creating negative lots
    try:
        qty_float = float(quantity)
    except Exception:
        qty_float = 0.0
    if is_initial_stock and qty_float > 0 and change_type in ADDITIVE_OPERATIONS:
        effective_change_type = "initial_stock"
    else:
        effective_change_type = change_type

    try:
        # Normalize quantity to the item's canonical unit if a different unit was provided
        normalized_quantity = quantity
        conversion_factor = None
        if unit and item.unit and unit != item.unit:
            try:
                amount_val = float(quantity)
                conv = ConversionEngine.convert_units(
                    amount=amount_val,
                    from_unit=unit,
                    to_unit=item.unit,
                    ingredient_id=item.id,
                    density=item.density,
                )
                if conv and conv.get("converted_value") is not None:
                    normalized_quantity = conv["converted_value"]
                    if amount_val:
                        conversion_factor = normalized_quantity / amount_val
                    logger.info(
                        f"UNIT NORMALIZATION: {quantity} {unit} -> {normalized_quantity} {item.unit} for item {item.id}"
                    )
                else:
                    db.session.rollback()
                    logger.error(
                        f"Unit conversion returned None for item {item.id}: {unit} -> {item.unit}"
                    )
                    return _response(
                        False,
                        f"Cannot convert {unit} to {item.unit}. Please check unit compatibility or use the item's default unit ({item.unit}).",
                    )
            except Exception as e:
                db.session.rollback()
                logger.error(f"Unit conversion failed for item {item.id}: {e}")
                return _response(False, f"Unit conversion failed: {str(e)}")

        # Normalize cost override to item's unit when a different unit was provided
        if cost_override is not None and unit and item.unit and unit != item.unit:
            if not conversion_factor:
                try:
                    conv_cost = ConversionEngine.convert_units(
                        amount=1.0,
                        from_unit=unit,
                        to_unit=item.unit,
                        ingredient_id=item.id,
                        density=item.density,
                    )
                    if conv_cost and conv_cost.get("converted_value") is not None:
                        conversion_factor = conv_cost["converted_value"]
                except Exception as e:
                    logger.error(f"Cost conversion failed for item {item.id}: {e}")
                    return _response(False, f"Cost conversion failed: {str(e)}")
            if not conversion_factor or conversion_factor <= 0:
                return _response(
                    False, f"Cannot convert cost from {unit} to {item.unit}."
                )
            try:
                original_cost = float(cost_override)
                cost_override = original_cost / conversion_factor
                logger.info(
                    "COST NORMALIZATION: %s per %s -> %s per %s for item %s",
                    original_cost,
                    unit,
                    cost_override,
                    item.unit,
                    item.id,
                )
            except (TypeError, ValueError):
                return _response(False, "Invalid cost provided.")

        # Convert normalized quantities to base integers for authoritative math
        normalized_quantity_base = to_base_quantity(
            amount=normalized_quantity,
            unit_name=item.unit or unit,
            ingredient_id=item.id,
            density=item.density,
        )
        target_quantity_base = None
        if change_type == "recount" and target_quantity is not None:
            target_quantity_base = to_base_quantity(
                amount=target_quantity,
                unit_name=item.unit or unit,
                ingredient_id=item.id,
                density=item.density,
            )

        # CENTRAL DELEGATION - Route to appropriate operation module
        result = _delegate_to_operation_module(
            effective_change_type=effective_change_type,
            original_change_type=change_type,
            item=item,
            quantity=normalized_quantity,
            quantity_base=normalized_quantity_base,
            notes=notes,
            created_by=created_by,
            cost_override=cost_override,
            custom_expiration_date=custom_expiration_date,
            custom_shelf_life_days=custom_shelf_life_days,
            customer=customer,
            sale_price=sale_price,
            order_id=order_id,
            target_quantity=target_quantity,
            target_quantity_base=target_quantity_base,
            unit=item.unit or unit,
            batch_id=batch_id,
        )

        # Handle different return formats for backwards compatibility
        if len(result) == 2:
            success, message = result
            quantity_delta = None
            quantity_delta_base = None
        elif len(result) == 3:
            success, message, quantity_delta = result
            quantity_delta_base = None
        elif len(result) == 4:
            success, message, quantity_delta, quantity_delta_base = result
        else:
            logger.error(f"Operation returned unexpected format: {result}")
            return _response(False, "Operation returned invalid response format")

        if not success:
            db.session.rollback()
            logger.error(
                f"DELEGATION FAILED: {change_type} operation failed for item {item.id}: {message}"
            )
            return _response(False, message)

        # CENTRAL QUANTITY CONTROL - Only this core function modifies item.quantity
        if quantity_delta_base is None and quantity_delta is not None:
            quantity_delta_base = to_base_quantity(
                amount=quantity_delta,
                unit_name=item.unit or unit,
                ingredient_id=item.id,
                density=item.density,
            )

        if quantity_delta_base is not None:
            current_base = int(getattr(item, "quantity_base", 0) or 0)
            new_base = current_base + int(quantity_delta_base)
            item.quantity_base = new_base
            sync_item_quantity_from_base(item)

            # Log the operation correctly for readability
            if quantity_delta is not None and quantity_delta >= 0:
                logger.info(
                    f"QUANTITY UPDATE: Item {item.id} quantity {original_quantity} + {quantity_delta} = {item.quantity}"
                )
            else:
                logger.info(
                    f"QUANTITY UPDATE: Item {item.id} quantity {original_quantity} - {abs(quantity_delta or 0)} = {item.quantity}"
                )
        elif change_type == "recount" and target_quantity_base is not None:
            # Special case for recount - set absolute quantity
            logger.info(
                f"RECOUNT: Item {item.id} quantity {item.quantity} -> {target_quantity}"
            )
            item.quantity_base = int(target_quantity_base)
            sync_item_quantity_from_base(item)

        org_tracks_quantities = org_allows_inventory_quantity_tracking(
            organization=getattr(item, "organization", None)
        )
        effective_tracking_enabled = (
            bool(getattr(item, "is_tracked", True)) and org_tracks_quantities
        )
        if not effective_tracking_enabled:
            # Infinite mode must always present as non-depleting stock.
            item.quantity_base = 0
            sync_item_quantity_from_base(item)

        # Validate FIFO sync before commit. During a multi-step batch start (defer_commit=True),
        # skip validation until outer transaction commits to avoid transient mismatch.
        try:
            if not defer_commit:
                is_valid, error_msg, inv_qty, fifo_total = validate_inventory_fifo_sync(
                    item_id
                )
            else:
                is_valid, error_msg = True, None

            if not is_valid:
                logger.error(
                    f"FIFO VALIDATION FAILED before commit for item {item_id}: {error_msg}"
                )
                db.session.rollback()
                return _response(False, f"FIFO validation failed: {error_msg}")

        except Exception as e:
            logger.error(f"FIFO VALIDATION ERROR for item {item_id}: {str(e)}")
            db.session.rollback()
            return _response(False, f"FIFO validation error: {str(e)}")

        # Update master item's moving average cost (WAC) only for additive ops; skip for deductions/spoilage
        try:
            is_additive = False
            for group_name, group_cfg in ADDITIVE_OPERATION_GROUPS.items():
                if effective_change_type in group_cfg["operations"]:
                    is_additive = True
                    break
            # Preserve additive semantics for remapped "initial_stock" operations
            if not is_additive and effective_change_type == "initial_stock":
                is_additive = True
            if is_additive:
                new_wac = weighted_average_cost_for_item(item.id)
                try:
                    current = float(item.cost_per_unit or 0.0)
                except Exception:
                    current = 0.0
                if abs((new_wac or 0.0) - current) > 1e-9:
                    item.cost_per_unit = float(new_wac or 0.0)
        except Exception:
            # Do not fail the adjustment because of WAC recompute issues
            pass

        if quantity_delta_base is not None:
            event_quantity_delta = from_base_quantity(
                base_amount=quantity_delta_base,
                unit_name=item.unit,
                ingredient_id=item.id,
                density=item.density,
            )
        else:
            event_quantity_delta = (
                quantity_delta if quantity_delta is not None else None
            )

        recount_delta = None
        if change_type == "recount" and target_quantity is not None:
            recount_delta = float(target_quantity) - float(original_quantity)

        event_properties = {
            "change_type": change_type,
            "quantity_delta": (
                event_quantity_delta
                if event_quantity_delta is not None
                else recount_delta
            ),
            "unit": item.unit,
            "notes": notes,
            "cost_override": cost_override,
            "original_quantity": original_quantity,
            "new_quantity": float(item.quantity),
            "item_name": item.name,
            "item_type": item.type,
            "batch_id": batch_id,
            "is_initial_stock": is_initial_stock,
        }
        event_payload: Dict[str, Any] = {
            "event_name": "inventory_adjusted",
            "properties": event_properties,
            "organization_id": item.organization_id,
            "user_id": created_by,
            "entity_type": "inventory_item",
            "entity_id": item.id,
        }

        # Commit database changes unless caller defers commit for an outer transaction
        try:
            if defer_commit:
                logger.info(
                    f"SUCCESS (DEFERRED): {change_type} prepared for item {item.id} (FIFO validated)"
                )
                return _response(True, message, event_payload)
            else:
                db.session.commit()
                logger.info(
                    f"SUCCESS: {change_type} completed for item {item.id} (FIFO validated)"
                )

                # Emit domain event (non-blocking best-effort; don't fail the operation on emitter errors)
                AnalyticsTrackingService.emit(**event_payload, auto_commit=False)

                return _response(
                    True, message, event_payload if include_event_payload else None
                )

        except Exception as e:
            logger.error(f"FAILED: Database commit failed for item {item_id}: {str(e)}")
            db.session.rollback()
            return _response(False, f"Database error: {str(e)}")

    except Exception as e:
        db.session.rollback()
        logger.error(
            f"Central delegation error for {change_type} on item {item.id}: {e}",
            exc_info=True,
        )
        return _response(False, "A critical internal error occurred.")


# --- Operation module delegator ---
# Purpose: Route normalized adjustments to additive, deductive, or special handlers.
# Inputs: Normalized operation context and all adjustment arguments required by downstream handlers.
# Outputs: Handler tuple response in legacy-compatible formats (2/3/4 items).
def _delegate_to_operation_module(
    effective_change_type,
    original_change_type,
    item,
    quantity,
    quantity_base,
    notes,
    created_by,
    cost_override,
    custom_expiration_date,
    custom_shelf_life_days,
    customer,
    sale_price,
    order_id,
    target_quantity,
    target_quantity_base,
    unit,
    batch_id,
):
    """
    DELEGATION LOGIC - Routes to appropriate operation module based on change type
    """
    logger.info(f"DELEGATING: {effective_change_type} -> routing to operation module")

    # Check if it's an additive operation
    for group_name, group_config in ADDITIVE_OPERATION_GROUPS.items():
        if effective_change_type in group_config["operations"]:
            logger.info(f"ROUTING: {effective_change_type} -> ADDITIVE ({group_name})")
            return _universal_additive_handler(
                item=item,
                quantity=quantity,
                quantity_base=quantity_base,
                change_type=original_change_type,  # Preserve original intent
                notes=notes,
                created_by=created_by,
                cost_override=cost_override,
                custom_expiration_date=custom_expiration_date,
                custom_shelf_life_days=custom_shelf_life_days,
                unit=unit,
                batch_id=batch_id,
            )

    # Check if it's a deductive operation
    for group_name, group_config in DEDUCTIVE_OPERATION_GROUPS.items():
        if effective_change_type in group_config["operations"]:
            logger.info(f"ROUTING: {effective_change_type} -> DEDUCTIVE ({group_name})")
            return _handle_deductive_operation(
                item=item,
                quantity=quantity,
                quantity_base=quantity_base,
                change_type=original_change_type,
                notes=notes,
                created_by=created_by,
                customer=customer,
                sale_price=sale_price,
                order_id=order_id,
                batch_id=batch_id,
            )

    # Check for special operations
    if effective_change_type == "recount":
        logger.info(f"ROUTING: {effective_change_type} -> RECOUNT (special)")
        return handle_recount(
            item=item,
            quantity=quantity,
            quantity_base=quantity_base,
            change_type=original_change_type,
            notes=notes,
            created_by=created_by,
            target_quantity=target_quantity,
            target_quantity_base=target_quantity_base,
            unit=unit,
            batch_id=batch_id,
        )
    elif effective_change_type == "cost_override":
        logger.info(f"ROUTING: {effective_change_type} -> COST_OVERRIDE (special)")
        return handle_cost_override(
            item=item,
            quantity=quantity,
            quantity_base=quantity_base,
            change_type=original_change_type,
            notes=notes,
            created_by=created_by,
            cost_override=cost_override,
            unit=unit,
            batch_id=batch_id,
        )
    elif effective_change_type == "unit_conversion":
        logger.info(f"ROUTING: {effective_change_type} -> UNIT_CONVERSION (special)")
        return handle_unit_conversion(
            item=item,
            quantity=quantity,
            quantity_base=quantity_base,
            change_type=original_change_type,
            notes=notes,
            created_by=created_by,
            unit=unit,
            batch_id=batch_id,
        )

    # Handle initial_stock as special additive case
    if effective_change_type == "initial_stock":
        logger.info(
            f"ROUTING: {effective_change_type} -> INITIAL_STOCK (additive special case)"
        )
        return _universal_additive_handler(
            item=item,
            quantity=quantity,
            quantity_base=quantity_base,
            change_type="restock",  # Treat as restock for processing
            notes=notes or "Initial stock entry",
            created_by=created_by,
            cost_override=cost_override,
            custom_expiration_date=custom_expiration_date,
            custom_shelf_life_days=custom_shelf_life_days,
            unit=unit,
            batch_id=batch_id,
        )

    # Unknown operation type
    logger.error(f"ROUTING ERROR: Unknown change type '{effective_change_type}'")
    return False, f"Unknown inventory change type: '{effective_change_type}'"
