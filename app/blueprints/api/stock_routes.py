
from flask import Blueprint, jsonify, request
from flask_login import current_user
from ...models import Recipe
from ...services.stock_check import universal_stock_check

stock_api_bp = Blueprint('stock_api', __name__)

@stock_api_bp.route('/api/check-stock', methods=['POST'])
def check_stock():
    try:
        data = request.get_json()
        recipe_id = data.get('recipe_id')
        scale = float(data.get('scale', 1.0))
        flex_mode = data.get('flex_mode', False)

        # Get recipe with organization scoping
        if current_user.role == 'developer':
            recipe = Recipe.query.get_or_404(recipe_id)
        else:
            recipe = Recipe.query.filter_by(
                id=recipe_id, 
                organization_id=current_user.organization_id
            ).first_or_404()
        
        result = universal_stock_check(recipe, scale, flex_mode=flex_mode)
        
        # Ensure consistent response format
        return jsonify({
            'stock_check': result.get('stock_check', []),
            'all_ok': result.get('all_ok', False),
            'recipe_name': recipe.name
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400
