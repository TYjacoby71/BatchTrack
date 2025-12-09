import json
from typing import Optional

from flask import Blueprint, render_template, request, redirect, url_for, current_app
from app.models import db, GlobalItem
from app.services.statistics import AnalyticsDataService
from app.models.category import IngredientCategory
from app.utils.seo import slugify_value
from app.extensions import limiter, cache
from app.utils.cache_utils import should_bypass_cache, stable_cache_key
from app.services.cache_invalidation import global_library_cache_key

global_library_bp = Blueprint('global_library_bp', __name__)


@global_library_bp.route('/global-items')
@limiter.limit("60000/hour;5000/minute")
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

    cache_payload = {
        "item_type": item_type or "",
        "category": category_filter or "",
        "search": search_query or "",
    }
    raw_cache_key = stable_cache_key("global_library", cache_payload)
    cache_key = global_library_cache_key(raw_cache_key)

    if should_bypass_cache():
        cache.delete(cache_key)
    else:
        cached_page = cache.get(cache_key)
        if cached_page is not None:
            return cached_page

    # Filter by item type if provided
    if item_type:
        query = query.filter(GlobalItem.item_type == item_type)

    # Filter by ingredient category name if provided and type is ingredient
    if category_filter and item_type == 'ingredient':
        query = query.join(IngredientCategory, GlobalItem.ingredient_category_id == IngredientCategory.id).filter(
            IngredientCategory.name == category_filter
        )

    # Apply search across name and aliases
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

    items = query.order_by(GlobalItem.item_type.asc(), GlobalItem.name.asc()).limit(200).all()

    # Get global ingredient categories for the filter dropdown (only for ingredients)
    categories = []
    if item_type == 'ingredient':
        global_categories = IngredientCategory.query.filter_by(
            organization_id=None,
            is_active=True,
            is_global_category=True
        ).order_by(IngredientCategory.name).all()
        categories = [cat.name for cat in global_categories]

    canonical_url = url_for('global_library_bp.global_library', _external=True)
    description_bits = [
        "Search the BatchTrack global inventory library.",
        "Browse ingredients, containers, packaging, and consumables with authoritative specs.",
    ]
    if item_type:
        description_bits.insert(0, f"{item_type.capitalize()} from the BatchTrack library.")

    rendered = render_template(
        'library/global_items_public.html',
        items=items,
        categories=categories,
        selected_type=item_type,
        selected_category=category_filter,
        search_query=search_query,
        slugify=slugify_value,
        page_title="Global Item Library — BatchTrack",
        page_description=" ".join(description_bits),
        canonical_url=canonical_url,
    )
    cache.set(cache_key, rendered, timeout=current_app.config.get("GLOBAL_LIBRARY_CACHE_TTL", 300))
    return rendered


