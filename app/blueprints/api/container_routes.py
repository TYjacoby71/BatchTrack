
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

        allowed_containers = recipe.allowed_containers or []
        in_stock = []

        for container in InventoryItem.query.filter_by(type='container').all():
            if allowed_containers and container.id not in allowed_containers:
                continue

            try:
                conversion_result = ConversionEngine.convert_units(
                    container.storage_amount,
                    container.storage_unit,
                    recipe.predicted_yield_unit
                )
                if conversion_result and 'converted_value' in conversion_result:
                    in_stock.append({
                        "id": container.id,
                        "name": container.name,
                        "storage_amount": conversion_result['converted_value'],
                        "storage_unit": recipe.predicted_yield_unit,
                        "stock_qty": container.quantity
                    })
            except Exception:
                continue

        sorted_containers = sorted(in_stock, key=lambda c: c['storage_amount'], reverse=True)
        return jsonify({
            "available": sorted_containers,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
