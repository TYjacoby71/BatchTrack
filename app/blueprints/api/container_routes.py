
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ...models import Recipe, InventoryItem
from app.services.unit_conversion import ConversionEngine

container_api_bp = Blueprint('container_api', __name__, url_prefix='/api')

@container_api_bp.route('/debug-containers')
@login_required
def debug_containers():
    try:
        all_containers = InventoryItem.query.filter_by(
            organization_id=current_user.organization_id
        ).all()
        
        container_debug = []
        for item in all_containers:
            container_debug.append({
                "id": item.id,
                "name": item.name,
                "type": item.type,
                "storage_amount": item.storage_amount,
                "storage_unit": item.storage_unit,
                "quantity": item.quantity
            })
            
        return jsonify({
            "total_items": len(all_containers),
            "container_items": [c for c in container_debug if c["type"] == "container"],
            "all_items": container_debug
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@container_api_bp.route('/available-containers/<int:recipe_id>')
@login_required
def available_containers(recipe_id):
    try:
        scale = float(request.args.get('scale', '1.0'))

        # Scoped query to current user's organization
        recipe = Recipe.scoped().filter_by(id=recipe_id).first()
        if not recipe:
            return jsonify({"error": "Recipe not found"}), 404

        allowed_container_ids = recipe.allowed_containers or []
        predicted_unit = recipe.predicted_yield_unit
        if not predicted_unit:
            return jsonify({"error": "Recipe missing predicted yield unit"}), 400

        in_stock = []

        # Filter containers for this organization only
        containers_query = InventoryItem.query.filter_by(
            type='container',
            organization_id=current_user.organization_id
        )

        print(f"Found {containers_query.count()} containers for organization {current_user.organization_id}")
        
        for container in containers_query:
            print(f"Processing container: {container.name}, storage_amount: {container.storage_amount}, storage_unit: {container.storage_unit}")
            
            if allowed_container_ids and container.id not in allowed_container_ids:
                print(f"Container {container.name} not in allowed list: {allowed_container_ids}")
                continue

            try:
                conversion = ConversionEngine.convert_units(
                    container.storage_amount,
                    container.storage_unit,
                    predicted_unit,
                    conversion_type='container_sizing'
                )
                print(f"Conversion result for {container.name}: {conversion}")
                
                if conversion and 'converted_value' in conversion:
                    in_stock.append({
                        "id": container.id,
                        "name": container.name,
                        "storage_amount": conversion['converted_value'],
                        "storage_unit": predicted_unit,
                        "stock_qty": container.quantity
                    })
            except Exception as e:
                print(f"Conversion failed for {container.name}: {e}")
                # Rollback any failed database operations
                from ...extensions import db
                try:
                    db.session.rollback()
                except:
                    pass
                continue  # silently skip conversion failures

        sorted_containers = sorted(in_stock, key=lambda c: c['storage_amount'], reverse=True)

        return jsonify({"available": sorted_containers})

    except Exception as e:
        return jsonify({"error": f"Container API failed: {str(e)}"}), 500
