from collections import OrderedDict

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from app.utils.permissions import require_permission

from ...extensions import cache, limiter
from ...models import GlobalItem, IngredientCategory, InventoryItem, db
from ...models.ingredient_reference import IngredientDefinition, PhysicalForm, Variation
from ...services.cache_invalidation import global_library_cache_key
from ...services.density_assignment_service import DensityAssignmentService
from ...services.statistics.global_item_stats import GlobalItemStatsService
from ...utils.cache_utils import stable_cache_key

ingredient_api_bp = Blueprint("ingredient_api", __name__)


def _global_library_cache_timeout() -> int:
    return current_app.config.get(
        "GLOBAL_LIBRARY_CACHE_TIMEOUT",
        current_app.config.get("CACHE_DEFAULT_TIMEOUT", 120),
    )


@ingredient_api_bp.route("/categories", methods=["GET"])
@login_required
@require_permission("inventory.view")
def get_categories():
    """Return ingredient categories: global categories plus user's custom ones."""

    # Get only global ingredient categories (no user-owned categories)
    all_categories = (
        IngredientCategory.query.filter_by(
            organization_id=None, is_active=True, is_global_category=True
        )
        .order_by(IngredientCategory.name.asc())
        .all()
    )

    return jsonify(
        [
            {"id": cat.id, "name": cat.name, "default_density": cat.default_density}
            for cat in all_categories
        ]
    )


@ingredient_api_bp.route("/global-library/density-options", methods=["GET"])
@login_required
@require_permission("inventory.view")
def get_global_library_density_options():
    """Expose global ingredient density options sourced from the Global Inventory Library."""
    include_uncategorized = request.args.get("include_uncategorized", "1") not in {
        "0",
        "false",
        "False",
    }
    payload = DensityAssignmentService.build_global_library_density_options(
        include_uncategorized=include_uncategorized
    )
    return jsonify(payload)


@ingredient_api_bp.route("/ingredient/<int:id>/density", methods=["GET"])
@login_required
@require_permission("inventory.view")
def get_ingredient_density(id):
    ingredient = InventoryItem.query.get_or_404(id)
    if ingredient.density:
        return jsonify({"density": ingredient.density})
    elif ingredient.category:
        return jsonify({"density": ingredient.category.default_density})
    return jsonify({"density": 1.0})


@ingredient_api_bp.route("/ingredients/search", methods=["GET"])
@login_required
@limiter.limit("3000/minute")
@require_permission("inventory.view")
def search_ingredients():
    """Search existing inventory items and return top matches for name field autocomplete.
    This preserves current add flow while enabling typeahead suggestions.
    """
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"results": []})

    query = InventoryItem.query.options(
        joinedload(InventoryItem.global_item).joinedload(GlobalItem.ingredient),
        joinedload(InventoryItem.global_item)
        .joinedload(GlobalItem.variation)
        .joinedload(Variation.physical_form),
    )
    # Scope to the user's organization for privacy
    if current_user.organization_id:
        query = query.filter(
            InventoryItem.organization_id == current_user.organization_id
        )

    # Only show true ingredients (exclude containers, products, etc.)
    query = query.filter(InventoryItem.type == "ingredient")

    ilike_term = f"%{q}%"
    results = (
        query.filter(InventoryItem.name.ilike(ilike_term))
        .order_by(func.length(InventoryItem.name).asc())
        .limit(20)
        .all()
    )

    payload = []
    for item in results:
        global_obj = getattr(item, "global_item", None)
        ingredient_obj = getattr(global_obj, "ingredient", None) if global_obj else None
        variation_obj = getattr(global_obj, "variation", None) if global_obj else None
        physical_form_obj = (
            getattr(variation_obj, "physical_form", None) if variation_obj else None
        )
        payload.append(
            {
                "id": item.id,
                "text": item.name,
                "category": item.category.name if item.category else None,
                "unit": item.unit,
                "density": item.density,
                "type": item.type,
                "global_item_id": item.global_item_id,
                "ingredient_id": ingredient_obj.id if ingredient_obj else None,
                "ingredient_name": ingredient_obj.name if ingredient_obj else item.name,
                "variation_id": variation_obj.id if variation_obj else None,
                "variation_name": variation_obj.name if variation_obj else None,
                "physical_form_id": physical_form_obj.id if physical_form_obj else None,
                "physical_form_name": (
                    physical_form_obj.name if physical_form_obj else None
                ),
                "cost_per_unit": item.cost_per_unit,
                "inci_name": getattr(item, "inci_name", None),
                "cas_number": getattr(item, "cas_number", None),
            }
        )

    return jsonify({"results": payload})


