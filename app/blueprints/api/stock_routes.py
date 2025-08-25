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

@stock_api_bp.route('/stock-check', methods=['POST'])
@login_required
@permission_required('batch_production.create')
def check_stock():
    """Check stock availability for items"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        items = data.get('items', [])
        organization_id = current_user.organization_id if current_user.is_authenticated else None

        # Use the Universal Stock Check Service
        uscs = UniversalStockCheckService(organization_id=organization_id)
        result = uscs.check_multiple_items(items)

        if not isinstance(result, dict):
            result = {'stock_check': [], 'status': 'error', 'message': 'Invalid result format'}

        # Always return 200 OK for successful stock checks, even if ingredients are insufficient
        # The frontend will handle displaying the results appropriately
        return jsonify(result), 200

    except Exception as e:
        current_app.logger.error(f"Stock check error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@stock_api_bp.route('/stock-check/recipe/<int:recipe_id>', methods=['POST'])
@login_required
@permission_required('batch_production.create')
def check_recipe_ingredients(recipe_id):
    """Check stock availability for all ingredients in a recipe using USCS ingredient handler"""
    try:
        data = request.get_json() or {}
        scale = data.get('scale', 1.0)

        # Load recipe
        from ...models import Recipe
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return jsonify({'success': False, 'error': 'Recipe not found'}), 404

        # Check organization access
        if recipe.organization_id != current_user.organization_id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        # Use USCS ingredient handler directly
        from ...services.stock_check.handlers.ingredient_handler import IngredientHandler

        organization_id = current_user.organization_id if current_user.is_authenticated else None
        ingredient_handler = IngredientHandler(organization_id=organization_id)

        # Get ingredient stock check results
        stock_results = ingredient_handler.check_recipe_ingredients(recipe, scale)

        # Convert to the format expected by frontend
        stock_check = []
        for result in stock_results:
            stock_check.append({
                'item_id': result['inventory_item_id'],
                'item_name': result['item_name'],
                'needed_quantity': result['needed_quantity'],
                'needed_unit': result['needed_unit'],
                'available_quantity': result['available_quantity'],
                'available_unit': result['available_unit'],
                'status': result['status'],
                'formatted_needed': result['formatted_needed'],
                'formatted_available': result['formatted_available']
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