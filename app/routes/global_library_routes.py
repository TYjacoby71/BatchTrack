import json
from typing import Optional
from datetime import datetime, timezone, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, current_app, flash, session, abort
from flask_login import current_user
from app.models import GlobalItem, InventoryItem
from app.services.statistics import AnalyticsDataService
from app.services.inventory_adjustment import create_inventory_item
from app.utils.seo import slugify_value
from app.utils.permissions import _permission_denied_response, _record_required_permissions, has_permission
from app.extensions import limiter, cache
from app.utils.cache_utils import should_bypass_cache, stable_cache_key
from app.services.cache_invalidation import global_library_cache_key
from app.utils.settings import is_feature_enabled
from app.services.global_item_listing_service import (
    DEFAULT_PER_PAGE_OPTIONS as GLOBAL_LIBRARY_PER_PAGE_OPTIONS,
    DEFAULT_SCOPE as GLOBAL_LIBRARY_DEFAULT_SCOPE,
    SCOPE_LABELS as GLOBAL_SCOPE_LABELS,
    VALID_SCOPES as GLOBAL_LIBRARY_VALID_SCOPES,
    fetch_global_item_listing,
)

global_library_bp = Blueprint('global_library_bp', __name__)

PUBLIC_LIBRARY_SEARCH_LIMIT = 10
PUBLIC_LIBRARY_DETAIL_LIMIT = 10
PUBLIC_LIBRARY_WINDOW_HOURS = 24


def _global_library_rate_limit() -> str:
    if current_user.is_authenticated:
        return "6000/hour;300/minute"
    return "600/hour;60/minute"


def _global_library_enabled() -> bool:
    if current_user.is_authenticated and getattr(current_user, "user_type", "") == "developer":
        return True
    return is_feature_enabled("FEATURE_GLOBAL_ITEM_LIBRARY")


def _advance_public_counter(key: str, limit: int) -> tuple[bool, int]:
    """Advance a session counter and return (allowed, remaining)."""
    record = session.get(key) or {}
    now = datetime.now(timezone.utc)
    try:
        last_ts = record.get("timestamp")
        if last_ts:
            last_dt = datetime.fromisoformat(last_ts)
            if now - last_dt > timedelta(hours=PUBLIC_LIBRARY_WINDOW_HOURS):
                record = {}
    except Exception:
        record = {}
    count = int(record.get("count") or 0)
    if count >= limit:
        return False, 0
    count += 1
    record["count"] = count
    record["timestamp"] = now.isoformat()
    session[key] = record
    return True, max(0, limit - count)


def _remaining_public_counter(key: str, limit: int) -> int:
    record = session.get(key) or {}
    try:
        last_ts = record.get("timestamp")
        if last_ts:
            last_dt = datetime.fromisoformat(last_ts)
            if datetime.now(timezone.utc) - last_dt > timedelta(hours=PUBLIC_LIBRARY_WINDOW_HOURS):
                return limit
    except Exception:
        return limit
    count = int(record.get("count") or 0)
    return max(0, limit - count)


