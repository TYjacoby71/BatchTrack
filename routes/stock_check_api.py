
from flask import Blueprint, request, jsonify
from models import db, Recipe
from services.stock_check import universal_stock_check
import logging

logger = logging.getLogger(__name__)
stock_api_bp = Blueprint('stock_api', __name__)

@stock_api_bp.route('/api/check-stock', methods=['POST'])
def api_check_stock():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        recipe_id = data.get('recipe_id')
        scale = float(data.get('scale', 1.0))
        flex_mode = data.get('flex_mode', False)

        if not recipe_id:
            return jsonify({'error': 'Recipe ID required'}), 400

        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return jsonify({'error': 'Recipe not found'}), 404

        from services.stock_check_utils import check_stock
        results = check_stock(recipe_id, scale, [])
        
        if not isinstance(results, dict):
            logger.error(f"Invalid stock check results format: {results}")
            return jsonify({'error': 'Invalid stock check results'}), 500

        return jsonify({
            'stock_check': results['stock_check'],
            'all_ok': results['all_ok']
        })

    except Exception as e:
        logger.exception("Error in /api/check-stock")
        return jsonify({'error': str(e)}), 500
