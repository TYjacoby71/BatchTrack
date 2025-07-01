
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from ...models import db, Batch, InventoryItem, ExtraBatchContainer, ExtraBatchIngredient
from ...services.unit_conversion import ConversionEngine
from ...services.inventory_adjustment import process_inventory_adjustment

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
            continue

        needed_amount = float(container["quantity"])
        reason = container.get("reason", "extra_needed")  # primary_packaging, overflow, broke_container, test_sample, other
        one_time = container.get("one_time", False)  # For broken containers when inventory is zero
        
        # Validate reason
        valid_reasons = ["primary_packaging", "overflow", "broke_container", "test_sample", "other"]
        if reason not in valid_reasons:
            errors.append(f"Invalid reason for container {container_item.name}")
            continue

        # Handle one-time containers (don't deduct from inventory)
        if one_time:
            # Log the container usage without inventory deduction
            from app.models import BatchContainer
            batch_container = BatchContainer(
                batch_id=batch.id,
                container_name=container_item.name,
                container_size=container_item.size or 0,
                quantity_used=needed_amount,
                reason=reason,
                one_time_use=True,
                exclude_from_product=(reason == "broke_container"),
                created_by=current_user.id
            )
            db.session.add(batch_container)
        else:
            # Normal inventory deduction
            result = process_inventory_adjustment(
                item_id=container_item.id,
                quantity=-needed_amount,  # Negative for deduction
                change_type='batch',
                unit=container_item.unit,
                notes=f"Extra container for batch {batch.label_code} - Reason: {reason}",
                batch_id=batch.id,
                created_by=current_user.id
            )
            
            # Track container usage with reason
            from app.models import BatchContainer
            batch_container = BatchContainer(
                batch_id=batch.id,
                container_item_id=container_item.id,
                container_name=container_item.name,
                container_size=container_item.size or 0,
                quantity_used=needed_amount,
                reason=reason,
                one_time_use=False,
                exclude_from_product=(reason == "broke_container"),
                created_by=current_user.id
            )
            db.session.add(batch_container)

        if not result:
            errors.append({
                "item": container_item.name,
                "message": "Not enough in stock",
                "needed": needed_amount,
                "needed_unit": "units"
            })
        else:
            # Use container's current cost
            new_extra = ExtraBatchContainer(
                batch_id=batch.id,
                container_id=container_item.id,
                container_quantity=int(needed_amount),  # Number of containers used
                quantity_used=int(needed_amount),  # Same as container_quantity for backwards compatibility
                cost_each=container_item.cost_per_unit,
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