@ingredient_api_bp.route("/ingredients/definitions/search", methods=["GET"])
@login_required
@limiter.limit("3000/minute")
@require_permission("inventory.view")
def search_ingredient_definitions():
    """Search ingredient definitions for the create global item form."""
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"results": []})

    ilike_term = f"%{q}%"
    definitions = (
        IngredientDefinition.query.filter(
            or_(
                IngredientDefinition.name.ilike(ilike_term),
                IngredientDefinition.inci_name.ilike(ilike_term),
                IngredientDefinition.cas_number.ilike(ilike_term),
            ),
            IngredientDefinition.is_active,
        )
        .order_by(func.length(IngredientDefinition.name).asc())
        .limit(20)
        .all()
    )

    results = []
    for definition in definitions:
        results.append(
            {
                "id": definition.id,
                "name": definition.name,
                "slug": definition.slug,
                "inci_name": definition.inci_name,
                "cas_number": definition.cas_number,
                "ingredient_category_id": definition.ingredient_category_id,
                "ingredient_category_name": (
                    definition.category.name if definition.category else None
                ),
                "description": definition.description,
            }
        )

    return jsonify({"results": results})


@ingredient_api_bp.route(
    "/ingredients/definitions/<int:ingredient_id>/forms", methods=["GET"]
)
@login_required
@limiter.limit("3000/minute")
@require_permission("inventory.view")
def list_forms_for_ingredient_definition(ingredient_id: int):
    """Return the existing global items tied to a specific ingredient definition."""
    ingredient = IngredientDefinition.query.get_or_404(ingredient_id)
    items = (
        GlobalItem.query.filter(
            GlobalItem.ingredient_id == ingredient.id,
            not GlobalItem.is_archived,
        )
        .order_by(GlobalItem.name.asc())
        .all()
    )

    payload = []
    for item in items:
        variation_obj = getattr(item, "variation", None)
        physical_form_obj = (
            getattr(variation_obj, "physical_form", None) if variation_obj else None
        )
        payload.append(
            {
                "id": item.id,
                "name": item.name,
                "variation_id": variation_obj.id if variation_obj else None,
                "variation_name": variation_obj.name if variation_obj else None,
                "variation_slug": variation_obj.slug if variation_obj else None,
                "variation": (
                    {
                        "id": variation_obj.id,
                        "name": variation_obj.name,
                        "slug": variation_obj.slug,
                        "default_unit": variation_obj.default_unit,
                        "form_bypass": variation_obj.form_bypass,
                        "physical_form_id": variation_obj.physical_form_id,
                        "physical_form_name": (
                            physical_form_obj.name if physical_form_obj else None
                        ),
                    }
                    if variation_obj
                    else None
                ),
                # Backwards-compatible physical form accessors
                "physical_form_name": (
                    physical_form_obj.name if physical_form_obj else None
                ),
                "physical_form_id": physical_form_obj.id if physical_form_obj else None,
                # Item-level labeling
                "inci_name": getattr(item, "inci_name", None),
                "cas_number": getattr(item, "cas_number", None),
            }
        )

    return jsonify(
        {
            "ingredient": {
                "id": ingredient.id,
                "name": ingredient.name,
                # Definition-level identifiers remain as defaults/fallbacks.
                "inci_name": ingredient.inci_name,
                "cas_number": ingredient.cas_number,
                "ingredient_category_id": ingredient.ingredient_category_id,
                "ingredient_category_name": (
                    ingredient.category.name if ingredient.category else None
                ),
            },
            "items": payload,
        }
    )


