from flask import Blueprint, jsonify, request
from models import Recipe, InventoryItem
from services.unit_conversion import ConversionEngine
from services.stock_check import universal_stock_check

api_bp = Blueprint('api', __name__)
container_api_bp = Blueprint('container_api', __name__)

@api_bp.route('/api/check-stock', methods=['POST'])
def check_stock():
    try:
        data = request.get_json()
        recipe_id = data.get('recipe_id')
        scale = float(data.get('scale', 1.0))
        
        recipe = Recipe.query.get_or_404(recipe_id)
        result = universal_stock_check(recipe, scale)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

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

        sorted_containers = sorted(in_stock, key=lambda c: c['storage_amount'], reverse=True)
        return jsonify({
            "available": sorted_containers,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500