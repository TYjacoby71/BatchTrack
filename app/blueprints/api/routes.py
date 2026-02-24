"""API routes for client bootstrap and batchbot features.

Synopsis:
Provides JSON endpoints for dashboard widgets, bootstrap payloads, and recipe prefix generation.

Glossary:
- Bootstrap: Lightweight payload for client selection lists.
- Dashboard alerts: Aggregated warning or status indicators.
- Recipe prefix: Unique label prefix derived from a recipe name.
"""

import logging
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request, session, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import load_only

from app import db  # Assuming db is imported from app
from app.extensions import cache
from app.models import InventoryItem  # Added for get_ingredients endpoint
from app.models import (
    Product,
    Recipe,
)
from app.models.product import ProductSKU
from app.services.ai import GoogleAIClientError
from app.services.batchbot_credit_service import BatchBotCreditService
from app.services.batchbot_service import BatchBotService, BatchBotServiceError
from app.services.batchbot_usage_service import (
    BatchBotChatLimitError,
    BatchBotLimitError,
    BatchBotUsageService,
)
from app.services.cache_invalidation import (
    ingredient_list_cache_key,
    product_bootstrap_cache_key,
    recipe_bootstrap_cache_key,
)
from app.utils.cache_utils import should_bypass_cache
from app.utils.code_generator import generate_recipe_prefix
from app.utils.permissions import require_permission

# Configure logging
logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__, url_prefix="/api")


# --- Batchbot flag ---
# Purpose: Check if BatchBot features are enabled in config.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
def _is_batchbot_enabled() -> bool:
    return bool(current_app.config.get("FEATURE_BATCHBOT", False))


# --- Resolve org scope ---
# Purpose: Determine the request organization scope (supports developer masquerade).
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
def _resolve_org_id():
    """
    Determine the organization scope for the current request, respecting developer masquerade.
    """
    org_id = getattr(current_user, "organization_id", None)
    if getattr(current_user, "user_type", None) == "developer":
        dev_selected = session.get("dev_selected_org_id")
        if dev_selected:
            org_id = dev_selected
    return org_id