@ingredient_api_bp.route("/physical-forms/search", methods=["GET"])
@login_required
@limiter.limit("3000/minute")
@require_permission("inventory.view")
def search_physical_forms():
    """Search physical forms with lightweight typeahead payloads."""
    q = (request.args.get("q") or "").strip()
    query = PhysicalForm.query.filter(PhysicalForm.is_active)
    if q:
        ilike_term = f"%{q}%"
        query = query.filter(
            or_(
                PhysicalForm.name.ilike(ilike_term), PhysicalForm.slug.ilike(ilike_term)
            )
        )

    forms = (
        query.order_by(func.length(PhysicalForm.name).asc(), PhysicalForm.name.asc())
        .limit(30)
        .all()
    )
    return jsonify(
        {
            "results": [
                {
                    "id": physical_form.id,
                    "name": physical_form.name,
                    "slug": physical_form.slug,
                    "description": physical_form.description,
                }
                for physical_form in forms
            ]
        }
    )


@ingredient_api_bp.route("/variations/search", methods=["GET"])
@login_required
@limiter.limit("3000/minute")
@require_permission("inventory.view")
def search_variations():
    """Search curated variations with physical form metadata."""
    q = (request.args.get("q") or "").strip()
    query = Variation.query.filter(Variation.is_active)
    if q:
        ilike_term = f"%{q}%"
        query = query.filter(
            or_(Variation.name.ilike(ilike_term), Variation.slug.ilike(ilike_term))
        )

    variations = (
        query.order_by(func.length(Variation.name).asc(), Variation.name.asc())
        .limit(30)
        .all()
    )
    return jsonify(
        {
            "results": [
                {
                    "id": variation.id,
                    "name": variation.name,
                    "slug": variation.slug,
                    "description": variation.description,
                    "physical_form_name": (
                        variation.physical_form.name
                        if variation.physical_form
                        else None
                    ),
                    "physical_form_id": variation.physical_form_id,
                    "default_unit": variation.default_unit,
                    "form_bypass": variation.form_bypass,
                }
                for variation in variations
            ]
        }
    )


