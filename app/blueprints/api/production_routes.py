
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ...utils.permissions import permission_required
from ...models import Recipe
import logging

logger = logging.getLogger(__name__)

production_api_bp = Blueprint('production_api', __name__)

@production_api_bp.route('/production/validate-stock', methods=['POST'])
@login_required
@permission_required('batch_production.create')
def validate_stock_for_production():
    """Internal stock validation for production planning"""
    try:
        data = request.get_json() or {}
        recipe_id = data.get('recipe_id')
        scale = float(data.get('scale', 1.0))

        if not recipe_id:
            return jsonify({'success': False, 'error': 'recipe_id is required'}), 400

        # Get the recipe
        recipe = Recipe.query.get_or_404(recipe_id)

        # Use production planning service for stock validation
        from app.services.production_planning import ProductionPlanningService
        planning_service = ProductionPlanningService()
        
        # Get stock validation results
        validation_result = planning_service.validate_recipe_stock(recipe, scale)

        if not validation_result['can_produce']:
            return jsonify({
                'success': True,
                'stock_check': validation_result['ingredient_issues'],
                'can_produce': False,
                'message': 'Insufficient stock for production'
            })

        return jsonify({
            'success': True,
            'stock_check': validation_result['ingredient_status'],
            'can_produce': True,
            'message': 'All ingredients available'
        })

    except Exception as e:
        logger.error(f"Production stock validation error: {e}")
        return jsonify({
            'success': False,
            'error': f'Stock validation failed: {str(e)}'
        }), 500
