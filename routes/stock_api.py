from flask import Blueprint, request, jsonify
from models import Recipe
from stock_check_utils import check_recipe_stock, check_containers
import logging

logger = logging.getLogger(__name__)
stock_api_bp = Blueprint('stock_api', __name__)

@stock_api_bp.route('/check-stock', methods=['POST'])
def api_check_stock():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        recipe_id = data.get('recipe_id')
        if not recipe_id or not isinstance(recipe_id, int):
            return jsonify({'error': 'Invalid or missing recipe ID'}), 400

        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return jsonify({'error': 'Recipe not found'}), 404

        try:
            scale = float(data.get('scale', 1.0))
            if scale <= 0:
                raise ValueError()
            logger.info(f"[StockCheck] Recipe ID: {recipe_id}, Scale: {scale}, Container IDs: {data.get('container_ids', [])}")
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid or missing scale'}), 400

        # Check recipe ingredients
        ingredient_results, conversion_warning = check_recipe_stock(recipe, scale)

        # Check containers if provided
        container_ids = data.get('container_ids', [])
        if container_ids:
            container_results, containers_ok = check_containers(container_ids, scale)
            all_ok = all(r['status'] == 'OK' for r in ingredient_results + container_results)
            stock_results = ingredient_results + container_results
        else:
            all_ok = all(r['status'] == 'OK' for r in ingredient_results)
            stock_results = ingredient_results

        return jsonify({
            'all_ok': all_ok,
            'stock_check': stock_results,
            'conversion_warning': conversion_warning,
            'recipe_name': recipe.name
        })

    except Exception as e:
        logger.exception("Stock check failed")
        return jsonify({'error': str(e)}), 500