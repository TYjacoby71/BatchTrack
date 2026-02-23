"""Public API routes for unauthenticated tool and utility endpoints.

Synopsis:
Provide rate-limited public endpoints for server time, bot-trap handling,
global-library search, soapcalc lookup, unit conversion, and help-bot access.

Glossary:
- Public API blueprint: Route namespace containing unauthenticated API handlers.
- Bot trap: Endpoint that records and blocks suspicious automation traffic.
- Group mode: Ingredient-centric payload mode for grouped global-item results.
"""

from collections import OrderedDict
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, make_response, request
from flask_login import current_user
from sqlalchemy import func, or_

from app.extensions import cache, csrf, limiter
from app.models.global_item import GlobalItem
from app.models.models import Unit
from app.services.ai import GoogleAIClientError
from app.services.cache_invalidation import global_library_cache_key
from app.services.public_bot_service import PublicBotService, PublicBotServiceError
from app.services.public_bot_trap_service import PublicBotTrapService
from app.services.soapcalc_oils_service import (
    search_soapcalc_items,
    search_soapcalc_oils,
)
from app.services.unit_conversion.unit_conversion import ConversionEngine
from app.utils.cache_utils import stable_cache_key

# --- Public API blueprint ---
# Purpose: Group unauthenticated API routes used by public tools/pages.
# Inputs: None.
# Outputs: Blueprint namespace for public endpoints.
public_api_bp = Blueprint("public_api", __name__)


# --- Resolve global library cache timeout ---
# Purpose: Provide cache timeout fallback for public global-library responses.
# Inputs: Flask app config.
# Outputs: Timeout integer for cache writes.
def _global_library_cache_timeout() -> int:
    return current_app.config.get(
        "GLOBAL_LIBRARY_CACHE_TIMEOUT",
        current_app.config.get("CACHE_DEFAULT_TIMEOUT", 120),
    )


# --- Return server time ---
# Purpose: Expose current UTC server time for client synchronization checks.
# Inputs: None.
# Outputs: JSON response with ISO8601 UTC timestamp.
@public_api_bp.route("/server-time", methods=["GET"])
@limiter.exempt
def server_time():
    ts = datetime.now(timezone.utc).isoformat()
    resp = make_response(jsonify({"server_time": ts}))
    resp.headers["Cache-Control"] = "no-store"
    return resp


# --- Record bot-trap hit ---
# Purpose: Capture and process suspected bot activity from public flows.
# Inputs: Query/body payload with source/reason/email metadata.
# Outputs: 204 response after trap record + optional user/email blocking.
@public_api_bp.route("/bot-trap", methods=["GET", "POST"])
@limiter.limit("60/minute")
@csrf.exempt
def public_bot_trap():
    payload = {}
    if request.is_json:
        payload = request.get_json(silent=True) or {}
    elif request.form:
        payload = request.form.to_dict()
    if not isinstance(payload, dict):
        payload = {}

    raw_source = request.args.get("source") or payload.get("source") or "public"
    raw_reason = request.args.get("reason") or payload.get("reason") or "link_click"
    source = str(raw_source).strip()
    reason = str(raw_reason).strip()
    email = (
        payload.get("email") or request.args.get("email") or ""
    ).strip().lower() or None

    user_id = current_user.get_id() if current_user.is_authenticated else None

    PublicBotTrapService.record_hit(
        request=request,
        source=source,
        reason=reason,
        email=email,
        user_id=user_id,
        extra={"payload_keys": list(payload.keys())},
        block=True,
    )

    if current_user.is_authenticated:
        PublicBotTrapService.block_user(current_user, reason="bot_trap_route")
    elif email:
        PublicBotTrapService.block_email_if_user_exists(email)

    resp = make_response("", 204)
    resp.headers["Cache-Control"] = "no-store"
    return resp


