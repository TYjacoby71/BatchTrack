"""Ingredient API routes for inventory and global-library workflows.

Synopsis:
Expose authenticated endpoints for ingredient category retrieval, inventory
typeahead search, global-library lookup/grouping, and create-or-link helpers
used by inventory and recipe planning surfaces.

Glossary:
- Global library: Canonical global item catalog used for linking org inventory.
- Definition search: Ingredient-definition lookup for curated global items.
- Group mode: Ingredient-centric payload mode that nests forms per ingredient.
"""

import logging

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from app.utils.permissions import require_permission

from ...extensions import cache, limiter
from ...services.cache_invalidation import global_library_cache_key
from ...services.density_assignment_service import DensityAssignmentService
from ...services.ingredient_route_service import IngredientRouteService
from ...services.statistics.global_item_stats import GlobalItemStatsService
from ...utils.cache_utils import stable_cache_key

logger = logging.getLogger(__name__)


# --- Ingredient API blueprint ---
# Purpose: Group authenticated ingredient and global-item API endpoints.
# Inputs: None.
# Outputs: Blueprint namespace for ingredient route registration.
ingredient_api_bp = Blueprint("ingredient_api", __name__)


# --- Resolve global library cache timeout ---
# Purpose: Provide cache timeout fallback for global-library responses.
# Inputs: Flask app config.
# Outputs: Timeout integer for cache writes.
def _global_library_cache_timeout() -> int:
    return current_app.config.get(
        "GLOBAL_LIBRARY_CACHE_TIMEOUT",
        current_app.config.get("CACHE_DEFAULT_TIMEOUT", 120),
    )


# --- List ingredient categories ---
# Purpose: Return active global ingredient categories for selection UIs.
# Inputs: Authenticated request context.
# Outputs: JSON list of category id/name/default density.
@ingredient_api_bp.route("/categories", methods=["GET"])
@login_required
@require_permission("inventory.view")
def get_categories():
    """Return ingredient categories: global categories plus user's custom ones."""
    return jsonify(IngredientRouteService.list_global_ingredient_categories())


# --- List global-library density options ---
# Purpose: Return density options derived from global-library metadata.
# Inputs: Optional include_uncategorized query flag.
# Outputs: JSON payload from density assignment service.
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


# --- Get ingredient density ---
# Purpose: Resolve effective density for an inventory ingredient item.
# Inputs: Inventory item id path parameter.
# Outputs: JSON density value from item/category/default fallback.
@ingredient_api_bp.route("/ingredient/<int:id>/density", methods=["GET"])
@login_required
@require_permission("inventory.view")
def get_ingredient_density(id):
    ingredient = IngredientRouteService.get_inventory_item_or_404(inventory_item_id=id)
    if ingredient.density:
        return jsonify({"density": ingredient.density})
    elif ingredient.category:
        return jsonify({"density": ingredient.category.default_density})
    return jsonify({"density": 1.0})


# --- Search inventory ingredients ---
# Purpose: Return scoped ingredient inventory suggestions for typeahead UX.
# Inputs: Query string parameter q.
# Outputs: JSON list of matched inventory ingredient payloads.
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

    return jsonify(
        IngredientRouteService.search_inventory_ingredients(
            query_text=q,
            organization_id=getattr(current_user, "organization_id", None),
            limit=20,
        )
    )


# --- Search ingredient definitions ---
# Purpose: Return curated ingredient-definition matches for global item forms.
# Inputs: Query string parameter q.
# Outputs: JSON list of ingredient definition metadata.
@ingredient_api_bp.route("/ingredients/definitions/search", methods=["GET"])
@login_required
@limiter.limit("3000/minute")
@require_permission("inventory.view")
def search_ingredient_definitions():
    """Search ingredient definitions for the create global item form."""
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"results": []})

    return jsonify(
        IngredientRouteService.search_ingredient_definitions(query_text=q, limit=20)
    )


# --- List forms for ingredient definition ---
# Purpose: Return global items/forms linked to one ingredient definition.
# Inputs: Ingredient definition id path parameter.
# Outputs: JSON payload with ingredient metadata and linked item forms.
@ingredient_api_bp.route(
    "/ingredients/definitions/<int:ingredient_id>/forms", methods=["GET"]
)
@login_required
@limiter.limit("3000/minute")
@require_permission("inventory.view")
def list_forms_for_ingredient_definition(ingredient_id: int):
    """Return the existing global items tied to a specific ingredient definition."""
    return jsonify(
        IngredientRouteService.list_forms_for_ingredient_definition(
            ingredient_id=ingredient_id
        )
    )


# --- Search physical forms ---
# Purpose: Return active physical-form suggestions for typeahead controls.
# Inputs: Optional query string parameter q.
# Outputs: JSON list of physical-form metadata payloads.
@ingredient_api_bp.route("/physical-forms/search", methods=["GET"])
@login_required
@limiter.limit("3000/minute")
@require_permission("inventory.view")
def search_physical_forms():
    """Search physical forms with lightweight typeahead payloads."""
    q = (request.args.get("q") or "").strip()
    return jsonify(
        IngredientRouteService.search_physical_forms(query_text=q, limit=30)
    )


# --- Search variations ---
# Purpose: Return active variation suggestions with physical-form metadata.
# Inputs: Optional query string parameter q.
# Outputs: JSON list of variation payloads.
@ingredient_api_bp.route("/variations/search", methods=["GET"])
@login_required
@limiter.limit("3000/minute")
@require_permission("inventory.view")
def search_variations():
    """Search curated variations with physical form metadata."""
    q = (request.args.get("q") or "").strip()
    return jsonify(IngredientRouteService.search_variations(query_text=q, limit=30))


# --- Create or link ingredient inventory item ---
# Purpose: Create organization inventory items and optionally link global items.
# Inputs: JSON payload with name/type/unit and optional global item id.
# Outputs: JSON success payload with existing/created inventory item details.
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
        payload, status_code = IngredientRouteService.create_or_link_inventory_item(
            data=data,
            organization_id=getattr(current_user, "organization_id", None),
            actor_user_id=getattr(current_user, "id", None),
        )
        return jsonify(payload), status_code
    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/api/ingredient_routes.py:496",
            exc_info=True,
        )
        IngredientRouteService.rollback_session()
        return jsonify({"success": False, "error": str(e)}), 500


# --- Search global items ---
# Purpose: Return global-library item search results for authenticated users.
# Inputs: Query string q plus optional type/group flags.
# Outputs: JSON list (or grouped list) of global-item payloads.
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

    payload = IngredientRouteService.search_global_items_payload(
        query_text=q,
        item_type=item_type,
        group_by_ingredient=request.args.get("group") == "ingredient",
        limit=20,
    )

    if cache_key:
        try:
            cache.set(cache_key, payload, timeout=_global_library_cache_timeout())
        except Exception:
            current_app.logger.debug(
                "Unable to write authenticated global item cache key %s", cache_key
            )

    return jsonify(payload)


# --- Get global item stats ---
# Purpose: Return rollup statistics for one global item.
# Inputs: Global item id path parameter.
# Outputs: JSON success payload with global item rollup stats.
@ingredient_api_bp.route("/global-items/<int:global_item_id>/stats", methods=["GET"])
@login_required
@require_permission("inventory.view")
def get_global_item_stats(global_item_id):
    try:
        rollup = GlobalItemStatsService.get_rollup(global_item_id)
        return jsonify({"success": True, "stats": rollup})
    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/api/ingredient_routes.py:811",
            exc_info=True,
        )
        return jsonify({"success": False, "error": str(e)}), 500
