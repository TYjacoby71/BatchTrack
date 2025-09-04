
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from ...models import IngredientCategory, InventoryItem, db

ingredient_api_bp = Blueprint('ingredient_api', __name__)

@ingredient_api_bp.route('/categories', methods=['GET'])
def get_categories():
    categories = IngredientCategory.query.all()
    return jsonify([{
        'id': cat.id,
        'name': cat.name,
        'default_density': cat.default_density
    } for cat in categories])

@ingredient_api_bp.route('/ingredient/<int:id>/density', methods=['GET'])
def get_ingredient_density(id):
    ingredient = InventoryItem.query.get_or_404(id)
    if ingredient.density:
        return jsonify({'density': ingredient.density})
    elif ingredient.category:
        return jsonify({'density': ingredient.category.default_density})
    return jsonify({'density': 1.0})

@ingredient_api_bp.route('/ingredients/search', methods=['GET'])
@login_required
def search_ingredients():
    """Search existing inventory items and return top matches for name field autocomplete.
    This preserves current add flow while enabling typeahead suggestions.
    """
    q = (request.args.get('q') or '').strip()
    if not q:
        return jsonify({
            'results': []
        })

    query = InventoryItem.query
    # Scope to the user's organization for privacy
    if current_user.organization_id:
        query = query.filter(InventoryItem.organization_id == current_user.organization_id)

    # Only show inventory-manageable types (exclude products)
    query = query.filter(~InventoryItem.type.in_(['product', 'product-reserved']))

    ilike_term = f"%{q}%"
    results = query.filter(
        InventoryItem.name.ilike(ilike_term)
    ).order_by(func.length(InventoryItem.name).asc()).limit(20).all()

    payload = []
    for item in results:
        payload.append({
            'id': item.name,  # select2 will write name directly; not selecting by id here
            'text': item.name,
            'category': item.category.name if item.category else None,
            'unit': item.unit,
            'density': item.density,
            'type': item.type
        })

    return jsonify({'results': payload})