# --- List public units ---
# Purpose: Return active standard units for public conversion/tool usage.
# Inputs: None.
# Outputs: JSON payload containing unit metadata collection.
@public_api_bp.route("/units", methods=["GET"])
@limiter.exempt
def public_units():
    """Return standard (non-custom) active units for public tools."""
    try:
        units = (
            Unit.query.filter_by(is_active=True, is_custom=False)
            .order_by(Unit.unit_type.asc(), Unit.name.asc())
            .all()
        )
        return jsonify(
            {
                "success": True,
                "data": [
                    {
                        "id": u.id,
                        "name": u.name,
                        "symbol": getattr(u, "symbol", None),
                        "unit_type": u.unit_type,
                    }
                    for u in units
                ],
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# --- Search public global items ---
# Purpose: Return public global-library matches by name/alias.
# Inputs: Query string q plus optional type/group flags.
# Outputs: JSON list (or grouped list) of global-item payloads.
@public_api_bp.route("/global-items/search", methods=["GET"])
@limiter.exempt
def public_global_item_search():
    """Public search for Global Items by name or alias. Limited to 25 results."""
    q = (request.args.get("q") or "").strip()
    item_type = (request.args.get("type") or "").strip()
    if not q:
        return jsonify({"success": True, "results": []})

    try:
        cache_key = None
        if cache:
            raw_key = stable_cache_key(
                "public-global-items",
                {
                    "q": q,
                    "item_type": item_type or "",
                    "group": request.args.get("group") or "",
                },
            )
            cache_key = global_library_cache_key(raw_key)
            cached_payload = cache.get(cache_key)
            if cached_payload:
                return jsonify(cached_payload)

        query = GlobalItem.query.filter(not GlobalItem.is_archived)
        if item_type:
            query = query.filter(GlobalItem.item_type == item_type)

        term = f"%{q}%"
        try:
            # Try alias table if present
            from app.models import db as _db
            from app.models.global_item import GlobalItem as _GI

            alias_tbl = _db.Table(
                "global_item_alias", _db.metadata, autoload_with=_db.engine
            )
            query = query.filter(
                or_(
                    _GI.name.ilike(term),
                    _db.exists()
                    .where(alias_tbl.c.global_item_id == _GI.id)
                    .where(alias_tbl.c.alias.ilike(term)),
                )
            )
        except Exception:
            query = query.filter(GlobalItem.name.ilike(term))

        items = query.order_by(func.length(GlobalItem.name).asc()).limit(25).all()
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
                        ingredient_category_obj.name
                        if ingredient_category_obj
                        else None
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
            category_tag_names = [tag.name for tag in getattr(gi, "category_tags", [])]

            display_name = gi.name
            if (
                ingredient_payload
                and variation_payload
                and not variation_payload.get("form_bypass")
            ):
                display_name = (
                    f"{ingredient_payload['name']}, {variation_payload['name']}"
                )
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
                "variation_name": (
                    variation_payload["name"] if variation_payload else None
                ),
                "variation_slug": (
                    variation_payload["slug"] if variation_payload else None
                ),
                "physical_form": physical_form_payload,
                "functions": function_names,
                "applications": application_names,
                "default_unit": gi.default_unit,
                "unit": gi.default_unit,
                "density": gi.density,
                "default_is_perishable": gi.default_is_perishable,
                "recommended_shelf_life_days": gi.recommended_shelf_life_days,
                "saponification_value": getattr(gi, "saponification_value", None),
                "iodine_value": getattr(gi, "iodine_value", None),
                "fatty_acid_profile": getattr(gi, "fatty_acid_profile", None),
                "melting_point_c": getattr(gi, "melting_point_c", None),
                "recommended_fragrance_load_pct": gi.recommended_fragrance_load_pct,
                "is_active_ingredient": gi.is_active_ingredient,
                "inci_name": gi.inci_name,
                "cas_number": getattr(gi, "cas_number", None),
                "protein_content_pct": gi.protein_content_pct,
                "brewing_color_srm": gi.brewing_color_srm,
                "brewing_potential_sg": gi.brewing_potential_sg,
                "brewing_diastatic_power_lintner": gi.brewing_diastatic_power_lintner,
                "certifications": gi.certifications or [],
                "category_tags": category_tag_names,
                "ingredient_name": (
                    ingredient_payload["name"] if ingredient_payload else None
                ),
                "physical_form_name": (
                    physical_form_payload["name"] if physical_form_payload else None
                ),
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
                            else None
                        ),
                        "ingredient_category_name": (
                            ingredient_payload["ingredient_category_name"]
                            if ingredient_payload
                            else None
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
                            physical_form_payload["name"]
                            if physical_form_payload
                            else None
                        ),
                        "default_unit": gi.default_unit,
                        "unit": gi.default_unit,
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
                        "saponification_value": getattr(
                            gi, "saponification_value", None
                        ),
                        "iodine_value": getattr(gi, "iodine_value", None),
                        "fatty_acid_profile": getattr(gi, "fatty_acid_profile", None),
                        "melting_point_c": getattr(gi, "melting_point_c", None),
                        "flash_point_c": getattr(gi, "flash_point_c", None),
                        "moisture_content_percent": getattr(
                            gi, "moisture_content_percent", None
                        ),
                        "comedogenic_rating": getattr(gi, "comedogenic_rating", None),
                        "ph_value": getattr(gi, "ph_value", None),
                        "category_tags": category_tag_names,
                    }
                )

        if group_mode:
            payload = {"success": True, "results": list(grouped.values())}
        else:
            payload = {"success": True, "results": results}

        if cache_key:
            try:
                cache.set(cache_key, payload, timeout=_global_library_cache_timeout())
            except Exception:
                current_app.logger.debug(
                    "Unable to write global library cache key %s", cache_key
                )
        return jsonify(payload)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# --- Search soapcalc items ---