# =========================================================
# HEALTH & TIME
# =========================================================
# --- Health check ---
# Purpose: Return API health status for monitoring.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@api_bp.route("/", methods=["GET", "HEAD"])
def health_check():
    """Health check endpoint for monitoring services"""
    if request.method == "HEAD":
        return "", 200
    return jsonify(
        {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
    )


# --- Server time ---
# Purpose: Return server time in user's timezone.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@api_bp.route("/server-time")
@login_required
@require_permission("dashboard.view")
def server_time():
    """Get current server time in user's timezone"""
    from ...utils.timezone_utils import TimezoneUtils

    # Get current time in user's timezone
    user_time = TimezoneUtils.now()

    return jsonify(
        {
            "current_time": user_time.isoformat(),
            "timestamp": user_time.isoformat(),
            "timezone": str(TimezoneUtils.get_user_timezone()),
        }
    )


# =========================================================
# RECIPES
# =========================================================
# --- Recipe label prefix ---
# Purpose: Generate a unique label prefix for a recipe name.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@api_bp.route("/recipes/prefix", methods=["GET"])
@login_required
@require_permission("recipes.create")
def recipe_prefix():
    name = (request.args.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Recipe name is required"}), 400
    org_id = _resolve_org_id()
    prefix = generate_recipe_prefix(name, org_id)
    return jsonify({"prefix": prefix})


# =========================================================
# ALERTS
# =========================================================
# --- Dismiss alert ---
# Purpose: Dismiss a dashboard alert for the session.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@api_bp.route("/dismiss-alert", methods=["POST"])
@login_required
@require_permission("alerts.dismiss")
def dismiss_alert():
    """Dismiss an alert for the current session"""
    from flask import request

    data = request.get_json()
    alert_type = data.get("alert_type")

    if not alert_type:
        return jsonify({"error": "Alert type required"}), 400

    # Initialize dismissed alerts in session if not exists
    if "dismissed_alerts" not in session:
        session["dismissed_alerts"] = []

    # Add to dismissed alerts if not already there
    if alert_type not in session["dismissed_alerts"]:
        session["dismissed_alerts"].append(alert_type)
        session.permanent = True  # Make session persistent

    return jsonify({"success": True})


# --- Dashboard alerts ---
# Purpose: Fetch dashboard alerts for the organization.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@api_bp.route("/dashboard-alerts")
@login_required
@require_permission("alerts.view")
def get_dashboard_alerts():
    """Get dashboard alerts for current user's organization"""
    try:
        import logging

        from flask import session

        from ...services.dashboard_alerts import DashboardAlertService

        # Get dismissed alerts from session
        dismissed_alerts = session.get("dismissed_alerts", [])

        # Get alerts from service
        alert_data = DashboardAlertService.get_dashboard_alerts(
            dismissed_alerts=dismissed_alerts
        )

        # Log for debugging
        logging.info(
            f"Dashboard alerts requested - found {len(alert_data.get('alerts', []))} alerts"
        )

        return jsonify(
            {
                "success": True,
                "alerts": alert_data["alerts"],
                "total_alerts": alert_data["total_alerts"],
                "hidden_count": alert_data["hidden_count"],
            }
        )

    except Exception as e:
        logging.error(f"Error getting dashboard alerts: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# Stock checking is now handled by the dedicated stock_routes.py blueprint
# All stock check requests should use /api/check-stock endpoint

# Import sub-blueprints to register their routes

from app.models.product_category import ProductCategory
from app.models.unit import Unit

from ...utils.unit_utils import get_global_unit_list
from .container_routes import container_api_bp
from .ingredient_routes import ingredient_api_bp
from .reservation_routes import reservation_api_bp

# Register sub-blueprints

api_bp.register_blueprint(ingredient_api_bp, url_prefix="/ingredients")
api_bp.register_blueprint(container_api_bp)
api_bp.register_blueprint(reservation_api_bp)


# =========================================================
# INVENTORY & PRODUCTS
# =========================================================
# --- Inventory item ---
# Purpose: Return inventory item details for editing.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@api_bp.route("/inventory/item/<int:item_id>", methods=["GET"])
@login_required
@require_permission("inventory.view")
def get_inventory_item(item_id):
    """Get inventory item details for editing"""
    from ...models import InventoryItem

    item = InventoryItem.query.filter_by(
        id=item_id, organization_id=current_user.organization_id
    ).first_or_404()

    return jsonify(
        {
            "id": item.id,
            "name": item.name,
            "quantity": item.quantity,
            "unit": item.unit,
            "type": item.type,
            "cost_per_unit": item.cost_per_unit,
            "notes": getattr(item, "notes", None),
            "density": item.density,
            "category_id": item.category_id,
            "global_item_id": item.global_item_id,
            "is_perishable": item.is_perishable,
            "shelf_life_days": item.shelf_life_days,
            "capacity": getattr(item, "capacity", None),
            "capacity_unit": getattr(item, "capacity_unit", None),
        }
    )


# --- Product category ---
# Purpose: Return product category details by id.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@api_bp.route("/categories/<int:cat_id>", methods=["GET"])
@login_required
@require_permission("products.view")
def get_category(cat_id):
    c = ProductCategory.query.get_or_404(cat_id)
    return jsonify(
        {
            "id": c.id,
            "name": c.name,
            "is_typically_portioned": bool(c.is_typically_portioned),
        }
    )


# =========================================================
# UNITS
# =========================================================
# --- Unit search ---
# Purpose: Search units for selection lists.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@api_bp.route("/unit-search", methods=["GET"])
@login_required
@require_permission("inventory.view")
def list_units():
    """Unified unit search using get_global_unit_list (standard + org custom)."""
    unit_type = (
        request.args.get("type") or request.args.get("unit_type") or ""
    ).strip()
    q = (request.args.get("q") or "").strip()
    try:
        units = get_global_unit_list() or []
    except Exception:
        units = []

    if unit_type:
        units = [u for u in units if getattr(u, "unit_type", None) == unit_type]
    if q:
        q_lower = q.lower()
        units = [
            u
            for u in units
            if (getattr(u, "name", "") or "").lower().find(q_lower) != -1
        ]

    try:
        units.sort(
            key=lambda u: (
                str(getattr(u, "unit_type", "") or ""),
                str(getattr(u, "name", "") or ""),
            )
        )
    except Exception:
        pass

    results = units[:50]
    return jsonify(
        {
            "success": True,
            "data": [
                {
                    "id": getattr(u, "id", None),
                    "name": getattr(u, "name", ""),
                    "unit_type": getattr(u, "unit_type", None),
                    "symbol": getattr(u, "symbol", None),
                    "is_custom": getattr(u, "is_custom", False),
                }
                for u in results
            ],
        }
    )


# --- Create unit ---
# Purpose: Create a new unit for inventory usage.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@api_bp.route("/units", methods=["POST"])
@login_required
@require_permission("inventory.edit")
def create_unit():
    try:
        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        unit_type = (data.get("unit_type") or "count").strip()
        if not name:
            return jsonify({"success": False, "error": "Name is required"}), 400
        # Prevent duplicates within standard scope
        existing = Unit.query.filter(Unit.name.ilike(name)).first()
        if existing:
            return jsonify(
                {
                    "success": True,
                    "data": {
                        "id": existing.id,
                        "name": existing.name,
                        "unit_type": existing.unit_type,
                    },
                }
            )
        u = Unit(
            name=name,
            unit_type=unit_type,
            conversion_factor=1.0,
            base_unit="Piece",
            is_active=True,
            is_custom=False,
            is_mapped=True,
            organization_id=None,
        )
        db.session.add(u)
        db.session.commit()
        return jsonify(
            {
                "success": True,
                "data": {"id": u.id, "name": u.name, "unit_type": u.unit_type},
            }
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


# =========================================================
# CONTAINERS
# =========================================================
# --- Container suggestions ---
# Purpose: Return curated container field suggestions.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@api_bp.route("/containers/suggestions", methods=["GET"])
@login_required
@require_permission("inventory.view")
def get_container_suggestions():
    """Return container field suggestions from curated master lists.

    Query params:
      - field: one of material|type|style|color (optional; default returns all)
      - q: optional search prefix to filter suggestions
      - limit: max suggestions per field (default 20)
    """
    try:
        field = (request.args.get("field") or "").strip().lower()
        q = (request.args.get("q") or "").strip().lower()
        limit = max(1, min(int(request.args.get("limit", 20)), 100))

        # Load master lists from settings - single source of truth
        from app.services.developer.reference_data_service import ReferenceDataService

        curated_lists = ReferenceDataService.load_curated_container_lists()

        def filter_list(items):
            if q:
                filtered = [item for item in items if q.lower() in item.lower()]
            else:
                filtered = items[:]
            return filtered[:limit]

        if field in ["material", "type", "style", "color"]:
            field_key = field + "s" if field != "material" else "materials"
            suggestions = filter_list(curated_lists.get(field_key, []))
            return jsonify(
                {"success": True, "field": field, "suggestions": suggestions}
            )

        # Return all fields
        payload = {
            "material": filter_list(curated_lists["materials"]),
            "type": filter_list(curated_lists["types"]),
            "style": filter_list(curated_lists["styles"]),
            "color": filter_list(curated_lists["colors"]),
        }
        return jsonify({"success": True, "suggestions": payload})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =========================================================
# TIMEZONE
# =========================================================
# --- Timezone info ---
# Purpose: Return server timezone metadata.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@api_bp.route("/timezone", methods=["GET"])
@login_required
@require_permission("settings.view")
def get_timezone():
    """Get server timezone info"""
    from datetime import datetime

    import pytz

    server_tz = current_app.config.get("TIMEZONE", "UTC")
    now_utc = datetime.now(timezone.utc)

    return jsonify(
        {
            "server_timezone": server_tz,
            "utc_time": now_utc.isoformat(),
            "available_timezones": pytz.all_timezones_set,
        }
    )


# =========================================================
# INGREDIENTS
# =========================================================
# --- Ingredient list ---
# Purpose: Return ingredient list for unit conversion.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@api_bp.route("/ingredients", methods=["GET"])
@login_required
@require_permission("inventory.view")
def get_ingredients():
    """Get user's ingredients for unit converter"""
    try:
        org_id = getattr(current_user, "organization_id", None) or 0
        cache_key = ingredient_list_cache_key(org_id)
        bypass_cache = should_bypass_cache()

        if bypass_cache:
            cache.delete(cache_key)
        else:
            cached = cache.get(cache_key)
            if cached is not None:
                return jsonify(cached)

        query = InventoryItem.query.filter_by(type="ingredient")
        if current_user.organization_id:
            query = query.filter_by(organization_id=current_user.organization_id)

        ingredients = query.order_by(InventoryItem.name).all()
        payload = [
            {
                "id": ing.id,
                "name": ing.name,
                "density": ing.density,
                "type": ing.type,
                "unit": ing.unit,
            }
            for ing in ingredients
        ]

        cache.set(
            cache_key,
            payload,
            timeout=current_app.config.get("INGREDIENT_LIST_CACHE_TTL", 120),
        )
        return jsonify(payload)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================================================
# BOOTSTRAP
# =========================================================
# --- Recipe bootstrap ---
# Purpose: Return current master recipes + current variations.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@api_bp.route("/bootstrap/recipes", methods=["GET"])
@login_required
@require_permission("recipes.view")
def bootstrap_recipes():
    """Lightweight recipe bootstrap payload for clients that only need IDs + variants."""
    org_id = _resolve_org_id()
    if not org_id:
        return jsonify({"recipes": [], "count": 0})

    cache_key = recipe_bootstrap_cache_key(org_id)
    bypass_cache = should_bypass_cache()
    cache_ttl = current_app.config.get("RECIPE_BOOTSTRAP_CACHE_TTL", 300)

    if not bypass_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return jsonify(
                {"recipes": cached, "count": len(cached), "cache": "hit", "version": 1}
            )

    masters = (
        Recipe.query.options(
            load_only(
                Recipe.id,
                Recipe.name,
                Recipe.label_prefix,
                Recipe.status,
                Recipe.recipe_group_id,
            ),
        )
        .filter(
            Recipe.organization_id == org_id,
            Recipe.is_master.is_(True),
            Recipe.test_sequence.is_(None),
            Recipe.status == "published",
            Recipe.is_archived.is_(False),
            Recipe.is_current.is_(True),
        )
        .order_by(Recipe.name.asc())
    )

    variations_query = Recipe.query.options(
        load_only(
            Recipe.id,
            Recipe.name,
            Recipe.label_prefix,
            Recipe.status,
            Recipe.recipe_group_id,
            Recipe.parent_recipe_id,
        ),
    ).filter(
        Recipe.organization_id == org_id,
        Recipe.is_master.is_(False),
        Recipe.test_sequence.is_(None),
        Recipe.status == "published",
        Recipe.is_archived.is_(False),
        Recipe.is_current.is_(True),
    )

    variations_by_group = {}
    variations_by_parent = {}
    for variation in variations_query.all():
        payload = {
            "id": variation.id,
            "name": variation.name,
            "status": getattr(variation, "status", None),
            "label_prefix": getattr(variation, "label_prefix", None),
        }
        if variation.recipe_group_id:
            variations_by_group.setdefault(variation.recipe_group_id, []).append(
                payload
            )
        elif variation.parent_recipe_id:
            variations_by_parent.setdefault(variation.parent_recipe_id, []).append(
                payload
            )

    recipes = []
    for recipe in masters.all():
        variations = []
        if recipe.recipe_group_id:
            variations = variations_by_group.get(recipe.recipe_group_id, [])
        elif recipe.id in variations_by_parent:
            variations = variations_by_parent.get(recipe.id, [])
        variations = sorted(
            variations, key=lambda item: (item.get("name") or "").lower()
        )
        recipes.append(
            {
                "id": recipe.id,
                "name": recipe.name,
                "label_prefix": getattr(recipe, "label_prefix", None),
                "status": getattr(recipe, "status", None),
                "variations": variations,
            }
        )

    cache.set(cache_key, recipes, timeout=cache_ttl)
    return jsonify(
        {"recipes": recipes, "count": len(recipes), "cache": "miss", "version": 1}
    )


# --- Product bootstrap ---
# Purpose: Return product list + SKU inventory ids.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@api_bp.route("/bootstrap/products", methods=["GET"])
@login_required
@require_permission("products.view")
def bootstrap_products():
    """Return product + SKU inventory identifiers for fast client bootstrapping."""
    org_id = _resolve_org_id()
    if not org_id:
        return jsonify({"products": [], "sku_inventory_ids": []})

    cache_key = product_bootstrap_cache_key(org_id)
    bypass_cache = should_bypass_cache()
    cache_ttl = current_app.config.get("PRODUCT_BOOTSTRAP_CACHE_TTL", 300)

    if not bypass_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return jsonify({**cached, "cache": "hit", "version": 1})

    products = (
        Product.query.options(load_only(Product.id, Product.name))
        .filter(
            Product.organization_id == org_id,
            Product.is_active.is_(True),
            Product.is_discontinued.is_(False),
        )
        .order_by(Product.name.asc())
        .all()
    )

    sku_rows = (
        ProductSKU.query.options(load_only(ProductSKU.inventory_item_id))
        .filter(
            ProductSKU.organization_id == org_id,
            ProductSKU.is_active.is_(True),
        )
        .all()
    )

    payload = {
        "products": [{"id": product.id, "name": product.name} for product in products],
        "sku_inventory_ids": [
            row.inventory_item_id
            for row in sku_rows
            if getattr(row, "inventory_item_id", None)
        ],
    }

    cache.set(cache_key, payload, timeout=cache_ttl)
    return jsonify({**payload, "cache": "miss", "version": 1})


# =========================================================
# UNIT CONVERSION
# =========================================================
# --- Unit converter ---
# Purpose: Convert between inventory units.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@api_bp.route("/unit-converter", methods=["POST"])
@login_required
@require_permission("inventory.view")
def unit_converter():
    """Unit conversion endpoint for the modal."""
    try:
        data = request.get_json() or {}
        from_amount = float(data.get("from_amount", 0))
        from_unit = data.get("from_unit", "")
        to_unit = data.get("to_unit", "")
        ingredient_id = data.get("ingredient_id")

        if not all([from_amount, from_unit, to_unit]):
            return jsonify({"success": False, "error": "Missing required parameters"})

        # Get ingredient for density if needed
        ingredient = None
        if ingredient_id:
            ingredient = db.session.get(InventoryItem, ingredient_id)

        # Perform conversion using unit conversion engine
        from app.services.unit_conversion import ConversionEngine

        result = ConversionEngine.convert_units(
            from_amount,
            from_unit,
            to_unit,
            ingredient_id=ingredient_id,
            density=ingredient.density if ingredient else None,
        )

        if result.get("success"):
            return jsonify(
                {
                    "success": True,
                    "result": result.get("converted_value"),
                    "from_amount": from_amount,
                    "from_unit": from_unit,
                    "to_unit": to_unit,
                    "conversion_type": result.get("conversion_type"),
                    "requires_attention": result.get("requires_attention", False),
                }
            )
        else:
            error_data = result.get("error_data") or {}
            return jsonify(
                {
                    "success": False,
                    "error": error_data.get("message")
                    or result.get("error_code")
                    or "Conversion failed",
                    "error_code": result.get("error_code"),
                    "drawer_payload": result.get("drawer_payload"),
                    "requires_drawer": result.get("requires_drawer", False),
                }
            )

    except Exception as e:
        current_app.logger.error(f"Unit converter API error: {str(e)}")
        return jsonify({"success": False, "error": str(e)})


# =========================================================
# BATCHBOT
# =========================================================
# --- BatchBot chat ---
# Purpose: Chat with BatchBot for recipe assistance.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@api_bp.route("/batchbot/chat", methods=["POST"])
@login_required
@require_permission("ai.batchbot")
def batchbot_chat():
    if not _is_batchbot_enabled():
        return (
            jsonify(
                {"success": False, "error": "BatchBot is disabled for this deployment."}
            ),
            404,
        )
    data = request.get_json() or {}
    prompt = (data.get("prompt") or "").strip()
    history = data.get("history") or []
    metadata = data.get("metadata") or {}

    if not prompt:
        return jsonify({"success": False, "error": "Prompt is required."}), 400

    try:
        service = BatchBotService(current_user)
        response = service.chat(prompt=prompt, history=history, metadata=metadata)
        return jsonify(
            {
                "success": True,
                "message": response.text,
                "tool_results": response.tool_results,
                "usage": response.usage,
                "quota": _serialize_quota(response.quota, response.credits),
            }
        )
    except BatchBotLimitError as exc:
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(exc),
                    "limit": {
                        "allowed": exc.allowed,
                        "used": exc.used,
                        "window_end": exc.window_end.isoformat(),
                    },
                    "refill_checkout_url": _generate_refill_checkout_url(),
                }
            ),
            429,
        )
    except BatchBotChatLimitError as exc:
        return (
            jsonify(
                {
                    "success": False,
                    "error": str(exc),
                    "chat_limit": {
                        "allowed": exc.limit,
                        "used": exc.used,
                        "window_end": exc.window_end.isoformat(),
                    },
                    "refill_checkout_url": _generate_refill_checkout_url(),
                }
            ),
            429,
        )
    except BatchBotServiceError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except GoogleAIClientError as exc:
        current_app.logger.exception("BatchBot AI failure")
        return jsonify({"success": False, "error": str(exc)}), 502
    except Exception:
        current_app.logger.exception("Unexpected BatchBot failure")
        return jsonify({"success": False, "error": "Unexpected BatchBot failure."}), 500


# --- BatchBot usage ---
# Purpose: Return BatchBot usage and quota snapshot.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@api_bp.route("/batchbot/usage", methods=["GET"])
@login_required
@require_permission("ai.batchbot")
def batchbot_usage():
    if not _is_batchbot_enabled():
        return (
            jsonify(
                {"success": False, "error": "BatchBot is disabled for this deployment."}
            ),
            404,
        )
    org = getattr(current_user, "organization", None)
    if not org:
        return jsonify({"success": False, "error": "Organization is required."}), 400

    snapshot = BatchBotUsageService.get_usage_snapshot(org)
    credit_snapshot = BatchBotCreditService.snapshot(org)
    return jsonify(
        {"success": True, "quota": _serialize_quota(snapshot, credit_snapshot)}
    )


# ---  Serialize Quota ---
# Purpose: Implement `_serialize_quota` behavior for this module.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
def _serialize_quota(snapshot, credits=None):
    return {
        "allowed": snapshot.allowed,
        "used": snapshot.used,
        "remaining": snapshot.remaining,
        "window_start": snapshot.window_start.isoformat(),
        "window_end": snapshot.window_end.isoformat(),
        "chat_limit": snapshot.chat_limit,
        "chat_used": snapshot.chat_used,
        "chat_remaining": snapshot.chat_remaining,
        "credits": (
            {
                "total": getattr(credits, "total", None),
                "remaining": getattr(credits, "remaining", None),
                "next_expiration": (
                    getattr(credits, "expires_next", None).isoformat()
                    if getattr(credits, "expires_next", None)
                    else None
                ),
            }
            if credits
            else None
        ),
    }


# ---  Generate Refill Checkout Url ---
# Purpose: Implement `_generate_refill_checkout_url` behavior for this module.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
def _generate_refill_checkout_url():
    try:
        lookup_key = current_app.config.get("BATCHBOT_REFILL_LOOKUP_KEY")
        if not lookup_key:
            return None
        if not current_user or not getattr(current_user, "email", None):
            return None
        from app.services.billing_service import BillingService

        success_url = (
            url_for("app_routes.dashboard", _external=True) + "?refill=success"
        )
        cancel_url = url_for("app_routes.dashboard", _external=True) + "?refill=cancel"
        metadata = {
            "organization_id": str(current_user.organization_id or ""),
            "user_id": str(current_user.id),
            "batchbot_refill_lookup_key": lookup_key,
        }
        session = BillingService.create_one_time_checkout_by_lookup_key(
            lookup_key=lookup_key,
            customer_email=current_user.email,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
        )
        return getattr(session, "url", None)
    except Exception as exc:
        current_app.logger.warning(
            "Unable to generate BatchBot refill checkout: %s", exc
        )
        return None
