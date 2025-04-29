
from flask import Blueprint, request, jsonify
from models import db, Recipe
from services.stock_check import universal_stock_check
from stock_check_utils import check_stock_for_recipe
import logging

logger = logging.getLogger(__name__)
stock_api_bp = Blueprint('stock_api', __name__)

@stock_api_bp.route('/api/check-stock', methods=['POST'])
def api_check_stock():
    try:
        data = request.get_json()
        recipe_id = data.get('recipe_id')
        scale = float(data.get('scale', 1))
        flex_mode = data.get('flex_mode', False)

        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return jsonify({'error': 'Recipe not found'}), 404

        # Use the proper stock check function that handles unit conversion
        report, all_ok = check_stock_for_recipe(recipe, scale)

        return jsonify({
            "all_ok": all_ok,
            "ingredients": report
        })
    except Exception as e:
        logger.error(f"Stock check failed: {str(e)}")
        return jsonify({'error': str(e)}), 400
