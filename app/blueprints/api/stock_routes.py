from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ...extensions import db
from ...models import InventoryItem, UnifiedInventoryHistory
from ...utils.permissions import permission_required
from ...services.stock_check.core import UniversalStockCheckService
import logging
from flask import current_app

logger = logging.getLogger(__name__)

# Create the blueprint
stock_api_bp = Blueprint('stock_api', __name__)

# Stock check functionality is now internal only
# Recipe stock checking is handled through the production planning service


@stock_api_bp.route('/stock-check/recipe/<int:recipe_id>', methods=['POST'])
@login_required
@permission_required('recipes.view')
def check_recipe_ingredients(recipe_id):
    """Check stock availability for all ingredients in a recipe using USCS ingredient handler"""
    try:
        data = request.get_json() or {}
        scale = float(data.get('scale', 1.0))

        # Get the recipe
        from app.models.recipe import Recipe
        recipe = Recipe.query.get_or_404(recipe_id)

        # Use the Universal Stock Check Service to check recipe ingredients
        from app.services.stock_check.core import UniversalStockCheckService
        uscs = UniversalStockCheckService()

        # Use the USCS check_recipe_stock method
        result = uscs.check_recipe_stock(recipe, scale)

        if not result['success']:
            return jsonify(result), 500

        stock_results = result['stock_check']

        # Convert to the format expected by frontend
        stock_check = []
        for result_item in stock_results:
            stock_check.append({
                'item_id': result_item['item_id'],
                'item_name': result_item['item_name'],
                'needed_quantity': result_item['needed_quantity'],
                'needed_unit': result_item['needed_unit'],
                'available_quantity': result_item['available_quantity'],
                'available_unit': result_item['available_unit'],
                'status': result_item['status'],
                'formatted_needed': result_item['formatted_needed'],
                'formatted_available': result_item['formatted_available']
            })

        return jsonify({
            'success': True,
            'stock_check': stock_check,
            'recipe_id': recipe_id,
            'scale': scale
        })

    except Exception as e:
        current_app.logger.error(f"Recipe ingredient stock check error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500