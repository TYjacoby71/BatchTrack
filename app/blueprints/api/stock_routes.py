from flask import Blueprint, jsonify, request
from flask_login import login_required
from ...services.stock_check import universal_stock_check
from ...models import Recipe

stock_api_bp = Blueprint('stock_api', __name__, url_prefix='/api')

@stock_api_bp.route('/check-stock', methods=['POST'])
@login_required
def check_stock():
    try:
        data = request.get_json()
        recipe_id = data.get('recipe_id')
        scale = float(data.get('scale', 1.0))
        flex_mode = data.get('flex_mode', False)

        # Use scoped query to ensure recipe belongs to current user's organization
        recipe = Recipe.scoped().filter_by(id=recipe_id).first()
        if not recipe:
            return jsonify({"error": "Recipe not found"}), 404
        result = universal_stock_check(recipe, scale, flex_mode=flex_mode)

        if 'stock_check' not in result:
            result = {
                'stock_check': result.get('ingredients', []),
                'all_ok': result.get('all_ok', False)
            }

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400