@global_library_bp.route('/global-items/<int:item_id>')
@global_library_bp.route('/global-items/<int:item_id>-<slug>')
def global_item_detail(item_id: int, slug: Optional[str] = None):
    """Public detail page for a specific Global Item."""
    gi = GlobalItem.query.filter(
        GlobalItem.is_archived != True,
        GlobalItem.id == item_id,
    ).first_or_404()

    canonical_slug = slugify_value(gi.name)
    if slug != canonical_slug:
        return redirect(
            url_for('global_library_bp.global_item_detail', item_id=item_id, slug=canonical_slug),
            code=301,
        )

    metadata = gi.metadata_json or {}
    description = metadata.get('meta_description') or f"{gi.name} specs, density, and usage guidance from the BatchTrack global library."
    page_title = metadata.get('meta_title') or f"{gi.name} — {gi.item_type.capitalize()} Reference"
    canonical_url = url_for('global_library_bp.global_item_detail', item_id=item_id, slug=canonical_slug, _external=True)

    rollup = {}
    cost = {}
    try:
        rollup = AnalyticsDataService.get_global_item_rollup(item_id) or {}
    except Exception:
        rollup = {}
    try:
        cost = AnalyticsDataService.get_cost_distribution(item_id) or {}
    except Exception:
        cost = {}

    related_items = []
    try:
        related_query = GlobalItem.query.filter(
            GlobalItem.item_type == gi.item_type,
            GlobalItem.id != gi.id,
            GlobalItem.is_archived != True,
        ).order_by(GlobalItem.name.asc()).limit(6)
        if gi.ingredient_category_id:
            related_query = related_query.filter(
                GlobalItem.ingredient_category_id == gi.ingredient_category_id
            )
        related_items = related_query.all()
    except Exception:
        related_items = []

    structured_data = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": gi.name,
        "description": description,
        "url": canonical_url,
        "category": gi.item_type,
        "sku": str(gi.id),
        "additionalProperty": [],
    }
    if gi.aliases:
        structured_data["alternateName"] = gi.aliases
    if gi.density is not None:
        structured_data["additionalProperty"].append({
            "@type": "PropertyValue",
            "name": "Density",
            "value": gi.density,
            "unitCode": "D41",
        })
    if gi.capacity is not None:
        structured_data["additionalProperty"].append({
            "@type": "PropertyValue",
            "name": "Capacity",
            "value": gi.capacity,
            "unitCode": gi.capacity_unit or "",
        })

    ld_json = json.dumps(structured_data, ensure_ascii=False)

    return render_template(
        'library/global_item_detail.html',
        item=gi,
        metadata=metadata,
        related_items=related_items,
        rollup=rollup,
        cost=cost,
        structured_data=ld_json,
        page_title=page_title,
        page_description=description,
        canonical_url=canonical_url,
        page_og_image=metadata.get('hero_image'),
        slugify=slugify_value,
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
        gi = GlobalItem.query.get_or_404(item_id)

        rollup = AnalyticsDataService.get_global_item_rollup(item_id)
        cost = AnalyticsDataService.get_cost_distribution(item_id)

        # Basic item details for sidebar population
        item_payload = {
            'id': gi.id,
            'name': gi.name,
            'item_type': gi.item_type,
            'ingredient': {
                'id': gi.ingredient.id,
                'name': gi.ingredient.name,
                'slug': gi.ingredient.slug,
                'inci_name': gi.ingredient.inci_name,
                'cas_number': gi.ingredient.cas_number,
            } if getattr(gi, 'ingredient', None) else None,
            'physical_form': gi.physical_form.name if getattr(gi, 'physical_form', None) else None,
            'physical_form_slug': gi.physical_form.slug if getattr(gi, 'physical_form', None) else None,
            'default_unit': gi.default_unit,
            'density': gi.density,
            'capacity': gi.capacity,
            'capacity_unit': gi.capacity_unit,
            'ingredient_category_id': gi.ingredient_category_id,
            'ingredient_category_name': gi.ingredient_category.name if gi.ingredient_category else None,
            'aliases': gi.aliases or [],
            'functions': [tag.name for tag in getattr(gi, 'functions', [])],
            'applications': [tag.name for tag in getattr(gi, 'applications', [])],
            'default_is_perishable': gi.default_is_perishable,
            'recommended_shelf_life_days': gi.recommended_shelf_life_days,
            'recommended_fragrance_load_pct': gi.recommended_fragrance_load_pct,
            'is_active_ingredient': gi.is_active_ingredient,
            'inci_name': gi.inci_name,
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
            'comedogenic_rating': getattr(gi, 'comedogenic_rating', None),
            'fatty_acid_profile': getattr(gi, 'fatty_acid_profile', None),
            # Baking
            'protein_content_pct': getattr(gi, 'protein_content_pct', None),
            # Brewing
            'brewing_color_srm': getattr(gi, 'brewing_color_srm', None),
            'brewing_potential_sg': getattr(gi, 'brewing_potential_sg', None),
            'brewing_diastatic_power_lintner': getattr(gi, 'brewing_diastatic_power_lintner', None),
            # Certifications
            'certifications': gi.certifications or [],
        }

        from flask import jsonify
        return jsonify({
            'success': True,
            'item': item_payload,
            'rollup': rollup,
            'cost': cost,
        })
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting stats for global item {item_id}: {str(e)}", exc_info=True)
        from flask import jsonify
        return jsonify({'success': False, 'error': str(e)}), 500