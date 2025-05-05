
from flask import Blueprint, jsonify
from models import IngredientCategory, InventoryItem

ingredient_api_bp = Blueprint('ingredient_api', __name__)

@ingredient_api_bp.route('/api/categories', methods=['GET'])
def get_categories():
    categories = IngredientCategory.query.all()
    return jsonify([{
        'id': cat.id,
        'name': cat.name,
        'default_density': cat.default_density
    } for cat in categories])

@ingredient_api_bp.route('/api/ingredient/<int:id>/density', methods=['GET'])
def get_ingredient_density(id):
    ingredient = InventoryItem.query.get_or_404(id)
    if ingredient.density:
        return jsonify({'density': ingredient.density})
    elif ingredient.category:
        return jsonify({'density': ingredient.category.default_density})
    return jsonify({'density': 1.0})
