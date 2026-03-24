"""Public API routes for unauthenticated tool and utility endpoints.

Synopsis:
Provide rate-limited public endpoints for server time, bot-trap handling,
global-library search, soapcalc lookup, unit conversion, and help-bot access.

Glossary:
- Public API blueprint: Route namespace containing unauthenticated API handlers.
- Bot trap: Endpoint that records and blocks suspicious automation traffic.
- Group mode: Ingredient-centric payload mode for grouped global-item results.
"""

import logging
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, make_response, request
from flask_login import current_user

from app.extensions import cache, csrf, limiter
from app.services.ai import GoogleAIClientError
from app.services.cache_invalidation import global_library_cache_key
from app.services.public_catalog_service import PublicCatalogService
from app.services.public_bot_service import PublicBotService, PublicBotServiceError
from app.services.public_bot_trap_service import PublicBotTrapService
from app.services.soapcalc_oils_service import (
    search_soapcalc_items,
    search_soapcalc_oils,
)
from app.services.unit_conversion.unit_conversion import ConversionEngine
from app.utils.cache_utils import stable_cache_key

logger = logging.getLogger(__name__)


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
    if PublicBotTrapService.is_google_ads_verification_request(request):
        current_app.logger.info(
            "Skipping bot trap for Google Ads verification request: ip=%s path=%s user_agent=%s referer=%s",
            PublicBotTrapService.resolve_request_ip(request),
            request.path,
            (request.headers.get("User-Agent") or "")[:160],
            (request.headers.get("Referer") or "")[:160],
        )
        resp = make_response("", 204)
        resp.headers["Cache-Control"] = "no-store"
        return resp

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
        units = PublicCatalogService.list_public_units()
        return jsonify(
            {
                "success": True,
                "data": units,
            }
        )
    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/api/public.py:151",
            exc_info=True,
        )
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

        payload = PublicCatalogService.build_public_global_item_search_payload(
            query_text=q,
            item_type=item_type or None,
            group=request.args.get("group"),
            limit=25,
        )

        if cache_key:
            try:
                cache.set(cache_key, payload, timeout=_global_library_cache_timeout())
            except Exception:
                current_app.logger.debug(
                    "Unable to write global library cache key %s", cache_key
                )
        return jsonify(payload)
    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/api/public.py:448",
            exc_info=True,
        )
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
        logger.warning(
            "Suppressed exception fallback at app/blueprints/api/public.py:523",
            exc_info=True,
        )
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
