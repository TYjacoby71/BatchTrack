from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.services.stock_check import UniversalStockCheckService
from app.models import Recipe
from app.utils.permissions import permission_required
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ...extensions import db
from ...models import InventoryItem, UnifiedInventoryHistory
from ...utils.permissions import require_permission
from ...services.stock_check.core import StockCheckService
import logging

logger = logging.getLogger(__name__)

# Create the blueprint
stock_bp = Blueprint('stock_api', __name__)

@stock_bp.route('/check-stock', methods=['POST'])
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

        # Use the Universal Stock Check Service
        from app.services.stock_check import UniversalStockCheckService

        uscs = UniversalStockCheckService()
        result = uscs.check_recipe_stock(recipe_id, scale)

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Stock check error: {e}")
        return jsonify({'error': 'Failed to check stock'}), 500


@stock_bp.route('/check-containers', methods=['POST'])
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

        # Use the Universal Stock Check Service for containers
        from app.services.stock_check import UniversalStockCheckService

        uscs = UniversalStockCheckService()
        result = uscs.check_container_availability(recipe_id, scale)

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Container stock check error: {e}")
        return jsonify({'error': 'Failed to check container availability'}), 500