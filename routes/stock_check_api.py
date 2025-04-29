
from flask import Blueprint, request, jsonify
from models import db, Recipe
from services.stock_check import universal_stock_check
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
        scale = float(data.get('scale', 1.0))

        if not recipe_id:
            return jsonify({'error': 'Invalid recipe ID'}), 400

        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return jsonify({'error': 'Recipe not found'}), 404

        # Only check ingredients, skip container validation
        check_results = []
        all_ok = True
        
        for ri in recipe.recipe_ingredients:
            required_amount = ri.amount * scale
            available = ri.inventory_item.quantity if ri.inventory_item else 0
            
            if available >= required_amount:
                status = "OK"
            elif available > 0:
                status = "LOW"
                all_ok = False
            else:
                status = "NEEDED"
                all_ok = False
                
            check_results.append({
                "name": ri.inventory_item.name,
                "needed": required_amount,
                "available": available,
                "unit": ri.unit,
                "status": status
            })

        return jsonify({
            'stock_check': check_results,
            'all_ok': all_ok
        })

    except Exception as e:
        logger.exception("Error in /api/check-stock")
        return jsonify({'error': str(e)}), 500
