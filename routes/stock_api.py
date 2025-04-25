
from flask import Blueprint, request, jsonify
from models import Recipe
from stock_check_utils import check_stock_for_recipe
import logging

stock_api_bp = Blueprint('stock_api', __name__)

@stock_api_bp.route('/check-stock', methods=['POST'])
def api_check_stock():
    try:
        data = request.get_json()
        if not data or 'recipe_id' not in data:
            return jsonify({'error': 'Missing recipe ID'}), 400

        recipe = Recipe.query.get(data['recipe_id'])
        if not recipe:
            return jsonify({'error': 'Recipe not found'}), 404

        scale = float(data.get('scale', 1.0))
        if scale <= 0:
            return jsonify({'error': 'Scale must be greater than 0'}), 400

        stock_results, all_ok = check_stock_for_recipe(recipe, scale)
        
        return jsonify({
            'ok': all_ok,
            'details': stock_results,
            'recipe_name': recipe.name,
            'missing': [r['name'] for r in stock_results if r['status'] != 'OK']
        })

    except ValueError as e:
        logging.error(f"Stock check validation error: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logging.exception("Stock check API failed")
        return jsonify({'error': 'Stock check failed'}), 500
