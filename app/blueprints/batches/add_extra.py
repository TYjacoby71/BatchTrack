from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import db, Batch, InventoryItem, ExtraBatchContainer, ExtraBatchIngredient
from app.services.unit_conversion import ConversionEngine
from services.inventory_adjustment import process_inventory_adjustment

add_extra_bp = Blueprint('add_extra', __name__)

@add_extra_bp.route('/<int:batch_id>', methods=['POST'])
@login_required
def add_extra_to_batch(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    data = request.get_json()
    extra_ingredients = data.get("extra_ingredients", [])
    extra_containers = data.get("extra_containers", [])
    errors = []

    # Handle extra containers
    for container in extra_containers:
        container_item = InventoryItem.query.get(container["item_id"])
        if not container_item:
            continue

        needed_amount = float(container["quantity"])
        result = process_inventory_adjustment(
                item_id=container_item.id,
                quantity=-needed_amount,  # Negative for deduction
                change_type='batch',
                unit=container_item.unit,
                notes=f"Extra container for batch {batch.label_code}",
                batch_id=batch.id,
                created_by=current_user.id
            )

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
                quantity_used=needed_amount,
                cost_each=container_item.cost_per_unit
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
                    quantity=needed_amount,
                    unit=inventory_item.unit,
                    cost_per_unit=inventory_item.cost_per_unit
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