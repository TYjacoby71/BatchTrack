from flask import Blueprint, jsonify, request
from flask_login import current_user
from ...models import Recipe, InventoryItem
from app.services.unit_conversion import ConversionEngine

container_api_bp = Blueprint('container_api', __name__)

@container_api_bp.route('/api/available-containers/<int:recipe_id>')
def available_containers(recipe_id):
    try:
        # Get recipe with organization scoping
        if current_user.role == 'developer':
            recipe = Recipe.query.get_or_404(recipe_id)
        else:
            recipe = Recipe.query.filter_by(
                id=recipe_id, 
                organization_id=current_user.organization_id
            ).first_or_404()

        scale = float(request.args.get('scale', 1.0))

        # Get containers based on recipe requirements with organization scoping
        base_query = InventoryItem.query.filter_by(type='container')

        # Apply organization scoping
        if current_user.role != 'developer':
            base_query = base_query.filter_by(organization_id=current_user.organization_id)

        if recipe.requires_containers and recipe.allowed_containers:
            container_ids = recipe.allowed_containers
            containers = base_query.filter(InventoryItem.id.in_(container_ids)).all()
        else:
            # If no specific requirements, get all containers
            containers = base_query.all()

        in_stock = []

        for container in containers:
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