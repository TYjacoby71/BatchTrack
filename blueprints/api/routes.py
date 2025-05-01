
from flask import Blueprint, jsonify, request, current_app
import json
import os
from models import Recipe, IngredientCategory, InventoryItem
from services.stock_check import universal_stock_check

api_bp = Blueprint('api', __name__)

@api_bp.route('/api/check-stock', methods=['POST'])
def check_stock():
    try:
        data = request.get_json()
        recipe_id = data.get('recipe_id')
        scale = float(data.get('scale', 1.0))
        flex_mode = data.get('flex_mode', False)

        recipe = Recipe.query.get_or_404(recipe_id)
        result = universal_stock_check(recipe, scale, flex_mode=flex_mode)
        
        # Ensure response matches expected structure
        if 'stock_check' not in result:
            result = {
                'stock_check': result.get('ingredients', []),
                'all_ok': result.get('all_ok', False)
            }
            
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400



@api_bp.route('/categories', methods=['GET'])
def get_categories():
    categories = IngredientCategory.query.all()
    return jsonify([{
        'id': cat.id,
        'name': cat.name,
        'default_density': cat.default_density
    } for cat in categories])

@api_bp.route('/ingredient/<int:id>/density', methods=['GET'])
def get_ingredient_density(id):
    ingredient = InventoryItem.query.get_or_404(id)
    if ingredient.density:
        return jsonify({'density': ingredient.density})
    elif ingredient.category:
        return jsonify({'density': ingredient.category.default_density})
    return jsonify({'density': 1.0})  # Default fallback