@global_library_bp.route('/global-items')
@limiter.limit(_global_library_rate_limit)
def global_library():
    """Public, read-only view of the Global Inventory Library.
    Supports filtering by item type and ingredient category, plus text search.
    Query params:
      - type: ingredient|container|packaging|consumable (optional)
      - category: ingredient category name (only when type=ingredient)
      - search: free text search across name and aka names
    """
    if not _global_library_enabled():
        abort(404)
    scope_param = (request.args.get('scope') or request.args.get('type') or '').strip()
    search_query = (request.args.get('search') or '').strip()
    raw_category = (request.args.get('category') or '').strip()
    show_columns = request.args.get('show_columns') == 'true'
    page = request.args.get('page', type=int) or 1
    if page < 1:
        page = 1
    per_page_input = request.args.get('page_size', type=int)
    per_page_value = (
        per_page_input
        if per_page_input in GLOBAL_LIBRARY_PER_PAGE_OPTIONS
        else GLOBAL_LIBRARY_PER_PAGE_OPTIONS[0]
    )

    normalized_scope = (scope_param or GLOBAL_LIBRARY_DEFAULT_SCOPE).lower() or GLOBAL_LIBRARY_DEFAULT_SCOPE
    if normalized_scope not in GLOBAL_LIBRARY_VALID_SCOPES:
        normalized_scope = GLOBAL_LIBRARY_DEFAULT_SCOPE
    category_key = raw_category if normalized_scope == "ingredient" else ""

    preview_remaining = None
    search_remaining = None
    if not current_user.is_authenticated:
        preview_remaining = _remaining_public_counter("global_library_detail_views", PUBLIC_LIBRARY_DETAIL_LIMIT)
        search_remaining = _remaining_public_counter("global_library_search_views", PUBLIC_LIBRARY_SEARCH_LIMIT)
        if search_query:
            allowed, remaining = _advance_public_counter("global_library_search_views", PUBLIC_LIBRARY_SEARCH_LIMIT)
            if not allowed:
                flash("Create a free account to keep searching the global library. You've reached the preview limit.")
                return redirect(url_for('auth.quick_signup', next=request.full_path))
            search_remaining = remaining

    cache_payload = {
        "scope": normalized_scope,
        "category": category_key,
        "search": search_query,
        "page": page,
        "page_size": per_page_value,
    }
    raw_cache_key = stable_cache_key("global_library", cache_payload)
    cache_key = global_library_cache_key(raw_cache_key)

    bypass_cache = should_bypass_cache() or not current_user.is_authenticated
    if bypass_cache:
        cache.delete(cache_key)
    else:
        cached_page = cache.get(cache_key)
        if cached_page is not None:
            return cached_page

    listing = fetch_global_item_listing(
        scope=scope_param,
        search_query=search_query,
        category_filter=raw_category,
        page=page,
        per_page=per_page_input,
        per_page_options=GLOBAL_LIBRARY_PER_PAGE_OPTIONS,
    )

    active_scope = listing["scope"]
    selected_category = raw_category if active_scope == "ingredient" else ""

    def _shared_query_params(target_scope: str | None = None) -> dict[str, str]:
        params: dict[str, str] = {}
        params["scope"] = target_scope or active_scope
        if search_query:
            params["search"] = search_query
        if listing["per_page"] != GLOBAL_LIBRARY_PER_PAGE_OPTIONS[0]:
            params["page_size"] = str(listing["per_page"])
        if selected_category and (
            (target_scope == "ingredient")
            or (target_scope is None and active_scope == "ingredient")
        ):
            params["category"] = selected_category
        if show_columns:
            params["show_columns"] = "true"
        return params

    def build_page_url(page_number: int) -> str:
        params = _shared_query_params()
        params["page"] = str(page_number)
        return url_for('global_library_bp.global_library', **params)

    def build_scope_url(target_scope: str) -> str:
        params = _shared_query_params(target_scope)
        params.pop("page", None)
        params["scope"] = target_scope
        return url_for('global_library_bp.global_library', **params)

    clear_filters_url = url_for('global_library_bp.global_library', scope=active_scope)
    canonical_url = url_for('global_library_bp.global_library', _external=True)
    description_bits = [
        "Search the BatchTrack global inventory library.",
        "Browse ingredients, containers, packaging, and consumables with authoritative specs.",
    ]
    if active_scope:
        description_bits.insert(0, f"{GLOBAL_SCOPE_LABELS.get(active_scope, active_scope.title())} in the BatchTrack library.")

    can_manage = current_user.is_authenticated and getattr(current_user, "user_type", "") == "developer"

    rendered = render_template(
        'library/global_items_list.html',
        items=listing["items"],
        grouped_items=listing["grouped_items"],
        categories=listing["categories"],
        active_scope=active_scope,
        scope_labels=GLOBAL_SCOPE_LABELS,
        selected_category=selected_category,
        search_query=search_query,
        pagination=listing["pagination"],
        per_page=listing["per_page"],
        per_page_options=GLOBAL_LIBRARY_PER_PAGE_OPTIONS,
        build_page_url=build_page_url,
        build_scope_url=build_scope_url,
        first_item_index=listing["first_item_index"],
        last_item_index=listing["last_item_index"],
        clear_filters_url=clear_filters_url,
        show_dev_controls=can_manage,
        show_hidden_columns=can_manage and show_columns,
        is_public_view=True,
        slugify=slugify_value,
        developer_link_base=url_for('developer.global_item_detail', item_id=0)[:-1] if can_manage else None,
        preview_remaining=preview_remaining,
        search_remaining=search_remaining,
        page_title="Global Item Library — BatchTrack",
        page_description=" ".join(description_bits),
        canonical_url=canonical_url,
    )

    if not bypass_cache:
        cache.set(cache_key, rendered, timeout=current_app.config.get("GLOBAL_LIBRARY_CACHE_TTL", 300))
    return rendered


