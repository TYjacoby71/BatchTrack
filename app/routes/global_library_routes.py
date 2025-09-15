from flask import Blueprint, render_template, request
from app.models import db, GlobalItem

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
        from app.models.category import IngredientCategory
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

    # Ingredient categories list for filter dropdown
    from app.models.category import IngredientCategory
    categories = db.session.query(IngredientCategory.name).join(
        GlobalItem, GlobalItem.ingredient_category_id == IngredientCategory.id
    ).filter(GlobalItem.item_type == 'ingredient').distinct().order_by(IngredientCategory.name).all()
    categories = [c[0] for c in categories if c[0]]

    return render_template(
        'library/global_items_public.html',
        items=items,
        categories=categories,
        selected_type=item_type,
        selected_category=category_filter,
        search_query=search_query,
    )

