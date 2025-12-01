from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from ...models import IngredientCategory, InventoryItem, GlobalItem, db
from ...services.statistics.global_item_stats import GlobalItemStatsService
from ...services.density_assignment_service import DensityAssignmentService
from ...extensions import limiter

ingredient_api_bp = Blueprint('ingredient_api', __name__)

@ingredient_api_bp.route('/categories', methods=['GET'])
def get_categories():
    """Return ingredient categories: global categories plus user's custom ones."""
    if not current_user.is_authenticated:
        return jsonify([])

    # Get only global ingredient categories (no user-owned categories)
    all_categories = IngredientCategory.query.filter_by(
        organization_id=None,
        is_active=True,
        is_global_category=True
    ).order_by(IngredientCategory.name.asc()).all()

    return jsonify([
        {
            'id': cat.id,
            'name': cat.name,
            'default_density': cat.default_density
        }
        for cat in all_categories
    ])

@ingredient_api_bp.route('/global-library/density-options', methods=['GET'])
@login_required
def get_global_library_density_options():
    """Expose global ingredient density options sourced from the Global Inventory Library."""
    include_uncategorized = request.args.get('include_uncategorized', '1') not in {'0', 'false', 'False'}
    payload = DensityAssignmentService.build_global_library_density_options(include_uncategorized=include_uncategorized)
    return jsonify(payload)

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
@limiter.limit("300 per minute")
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

    # Only show true ingredients (exclude containers, products, etc.)
    query = query.filter(InventoryItem.type == 'ingredient')

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

@ingredient_api_bp.route('/ingredients/create-or-link', methods=['POST'])
@login_required
def create_or_link_ingredient():
    """Create an inventory item by name if not present, optionally linking to a Global Item when a match exists.
    Input JSON: { name, type='ingredient'|'container'|'packaging'|'consumable', unit?, global_item_id? }
    Returns: { success, item: {id,name,unit,type,global_item_id} }
    """
    try:
        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        inv_type = (data.get('type') or 'ingredient').strip()
        unit = (data.get('unit') or '').strip()
        gi_id = data.get('global_item_id')

        if not name:
            return jsonify({'success': False, 'error': 'Name required'}), 400

        # Try existing org item exact match
        existing = InventoryItem.query.filter_by(
            organization_id=current_user.organization_id,
            name=name,
            type=inv_type
        ).order_by(InventoryItem.id.asc()).first()
        if existing:
            return jsonify({'success': True, 'item': {
                'id': existing.id,
                'name': existing.name,
                'unit': existing.unit,
                'type': existing.type,
                'global_item_id': getattr(existing, 'global_item_id', None)
            }})

        # If no org item, attempt to link to provided global item or find one by name
        global_item = None
        if gi_id:
            global_item = db.session.get(GlobalItem, int(gi_id))
        else:
            global_item = GlobalItem.query.filter(
                func.lower(GlobalItem.name) == func.lower(db.literal(name)),
                GlobalItem.item_type == inv_type,
                GlobalItem.is_archived != True
            ).order_by(GlobalItem.id.asc()).first()

        # Create new zero-qty org item
        new_item = InventoryItem(
            name=name,
            unit=(unit or (global_item.default_unit if global_item and global_item.default_unit else 'count' if inv_type=='container' else 'g')),
            type=inv_type,
            quantity=0.0,
            organization_id=current_user.organization_id,
            created_by=current_user.id
        )
        if global_item:
            new_item.global_item_id = global_item.id
            new_item.ownership = 'global'
            # If container, prefer count unit; set capacity metadata when present
            if inv_type == 'container' and getattr(global_item, 'capacity', None):
                new_item.capacity = global_item.capacity
                new_item.capacity_unit = global_item.capacity_unit

        db.session.add(new_item)
        db.session.commit()
        return jsonify({'success': True, 'item': {
            'id': new_item.id,
            'name': new_item.name,
            'unit': new_item.unit,
            'type': new_item.type,
            'global_item_id': getattr(new_item, 'global_item_id', None)
        }})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

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
    # Match by name or any synonym in aliases (JSON)
    name_match = GlobalItem.name.ilike(ilike_term)
    try:
        from sqlalchemy import or_
        alias_match = GlobalItem.aliases.cast(db.String).ilike(ilike_term)
        items = query.filter(or_(name_match, alias_match)).order_by(func.length(GlobalItem.name).asc()).limit(20).all()
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
            'container_material': getattr(gi, 'container_material', None),
            'container_type': getattr(gi, 'container_type', None),
            'container_style': getattr(gi, 'container_style', None),
            'container_color': getattr(gi, 'container_color', None),
            'aliases': gi.aliases,
            'default_is_perishable': gi.default_is_perishable,
            'recommended_shelf_life_days': gi.recommended_shelf_life_days,
            'recommended_usage_rate': gi.recommended_usage_rate,
            'recommended_fragrance_load_pct': gi.recommended_fragrance_load_pct,
            'inci_name': gi.inci_name,
            'protein_content_pct': gi.protein_content_pct,
            'brewing_color_srm': gi.brewing_color_srm,
            'brewing_potential_sg': gi.brewing_potential_sg,
            'brewing_diastatic_power_lintner': gi.brewing_diastatic_power_lintner,
            'certifications': gi.certifications or [],
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