@global_library_bp.route('/global-items/<int:item_id>')
@global_library_bp.route('/global-items/<int:item_id>-<slug>')
@limiter.limit(_global_library_rate_limit)
def global_item_detail(item_id: int, slug: Optional[str] = None):
    """Public detail page for a specific Global Item."""
    if not _global_library_enabled():
        abort(404)
    gi = GlobalItem.query.filter(
        GlobalItem.is_archived != True,
        GlobalItem.id == item_id,
    ).first_or_404()

    preview_remaining = None
    if not current_user.is_authenticated:
        allowed, preview_remaining = _advance_public_counter(
            "global_library_detail_views", PUBLIC_LIBRARY_DETAIL_LIMIT
        )
        if not allowed:
            flash("Create a free account to keep exploring the global library. You've reached the 10-item preview limit.")
            return redirect(url_for('auth.quick_signup', next=request.path, global_item_id=item_id))

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
        preview_remaining=preview_remaining,
    )


@global_library_bp.route('/global-items/<int:item_id>/save-to-inventory')
@limiter.limit("6000/hour;300/minute")
@_record_required_permissions("inventory.edit")
def save_global_item_to_inventory(item_id: int):
    """Save a public global item into the authenticated user's inventory.

    If unauthenticated, redirect to a lightweight free-account signup flow and
    then return here to complete the save.
    """
    if not _global_library_enabled():
        abort(404)
    gi = GlobalItem.query.filter(
        GlobalItem.is_archived != True,
        GlobalItem.id == item_id,
    ).first_or_404()

    if not current_user.is_authenticated:
        next_path = url_for('global_library_bp.save_global_item_to_inventory', item_id=item_id)
        return redirect(url_for('auth.quick_signup', next=next_path, global_item_id=item_id))

    if not has_permission(current_user, "inventory.edit"):
        return _permission_denied_response("inventory.edit")

    org_id = getattr(current_user, "organization_id", None)
    if not org_id:
        flash("No organization found for your account.", "error")
        return redirect(url_for('app_routes.dashboard'))

    existing = InventoryItem.query.filter(
        InventoryItem.organization_id == org_id,
        InventoryItem.global_item_id == item_id,
        InventoryItem.is_archived.is_(False),
    ).first()
    if existing:
        flash(f"{gi.name} is already in your inventory.", "info")
        return redirect(url_for('inventory.view_inventory', id=existing.id))

    form_data = {
        "name": gi.name,
        "type": gi.item_type,
        "global_item_id": str(gi.id),
        "quantity": "0",
    }
    success, message, created_id = create_inventory_item(
        form_data=form_data,
        organization_id=org_id,
        created_by=getattr(current_user, "id", None),
        auto_commit=True,
    )

    if success and created_id:
        flash(f"Saved {gi.name} to your inventory.", "success")
        return redirect(url_for('inventory.view_inventory', id=created_id))

    flash(message or "Unable to save this item to your inventory right now.", "error")
    return redirect(url_for('inventory.list_inventory'))


@global_library_bp.route('/global-items/<int:item_id>/stats')
def global_library_item_stats(item_id: int):
    """Public stats endpoint for a GlobalItem, including cost distribution, rollup,
    and basic item details.
    """
    if not _global_library_enabled():
        abort(404)
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
            'variation': {
                'id': gi.variation.id,
                'name': gi.variation.name,
                'slug': gi.variation.slug,
                'default_unit': gi.variation.default_unit,
                'form_bypass': gi.variation.form_bypass,
                'physical_form_id': gi.variation.physical_form_id,
                'physical_form_name': gi.variation.physical_form.name if getattr(gi.variation, 'physical_form', None) else None,
                'physical_form_slug': gi.variation.physical_form.slug if getattr(gi.variation, 'physical_form', None) else None,
            } if getattr(gi, 'variation', None) else None,
            # Backwards-compatible physical form fields (derived from variation when present)
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
            'cas_number': getattr(gi, 'cas_number', None),
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