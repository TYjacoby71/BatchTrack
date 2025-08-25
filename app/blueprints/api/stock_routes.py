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

@stock_api_bp.route('/check-stock', methods=['POST'])
@login_required
@permission_required('batch_production.create')
def check_stock():
    """Check ingredient stock availability for a recipe at given scale."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        recipe_id = data.get('recipe_id')
        scale = data.get('scale', 1.0)

        if not recipe_id:
            return jsonify({'error': 'Recipe ID is required'}), 400

        # Get the recipe object
        from app.models import Recipe
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return jsonify({'error': 'Recipe not found'}), 404

        # Use recipe service for stock checking
        from app.services.recipe_service import check_recipe_stock
        result = check_recipe_stock(recipe, scale)

        # Ensure we always return a valid response structure
        if not isinstance(result, dict):
            result = {'stock_check': [], 'status': 'error', 'message': 'Invalid result format'}

        # Always return 200 OK for successful stock checks, even if ingredients are insufficient
        # The frontend will handle displaying the results appropriately
        return jsonify(result), 200

    except Exception as e:
        current_app.logger.error(f"Stock check error: {e}")
        return jsonify({'error': 'Failed to check stock'}), 500


@stock_api_bp.route('/check-containers', methods=['POST'])
@login_required
@permission_required('batch_production.create')
def check_containers():
    """Check container availability for a recipe at given scale."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        recipe_id = data.get('recipe_id')
        scale = data.get('scale', 1.0)

        if not recipe_id:
            return jsonify({'error': 'Recipe ID is required'}), 400

        # Get the recipe object
        from app.models import Recipe
        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return jsonify({'error': 'Recipe not found'}), 404

        # Use the Universal Stock Check Service for containers
        uscs = UniversalStockCheckService()
        # For now, just return the regular stock check - container checking is part of it
        result = uscs.check_recipe_stock(recipe, scale)

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Container stock check error: {e}")
        return jsonify({'error': 'Failed to check container availability'}), 500