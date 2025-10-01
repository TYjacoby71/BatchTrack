from flask import Blueprint, render_template, request
from app.models import db, GlobalItem
from app.services.statistics.global_item_stats import GlobalItemStatsService
from app.models.category import IngredientCategory

global_library_bp = Blueprint('global_library_bp', __name__)


@global_library_bp.route('/global-items')
def global_library():
    """Public, read-only view of the Global Inventory Library.
    Supports filtering by item type and ingredient category, plus text search.
    Query params:
      - type: ingredient|container|packaging|consumable (optional)
      - category: ingredient category name (only when type=ingredient)
      - search: free text search across name and aka names
    """
    item_type = request.args.get('type', '').strip()
    category_filter = request.args.get('category', '').strip()
    search_query = request.args.get('search', '').strip()

    # Base query: active (not archived) items
    query = GlobalItem.query.filter(GlobalItem.is_archived != True)

    # Filter by item type if provided
    if item_type:
        query = query.filter(GlobalItem.item_type == item_type)

    # Filter by ingredient category name if provided and type is ingredient
    if category_filter and item_type == 'ingredient':
        query = query.join(IngredientCategory, GlobalItem.ingredient_category_id == IngredientCategory.id).filter(
            IngredientCategory.name == category_filter
        )

    # Apply search across name and aka_names JSON
    if search_query:
        term = f"%{search_query}%"
        try:
            query = query.filter(
                db.or_(
                    GlobalItem.name.ilike(term),
                    GlobalItem.aka_names.op('::text').ilike(term)
                )
            )
        except Exception:
            query = query.filter(GlobalItem.name.ilike(term))

    items = query.order_by(GlobalItem.item_type.asc(), GlobalItem.name.asc()).limit(500).all()

    # Get global ingredient categories for the filter dropdown (only for ingredients)
    categories = []
    if item_type == 'ingredient':
        global_categories = IngredientCategory.query.filter_by(
            organization_id=None,
            is_active=True,
            is_global_category=True
        ).order_by(IngredientCategory.name).all()
        categories = [cat.name for cat in global_categories]

    return render_template(
        'library/global_items_public.html',
        items=items,
        categories=categories,
        selected_type=item_type,
        selected_category=category_filter,
        search_query=search_query,
    )


@global_library_bp.route('/global-items/<int:item_id>/stats')
def global_library_item_stats(item_id: int):
    """Public stats endpoint for a GlobalItem, including cost distribution and rollup."""
    try:
        rollup = GlobalItemStatsService.get_rollup(item_id)
        cost = GlobalItemStatsService.get_cost_distribution(item_id)
        return {
            'success': True,
            'rollup': rollup,
            'cost': cost,
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}, 500

@global_library_bp.route('/global-items/<int:item_id>')
def global_library_item_detail(item_id: int):
    """Public endpoint for a single global item's basic details."""
    try:
        from app.models import GlobalItem
        item = GlobalItem.query.filter_by(id=item_id, is_archived=False).first()
        if not item:
            return {'success': False, 'error': 'Item not found'}, 404
        
        return {
            'success': True,
            'item': {
                'id': item.id,
                'name': item.name,
                'item_type': item.item_type,
                'default_unit': item.default_unit,
                'density': item.density,
                'capacity': item.capacity,
                'capacity_unit': item.capacity_unit,
                'default_is_perishable': item.default_is_perishable,
                'recommended_shelf_life_days': item.recommended_shelf_life_days,
                'category_name': item.ingredient_category.name if item.ingredient_category else None,
                'aka_names': item.aka_names
            }
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}, 500