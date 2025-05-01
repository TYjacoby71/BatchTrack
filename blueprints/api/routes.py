from flask import Blueprint, jsonify, request
from models import Recipe
from services.stock_check import universal_stock_check

api_bp = Blueprint('api', __name__)

@api_bp.route('/api/check-stock', methods=['POST'])
def check_stock():
    try:
        data = request.get_json()
        recipe_id = data.get('recipe_id')
        scale = float(data.get('scale', 1.0))
        flex_mode = data.get('flex_mode', False)

        recipe = Recipe.query.get_or_404(recipe_id)
        result = universal_stock_check(recipe, scale, flex_mode=flex_mode)
        
        # Ensure response matches expected structure
        if 'stock_check' not in result:
            result = {
                'stock_check': result.get('ingredients', []),
                'all_ok': result.get('all_ok', False)
            }
            
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
