
from flask import Blueprint, request, jsonify
from services.stock_check_service import check_stock

stock_check_api_bp = Blueprint('stock_check_api', __name__)

@stock_check_api_bp.route('/api/check-stock', methods=['POST'])
def api_check_stock():
    data = request.get_json()
    
    recipe_id = data.get('recipe_id')
    scale = float(data.get('scale', 1.0))
    container_plan = data.get('containers', [])
    flex_mode = data.get('flex_mode', False)

    if not recipe_id:
        return jsonify({'error': 'Missing recipe_id'}), 400

    try:
        result = check_stock(recipe_id, scale, container_plan, flex_mode)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400
from flask import Blueprint, request, jsonify
from models import db, Recipe
from services.stock_check import check_ingredient_stock, check_container_stock
import logging

logger = logging.getLogger(__name__)
stock_api_bp = Blueprint('stock_api', __name__)

@stock_api_bp.route('/api/check-stock', methods=['POST'])
def api_check_stock():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        recipe_id = data.get('recipe_id')
        if not recipe_id:
            return jsonify({'error': 'Invalid or missing recipe ID'}), 400

        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return jsonify({'error': 'Recipe not found'}), 404

        scale = float(data.get('scale', 1.0))
        if scale <= 0:
            return jsonify({'error': 'Invalid scale value'}), 400

        # Perform Stock Check Logic
        ingredient_results = check_ingredient_stock(recipe, scale)
        container_results = check_container_stock(recipe, scale)

        full_check = ingredient_results + container_results

        return jsonify({
            'stock_check': full_check,
            'all_ok': all(item['status'] == 'OK' for item in full_check)
        })

    except Exception as e:
        logger.exception("Error in /api/check-stock")
        return jsonify({'error': str(e)}), 500
