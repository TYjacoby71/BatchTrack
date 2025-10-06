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

    # Apply search across name and aliases (falls back to aka_names JSON)
    if search_query:
        term = f"%{search_query}%"
        try:
            # Try alias table first for scalable search
            from app.models import GlobalItem as _GI
            from sqlalchemy import or_, exists, and_
            alias_tbl = db.Table('global_item_alias', db.metadata, autoload_with=db.engine)
            query = query.filter(
                or_(
                    _GI.name.ilike(term),
                    exists().where(and_(alias_tbl.c.global_item_id == _GI.id, alias_tbl.c.alias.ilike(term)))
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
    """Public stats endpoint for a GlobalItem, including cost distribution, rollup,
    basic item details, and category-based visibility flags when applicable.
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Stats request for global item {item_id}")
    
    try:
        from app.models.global_item import GlobalItem
        from app.models.category import IngredientCategory

        gi = GlobalItem.query.get_or_404(item_id)

        rollup = GlobalItemStatsService.get_rollup(item_id)
        cost = GlobalItemStatsService.get_cost_distribution(item_id)

        # Basic item details for sidebar population
        item_payload = {
            'id': gi.id,
            'name': gi.name,
            'item_type': gi.item_type,
            'default_unit': gi.default_unit,
            'density': gi.density,
            'capacity': gi.capacity,
            'capacity_unit': gi.capacity_unit,
            'ingredient_category_id': gi.ingredient_category_id,
            'ingredient_category_name': gi.ingredient_category.name if gi.ingredient_category else None,
            # Container fields
            'container_material': getattr(gi, 'container_material', None),
            'container_type': getattr(gi, 'container_type', None),
            'container_style': getattr(gi, 'container_style', None),
            'container_color': getattr(gi, 'container_color', None),
            # Soap/cosmetic fields (raw values)
            'saponification_value': getattr(gi, 'saponification_value', None),
            'iodine_value': getattr(gi, 'iodine_value', None),
            'melting_point_c': getattr(gi, 'melting_point_c', None),
            'flash_point_c': getattr(gi, 'flash_point_c', None),
            'ph_value': getattr(gi, 'ph_value', None),
            'moisture_content_percent': getattr(gi, 'moisture_content_percent', None),
            'shelf_life_months': getattr(gi, 'shelf_life_months', None),
            'comedogenic_rating': getattr(gi, 'comedogenic_rating', None),
        }

        # Category visibility flags if ingredient category exists
        category_visibility = None
        if gi.ingredient_category_id:
            cat = IngredientCategory.query.get(gi.ingredient_category_id)
            if cat:
                category_visibility = {
                    'show_saponification_value': getattr(cat, 'show_saponification_value', False),
                    'show_iodine_value': getattr(cat, 'show_iodine_value', False),
                    'show_melting_point': getattr(cat, 'show_melting_point', False),
                    'show_flash_point': getattr(cat, 'show_flash_point', False),
                    'show_ph_value': getattr(cat, 'show_ph_value', False),
                    'show_moisture_content': getattr(cat, 'show_moisture_content', False),
                    'show_shelf_life_months': getattr(cat, 'show_shelf_life_months', False),
                    'show_comedogenic_rating': getattr(cat, 'show_comedogenic_rating', False),
                }

        from flask import jsonify
        return jsonify({
            'success': True,
            'item': item_payload,
            'rollup': rollup,
            'cost': cost,
            'category_visibility': category_visibility,
        })
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting stats for global item {item_id}: {str(e)}", exc_info=True)
        from flask import jsonify
        return jsonify({'success': False, 'error': str(e)}), 500