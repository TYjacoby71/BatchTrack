
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from ...models import db, Batch, InventoryItem, ExtraBatchContainer, ExtraBatchIngredient, BatchContainer
from ...services.unit_conversion import ConversionEngine
from ...services.inventory_adjustment import process_inventory_adjustment
# Removed unnecessary service import

add_extra_bp = Blueprint('add_extra', __name__)

@add_extra_bp.route('/<int:batch_id>', methods=['POST'])
@login_required
def add_extra_to_batch(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    data = request.get_json()
    extra_ingredients = data.get("extra_ingredients", [])
    extra_containers = data.get("extra_containers", [])
    errors = []

    # Handle extra containers with reason tracking
    for container in extra_containers:
        container_item = InventoryItem.query.get(container["item_id"])
        if not container_item:
            errors.append({"item": "Unknown", "message": "Container not found"})
            continue

        needed_amount = float(container["quantity"])
        reason = container.get("reason", "batch")
        
        # Validate reason - only damaged and extra_yield allowed
        valid_reasons = ["extra_yield", "damaged"]
        if reason not in valid_reasons:
            errors.append({"item": container_item.name, "message": f"Invalid reason: {reason}. Must be 'extra_yield' or 'damaged'"})
            continue

        # Check stock availability
        if container_item.quantity < needed_amount:
            errors.append({
                "item": container_item.name,
                "message": f"Not enough in stock. Available: {container_item.quantity}, Needed: {needed_amount}",
                "needed": needed_amount,
                "available": container_item.quantity,
                "needed_unit": "units"
            })
            continue

        # Handle inventory deduction - map to inventory adjustment types
        adjustment_type = "damaged" if reason == "damaged" else "batch"
        result = process_inventory_adjustment(
            item_id=container_item.id,
            quantity=-needed_amount,
            change_type=adjustment_type,
            unit=container_item.unit,
            notes=f"Extra container for batch {batch.label_code} - {reason}",
            batch_id=batch.id,
            created_by=current_user.id
        )
        
        if not result:
            errors.append({
                "item": container_item.name,
                "message": "Failed to deduct from inventory",
                "needed": needed_amount,
                "needed_unit": "units"
            })
            continue

        # Create ExtraBatchContainer record with reason tracking
        new_extra = ExtraBatchContainer(
            batch_id=batch.id,
            container_id=container_item.id,
            container_quantity=int(needed_amount),
            quantity_used=int(needed_amount),
            cost_each=container_item.cost_per_unit,
            reason=reason,  # Save the reason for future queries
            organization_id=current_user.organization_id
        )
        db.session.add(new_extra)

    # Handle extra ingredients 
    for item in extra_ingredients:
        inventory_item = InventoryItem.query.get(item["item_id"])
        if not inventory_item:
            continue

        try:
            # Handle ingredient conversion
            conversion = ConversionEngine.convert_units(
                item["quantity"],
                item["unit"],
                inventory_item.unit,
                ingredient_id=inventory_item.id,
                density=inventory_item.density or (inventory_item.category.default_density if inventory_item.category else None)
            )
            needed_amount = conversion['converted_value']

            # Use centralized inventory adjustment
            result = process_inventory_adjustment(
                item_id=inventory_item.id,
                quantity=-needed_amount,  # Negative for deduction
                change_type='batch',
                unit=inventory_item.unit,
                notes=f"Extra ingredient for batch {batch.label_code}",
                batch_id=batch.id,
                created_by=current_user.id
            )

            if not result:
                errors.append({
                    "item": inventory_item.name,
                    "message": "Not enough in stock", 
                    "needed": needed_amount,
                    "needed_unit": inventory_item.unit
                })
            else:
                # Use current inventory cost
                new_extra = ExtraBatchIngredient(
                    batch_id=batch.id,
                    inventory_item_id=inventory_item.id,
                    quantity_used=needed_amount,
                    unit=inventory_item.unit,
                    cost_per_unit=inventory_item.cost_per_unit,
                    organization_id=current_user.organization_id
                )
                db.session.add(new_extra)

        except ValueError as e:
            errors.append({
                "item": inventory_item.name,
                "message": str(e)
            })

    if errors:
        return jsonify({"status": "error", "errors": errors}), 400

    db.session.commit()
    return jsonify({"status": "success"})