@ingredient_api_bp.route("/ingredients/create-or-link", methods=["POST"])
@login_required
@require_permission("inventory.edit")
def create_or_link_ingredient():
    """Create an inventory item by name if not present, optionally linking to a Global Item when a match exists.
    Input JSON: { name, type='ingredient'|'container'|'packaging'|'consumable', unit?, global_item_id? }
    Returns: { success, item: {id,name,unit,type,global_item_id} }
    """
    try:
        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        inv_type = (data.get("type") or "ingredient").strip()
        unit = (data.get("unit") or "").strip()
        gi_id = data.get("global_item_id")

        if not name:
            return jsonify({"success": False, "error": "Name required"}), 400

        # Try existing org item exact match
        existing = (
            InventoryItem.query.filter_by(
                organization_id=current_user.organization_id, name=name, type=inv_type
            )
            .order_by(InventoryItem.id.asc())
            .first()
        )
        if existing:
            return jsonify(
                {
                    "success": True,
                    "item": {
                        "id": existing.id,
                        "name": existing.name,
                        "unit": existing.unit,
                        "type": existing.type,
                        "global_item_id": getattr(existing, "global_item_id", None),
                    },
                }
            )

        # If no org item, attempt to link to provided global item or find one by name
        global_item = None
        if gi_id:
            global_item = db.session.get(GlobalItem, int(gi_id))
        else:
            global_item = (
                GlobalItem.query.filter(
                    func.lower(GlobalItem.name) == func.lower(db.literal(name)),
                    GlobalItem.item_type == inv_type,
                    not GlobalItem.is_archived,
                )
                .order_by(GlobalItem.id.asc())
                .first()
            )

        # Create new zero-qty org item
        new_item = InventoryItem(
            name=name,
            unit=(
                unit
                or (
                    global_item.default_unit
                    if global_item and global_item.default_unit
                    else "count" if inv_type == "container" else "g"
                )
            ),
            type=inv_type,
            quantity=0.0,
            organization_id=current_user.organization_id,
            created_by=current_user.id,
        )
        if global_item:
            new_item.global_item_id = global_item.id
            new_item.ownership = "global"
            # If container, prefer count unit; set capacity metadata when present
            if inv_type == "container" and getattr(global_item, "capacity", None):
                new_item.capacity = global_item.capacity
                new_item.capacity_unit = global_item.capacity_unit

        db.session.add(new_item)
        db.session.commit()
        return jsonify(
            {
                "success": True,
                "item": {
                    "id": new_item.id,
                    "name": new_item.name,
                    "unit": new_item.unit,
                    "type": new_item.type,
                    "global_item_id": getattr(new_item, "global_item_id", None),
                },
            }
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@ingredient_api_bp.route("/global-items/search", methods=["GET"])
@login_required
@require_permission("inventory.view")
def search_global_items():
    q = (request.args.get("q") or "").strip()
    item_type = (
        request.args.get("type") or ""
    ).strip()  # optional: ingredient, container, packaging, consumable
    if not q:
        return jsonify({"results": []})

    cache_key = None
    if cache:
        cache_key = global_library_cache_key(
            stable_cache_key(
                "auth-global-items",
                {
                    "q": q,
                    "item_type": item_type or "",
                    "group": request.args.get("group") or "",
                    "org": getattr(current_user, "organization_id", None),
                },
            )
        )
        cached_payload = cache.get(cache_key)
        if cached_payload:
            return jsonify(cached_payload)

    query = GlobalItem.query.filter(not GlobalItem.is_archived)
    if item_type:
        query = query.filter(GlobalItem.item_type == item_type)

    ilike_term = f"%{q}%"
    # Match by name or any synonym in aliases (JSON)
    name_match = GlobalItem.name.ilike(ilike_term)
    try:
        from sqlalchemy import or_

        alias_match = GlobalItem.aliases.cast(db.String).ilike(ilike_term)
        items = (
            query.filter(or_(name_match, alias_match))
            .order_by(func.length(GlobalItem.name).asc())
            .limit(20)
            .all()
        )
    except Exception:
        items = (
            query.filter(name_match)
            .order_by(func.length(GlobalItem.name).asc())
            .limit(20)
            .all()
        )

    group_mode = request.args.get("group") == "ingredient" and (
        not item_type or item_type == "ingredient"
    )
    grouped = OrderedDict() if group_mode else None
    results = []

    for gi in items:
        ingredient_obj = gi.ingredient if getattr(gi, "ingredient", None) else None
        ingredient_category_obj = (
            ingredient_obj.category
            if ingredient_obj and getattr(ingredient_obj, "category", None)
            else None
        )
        variation_obj = gi.variation if getattr(gi, "variation", None) else None
        physical_form_obj = (
            variation_obj.physical_form
            if variation_obj and getattr(variation_obj, "physical_form", None)
            else (gi.physical_form if getattr(gi, "physical_form", None) else None)
        )
        ingredient_payload = None
        if ingredient_obj:
            ingredient_payload = {
                "id": ingredient_obj.id,
                "name": ingredient_obj.name,
                "slug": ingredient_obj.slug,
                # Definition-level values are defaults; item-level values live on GlobalItem.
                "inci_name": ingredient_obj.inci_name,
                "cas_number": ingredient_obj.cas_number,
                "ingredient_category_id": ingredient_obj.ingredient_category_id,
                "ingredient_category_name": (
                    ingredient_category_obj.name if ingredient_category_obj else None
                ),
            }
        variation_payload = None
        if variation_obj:
            variation_payload = {
                "id": variation_obj.id,
                "name": variation_obj.name,
                "slug": variation_obj.slug,
                "default_unit": variation_obj.default_unit,
                "form_bypass": variation_obj.form_bypass,
                "physical_form_id": variation_obj.physical_form_id,
                "physical_form_name": (
                    physical_form_obj.name if physical_form_obj else None
                ),
            }
        physical_form_payload = None
        if physical_form_obj:
            physical_form_payload = {
                "id": physical_form_obj.id,
                "name": physical_form_obj.name,
                "slug": physical_form_obj.slug,
            }
        function_names = [tag.name for tag in getattr(gi, "functions", [])]
        application_names = [tag.name for tag in getattr(gi, "applications", [])]
        ingredient_category_name = (
            gi.ingredient_category.name if gi.ingredient_category else None
        )

        display_name = gi.name
        if (
            ingredient_payload
            and variation_payload
            and not variation_payload.get("form_bypass")
        ):
            display_name = f"{ingredient_payload['name']}, {variation_payload['name']}"
        elif ingredient_payload and physical_form_payload:
            display_name = (
                f"{ingredient_payload['name']} ({physical_form_payload['name']})"
            )
        elif ingredient_payload:
            display_name = ingredient_payload["name"]

        item_payload = {
            "id": gi.id,
            "name": display_name,
            "text": display_name,
            "display_name": display_name,
            "raw_name": gi.name,
            "item_type": gi.item_type,
            "ingredient": ingredient_payload,
            "variation": variation_payload,
            "variation_id": variation_payload["id"] if variation_payload else None,
            "variation_name": variation_payload["name"] if variation_payload else None,
            "variation_slug": variation_payload["slug"] if variation_payload else None,
            "physical_form": physical_form_payload,
            "functions": function_names,
            "applications": application_names,
            "default_unit": gi.default_unit,
            "density": gi.density,
            "capacity": gi.capacity,
            "capacity_unit": gi.capacity_unit,
            "container_material": getattr(gi, "container_material", None),
            "container_type": getattr(gi, "container_type", None),
            "container_style": getattr(gi, "container_style", None),
            "container_color": getattr(gi, "container_color", None),
            "aliases": gi.aliases,
            "default_is_perishable": gi.default_is_perishable,
            "recommended_shelf_life_days": gi.recommended_shelf_life_days,
            "recommended_fragrance_load_pct": gi.recommended_fragrance_load_pct,
            "inci_name": gi.inci_name,
            "cas_number": getattr(gi, "cas_number", None),
            "protein_content_pct": gi.protein_content_pct,
            "brewing_color_srm": gi.brewing_color_srm,
            "brewing_potential_sg": gi.brewing_potential_sg,
            "brewing_diastatic_power_lintner": gi.brewing_diastatic_power_lintner,
            "certifications": gi.certifications or [],
            "ingredient_category_id": gi.ingredient_category_id,
            "ingredient_category_name": ingredient_category_name,
            "ingredient_name": (
                ingredient_payload["name"] if ingredient_payload else None
            ),
            "physical_form_name": (
                physical_form_payload["name"] if physical_form_payload else None
            ),
            "saponification_value": getattr(gi, "saponification_value", None),
            "iodine_value": getattr(gi, "iodine_value", None),
            "fatty_acid_profile": getattr(gi, "fatty_acid_profile", None),
            "melting_point_c": getattr(gi, "melting_point_c", None),
            "flash_point_c": getattr(gi, "flash_point_c", None),
            "moisture_content_percent": getattr(gi, "moisture_content_percent", None),
            "comedogenic_rating": getattr(gi, "comedogenic_rating", None),
            "ph_value": getattr(gi, "ph_value", None),
        }
        results.append(item_payload)

        if group_mode:
            group_key = (
                ingredient_payload["id"] if ingredient_payload else f"item-{gi.id}"
            )
            group_entry = grouped.get(group_key)
            if not group_entry:
                group_entry = {
                    "id": ingredient_payload["id"] if ingredient_payload else gi.id,
                    "ingredient_id": (
                        ingredient_payload["id"] if ingredient_payload else None
                    ),
                    "name": (
                        ingredient_payload["name"]
                        if ingredient_payload
                        else display_name
                    ),
                    "text": (
                        ingredient_payload["name"]
                        if ingredient_payload
                        else display_name
                    ),
                    "display_name": (
                        ingredient_payload["name"]
                        if ingredient_payload
                        else display_name
                    ),
                    "item_type": gi.item_type,
                    "ingredient": ingredient_payload,
                    "ingredient_category_id": (
                        ingredient_payload["ingredient_category_id"]
                        if ingredient_payload
                        else gi.ingredient_category_id
                    ),
                    "ingredient_category_name": (
                        ingredient_payload["ingredient_category_name"]
                        if ingredient_payload
                        else ingredient_category_name
                    ),
                    "forms": [],
                }
                grouped[group_key] = group_entry

            group_entry["forms"].append(
                {
                    "id": gi.id,
                    "name": display_name,
                    "text": display_name,
                    "display_name": display_name,
                    "raw_name": gi.name,
                    "item_type": gi.item_type,
                    "ingredient_id": (
                        ingredient_payload["id"] if ingredient_payload else None
                    ),
                    "ingredient_name": (
                        ingredient_payload["name"] if ingredient_payload else None
                    ),
                    "variation": variation_payload,
                    "variation_id": (
                        variation_payload["id"] if variation_payload else None
                    ),
                    "variation_name": (
                        variation_payload["name"] if variation_payload else None
                    ),
                    "variation_slug": (
                        variation_payload["slug"] if variation_payload else None
                    ),
                    "physical_form": physical_form_payload,
                    "physical_form_name": (
                        physical_form_payload["name"] if physical_form_payload else None
                    ),
                    "default_unit": gi.default_unit,
                    "density": gi.density,
                    "default_is_perishable": gi.default_is_perishable,
                    "recommended_shelf_life_days": gi.recommended_shelf_life_days,
                    "recommended_fragrance_load_pct": gi.recommended_fragrance_load_pct,
                    "aliases": gi.aliases or [],
                    "certifications": gi.certifications or [],
                    "functions": function_names,
                    "applications": application_names,
                    "inci_name": gi.inci_name,
                    "cas_number": getattr(gi, "cas_number", None),
                    "protein_content_pct": gi.protein_content_pct,
                    "brewing_color_srm": gi.brewing_color_srm,
                    "brewing_potential_sg": gi.brewing_potential_sg,
                    "brewing_diastatic_power_lintner": gi.brewing_diastatic_power_lintner,
                    "ingredient_category_id": gi.ingredient_category_id,
                    "ingredient_category_name": ingredient_category_name,
                    "saponification_value": getattr(gi, "saponification_value", None),
                    "iodine_value": getattr(gi, "iodine_value", None),
                    "fatty_acid_profile": getattr(gi, "fatty_acid_profile", None),
                    "melting_point_c": getattr(gi, "melting_point_c", None),
                    "flash_point_c": getattr(gi, "flash_point_c", None),
                    "moisture_content_percent": getattr(
                        gi, "moisture_content_percent", None
                    ),
                    "comedogenic_rating": getattr(gi, "comedogenic_rating", None),
                    "ph_value": getattr(gi, "ph_value", None),
                }
            )

    if group_mode:
        payload = {"results": list(grouped.values())}
    else:
        payload = {"results": results}

    if cache_key:
        try:
            cache.set(cache_key, payload, timeout=_global_library_cache_timeout())
        except Exception:
            current_app.logger.debug(
                "Unable to write authenticated global item cache key %s", cache_key
            )

    return jsonify(payload)


@ingredient_api_bp.route("/global-items/<int:global_item_id>/stats", methods=["GET"])
@login_required
@require_permission("inventory.view")
def get_global_item_stats(global_item_id):
    try:
        rollup = GlobalItemStatsService.get_rollup(global_item_id)
        return jsonify({"success": True, "stats": rollup})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
