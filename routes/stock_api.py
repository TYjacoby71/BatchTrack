
from flask import Blueprint, request, jsonify
from models import Recipe
from stock_check_utils import check_stock_for_recipe
import logging

stock_api_bp = Blueprint('stock_api', __name__)

@stock_api_bp.route('/check-stock', methods=['POST'])
def api_check_stock():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        if 'recipe_id' not in data:
            return jsonify({'error': 'Missing recipe ID'}), 400

        try:
            recipe_id = data.get('recipe_id')
            if not recipe_id:
                return jsonify({'error': 'Missing recipe ID'}), 400

            try:
                recipe_id = int(recipe_id)
            except (TypeError, ValueError):
                return jsonify({'error': 'Invalid recipe ID format'}), 400

            recipe = Recipe.query.get(recipe_id)
            if not recipe:
                return jsonify({'error': 'Recipe not found'}), 404

            try:
                scale = float(data.get('scale', 1.0))
            except (TypeError, ValueError):
                return jsonify({'error': 'Invalid scale value'}), 400

            if scale <= 0:
                return jsonify({'error': 'Scale must be greater than 0'}), 400

            stock_results, all_ok, conversion_warning = check_stock_for_recipe(recipe, scale)
            
            return jsonify({
                'all_ok': all_ok,
                'stock_check': stock_results,
                'conversion_warning': conversion_warning,
                'recipe_name': recipe.name,
                'status': 'success' if all_ok else 'warning'
            })

        except ValueError:
            return jsonify({'error': 'Invalid recipe ID format'}), 400

    except Exception as e:
        logging.exception("Stock check API failed")
        return jsonify({'error': 'Stock check failed'}), 500

