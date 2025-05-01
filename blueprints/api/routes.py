from flask import Blueprint, jsonify, request
from models import Recipe, InventoryItem
from services.unit_conversion import ConversionEngine

container_api_bp = Blueprint('container_api', __name__)

@container_api_bp.route('/api/available-containers/<int:recipe_id>')
def available_containers(recipe_id):
    try:
        scale = float(request.args.get('scale', 1.0))
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return jsonify({"error": "Recipe not found"}), 404

        # Handle allowed containers
        allowed_containers = recipe.allowed_containers or []

        # Get available containers and convert units 
        in_stock = []
        for container in InventoryItem.query.filter_by(type='container').all():
            # Skip if container not allowed for recipe
            if allowed_containers and container.id not in allowed_containers:
                continue

            try:
                converted_capacity = ConversionEngine.convert_units(
                    container.storage_amount,
                    container.storage_unit,
                    recipe.predicted_yield_unit
                )
                if converted_capacity:
                    in_stock.append({
                        "id": container.id,
                        "name": container.name,
                        "storage_amount": converted_capacity,
                        "storage_unit": recipe.predicted_yield_unit,
                        "stock_qty": container.quantity
                    })
            except Exception:
                continue

        # Sort largest to smallest for greedy fill
        sorted_containers = sorted(in_stock, key=lambda c: c['storage_amount'], reverse=True)

        # Calculate optimal container plan
        plan = []
        required_volume = recipe.predicted_yield * scale # Assuming predicted_yield and required_unit are defined elsewhere
        required_unit = recipe.predicted_yield_unit # Assuming this is defined elsewhere

        remaining = required_volume

        for container in sorted_containers:
            if remaining <= 0:
                break

            per_unit = container['storage_amount']
            max_needed = int(remaining // per_unit)
            if max_needed <= 0:
                continue

            use_qty = min(max_needed, container['stock_qty'])
            if use_qty > 0:
                plan.append({
                    "id": container['id'],
                    "name": container['name'],
                    "capacity": per_unit,
                    "unit": required_unit,
                    "quantity": use_qty
                })
                remaining -= use_qty * per_unit

        return jsonify({
            "available": sorted_containers,
            "plan": plan
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500