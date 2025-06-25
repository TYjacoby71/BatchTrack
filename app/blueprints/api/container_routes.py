from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ...models import Recipe, InventoryItem
from app.services.unit_conversion import ConversionEngine

container_api_bp = Blueprint('container_api', __name__, url_prefix='/api')

@container_api_bp.route('/available-containers/<int:recipe_id>')
@login_required
def available_containers(recipe_id):
    try:
        scale = float(request.args.get('scale', 1.0))
        recipe = Recipe.query.filter_by(
            id=recipe_id, 
            organization_id=current_user.organization_id
        ).first()
        if not recipe:
            return jsonify({"error": "Recipe not found"}), 404

        allowed_containers = recipe.allowed_containers or []
        in_stock = []

        # Scope containers by organization
        containers_query = InventoryItem.query.filter_by(
            type='container',
            organization_id=current_user.organization_id
        )

        for container in containers_query.all():
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