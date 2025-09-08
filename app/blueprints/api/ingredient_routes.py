
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from ...models import IngredientCategory, InventoryItem, GlobalItem, db
from ...services.statistics.global_item_stats import GlobalItemStatsService

ingredient_api_bp = Blueprint('ingredient_api', __name__)

@ingredient_api_bp.route('/categories', methods=['GET'])
def get_categories():
    """Return base ingredient categories with their default densities."""
    # Categories are org-scoped; expose current org's categories sorted by name
    categories = IngredientCategory.query.order_by(IngredientCategory.name.asc()).all()
    return jsonify([
        {
            'id': cat.id,
            'name': cat.name,
            'default_density': cat.default_density
        }
        for cat in categories
    ])

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
            'id': item.id,
            'text': item.name,
            'category': item.category.name if item.category else None,
            'unit': item.unit,
            'density': item.density,
            'type': item.type,
            'global_item_id': item.global_item_id
        })

    return jsonify({'results': payload})

@ingredient_api_bp.route('/global-items/search', methods=['GET'])
@login_required
def search_global_items():
    q = (request.args.get('q') or '').strip()
    item_type = (request.args.get('type') or '').strip()  # optional: ingredient, container, packaging, consumable
    if not q:
        return jsonify({'results': []})

    query = GlobalItem.query.filter(GlobalItem.is_archived != True)
    if item_type:
        query = query.filter(GlobalItem.item_type == item_type)

    ilike_term = f"%{q}%"
    # Match by name or any synonym in aka_names (JSON)
    name_match = GlobalItem.name.ilike(ilike_term)
    try:
        from sqlalchemy import or_
        aka_match = GlobalItem.aka_names.cast(db.String).ilike(ilike_term)
        items = query.filter(or_(name_match, aka_match)).order_by(func.length(GlobalItem.name).asc()).limit(20).all()
    except Exception:
        items = query.filter(name_match).order_by(func.length(GlobalItem.name).asc()).limit(20).all()

    results = []
    for gi in items:
        results.append({
            'id': gi.id,
            'text': gi.name,
            'item_type': gi.item_type,
            'default_unit': gi.default_unit,
            'density': gi.density,
            'capacity': gi.capacity,
            'capacity_unit': gi.capacity_unit,
            'aka_names': gi.aka_names,
            'default_is_perishable': gi.default_is_perishable,
            'recommended_shelf_life_days': gi.recommended_shelf_life_days,
        })

    return jsonify({'results': results})

@ingredient_api_bp.route('/global-items/<int:global_item_id>/stats', methods=['GET'])
@login_required
def get_global_item_stats(global_item_id):
    try:
        rollup = GlobalItemStatsService.get_rollup(global_item_id)
        return jsonify({'success': True, 'stats': rollup})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