# Purpose: Return soapcalc item matches for public tools.
# Inputs: Query string q and optional group/limit flags.
# Outputs: JSON result payload with soapcalc item matches.
@public_api_bp.route("/soapcalc-items/search", methods=["GET"])
@limiter.limit("60/minute")
def public_soapcalc_items_search():
    """Search soapcalc CSV inventory items for public tools."""
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"success": True, "results": []})
    group_mode = request.args.get("group") == "ingredient"
    limit_raw = request.args.get("limit")
    limit = 25
    if limit_raw:
        try:
            limit = max(1, min(25, int(limit_raw)))
        except (TypeError, ValueError):
            limit = 25
    results = search_soapcalc_items(q, limit=limit, group=group_mode)
    resp = make_response(jsonify({"success": True, "results": results}))
    resp.headers["Cache-Control"] = "no-store"
    return resp


# --- Search soapcalc oils ---
# Purpose: Return legacy soapcalc oil matches for compatibility clients.
# Inputs: Query string q and optional group/limit flags.
# Outputs: JSON result payload with soapcalc oil matches.
@public_api_bp.route("/soapcalc-oils/search", methods=["GET"])
@limiter.limit("60/minute")
def public_soapcalc_oils_search():
    """Legacy soapcalc oil search endpoint."""
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"success": True, "results": []})
    group_mode = request.args.get("group") == "ingredient"
    limit_raw = request.args.get("limit")
    limit = 25
    if limit_raw:
        try:
            limit = max(1, min(25, int(limit_raw)))
        except (TypeError, ValueError):
            limit = 25
    results = search_soapcalc_oils(q, limit=limit, group=group_mode)
    resp = make_response(jsonify({"success": True, "results": results}))
    resp.headers["Cache-Control"] = "no-store"
    return resp


# --- Convert units publicly ---
# Purpose: Convert quantities between units without authentication.
# Inputs: JSON payload with quantity/from_unit/to_unit plus optional density data.
# Outputs: JSON conversion result payload or error response.
@public_api_bp.route("/convert-units", methods=["POST"])
@limiter.exempt
@csrf.exempt
def public_convert_units():
    """Public unit conversion endpoint using ConversionEngine. Does not require auth."""
    try:
        data = request.get_json() or {}
        quantity = data.get("quantity")
        from_unit = (data.get("from_unit") or "").strip()
        to_unit = (data.get("to_unit") or "").strip()
        ingredient_id = data.get("ingredient_id")
        density = data.get("density")

        result = ConversionEngine.convert_units(
            quantity, from_unit, to_unit, ingredient_id=ingredient_id, density=density
        )
        return jsonify({"success": result.get("success", False), "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# --- Answer public help bot prompt ---
# Purpose: Return AI help-bot answer for public support prompts.
# Inputs: JSON payload containing prompt/question and optional tone.
# Outputs: JSON success payload with answer or error metadata.
@public_api_bp.route("/help-bot", methods=["POST"])
@limiter.limit("30/minute")
@csrf.exempt
def public_help_bot():
    data = request.get_json() or {}
    prompt = (data.get("prompt") or data.get("question") or "").strip()
    tone = data.get("tone")

    if not prompt:
        return jsonify({"success": False, "error": "Prompt is required."}), 400

    try:
        service = PublicBotService()
        result = service.answer(prompt, tone=tone)
        return jsonify({"success": True, **result})
    except PublicBotServiceError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except GoogleAIClientError as exc:
        current_app.logger.exception("Public help bot AI failure")
        return jsonify({"success": False, "error": str(exc)}), 502
    except Exception:
        current_app.logger.exception("Public help bot unexpected error")
        return jsonify({"success": False, "error": "Unexpected help bot failure."}), 500
