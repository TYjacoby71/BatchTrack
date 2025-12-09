from collections import OrderedDict

from flask import Blueprint, jsonify, make_response, request, current_app
from datetime import datetime, timezone
from app.extensions import limiter, csrf, cache
from app.models.models import Unit
from app.models.global_item import GlobalItem
from app.services.unit_conversion.unit_conversion import ConversionEngine
from app.services.public_bot_service import PublicBotService, PublicBotServiceError
from app.services.ai import GoogleAIClientError
from app.services.cache_invalidation import global_library_cache_key
from app.utils.cache_utils import stable_cache_key
from sqlalchemy import func, or_

public_api_bp = Blueprint("public_api", __name__)


def _global_library_cache_timeout() -> int:
    return current_app.config.get(
        "GLOBAL_LIBRARY_CACHE_TIMEOUT",
        current_app.config.get("CACHE_DEFAULT_TIMEOUT", 120),
    )

@public_api_bp.route("/server-time", methods=["GET"])
@limiter.exempt
def server_time():
    ts = datetime.now(timezone.utc).isoformat()
    resp = make_response(jsonify({"server_time": ts}))
    resp.headers["Cache-Control"] = "no-store"
    return resp


@public_api_bp.route("/units", methods=["GET"])
@limiter.exempt
def public_units():
    """Return standard (non-custom) active units for public tools."""
    try:
        units = Unit.query.filter_by(is_active=True, is_custom=False).order_by(Unit.unit_type.asc(), Unit.name.asc()).all()
        return jsonify({
            'success': True,
            'data': [
                {
                    'id': u.id,
                    'name': u.name,
                    'symbol': getattr(u, 'symbol', None),
                    'unit_type': u.unit_type,
                } for u in units
            ]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@public_api_bp.route("/global-items/search", methods=["GET"])
@limiter.exempt
def public_global_item_search():
    """Public search for Global Items by name or alias. Limited to 25 results."""
    q = (request.args.get('q') or '').strip()
    item_type = (request.args.get('type') or '').strip()
    if not q:
        return jsonify({'success': True, 'results': []})

    try:
        cache_key = None
        if cache:
            raw_key = stable_cache_key(
                "public-global-items",
                {
                    'q': q,
                    'item_type': item_type or '',
                    'group': request.args.get('group') or '',
                },
            )
            cache_key = global_library_cache_key(raw_key)
            cached_payload = cache.get(cache_key)
            if cached_payload:
                return jsonify(cached_payload)

        query = GlobalItem.query.filter(GlobalItem.is_archived != True)
        if item_type:
            query = query.filter(GlobalItem.item_type == item_type)

        term = f"%{q}%"
        try:
            # Try alias table if present
            from app.models.global_item import GlobalItem as _GI
            from app.models import db as _db
            alias_tbl = _db.Table('global_item_alias', _db.metadata, autoload_with=_db.engine)
            query = query.filter(
                or_(
                    _GI.name.ilike(term),
                    _db.exists().where(alias_tbl.c.global_item_id == _GI.id).where(alias_tbl.c.alias.ilike(term))
                )
            )
        except Exception:
            query = query.filter(GlobalItem.name.ilike(term))

        items = query.order_by(func.length(GlobalItem.name).asc()).limit(25).all()
        group_mode = request.args.get('group') == 'ingredient' and (not item_type or item_type == 'ingredient')
        grouped = OrderedDict() if group_mode else None
        results = []

        for gi in items:
            ingredient_obj = gi.ingredient if getattr(gi, 'ingredient', None) else None
            ingredient_category_obj = ingredient_obj.category if ingredient_obj and getattr(ingredient_obj, 'category', None) else None
            physical_form_obj = gi.physical_form if getattr(gi, 'physical_form', None) else None
            ingredient_payload = None
            if ingredient_obj:
                ingredient_payload = {
                    'id': ingredient_obj.id,
                    'name': ingredient_obj.name,
                    'slug': ingredient_obj.slug,
                    'inci_name': ingredient_obj.inci_name,
                    'cas_number': ingredient_obj.cas_number,
                    'ingredient_category_id': ingredient_obj.ingredient_category_id,
                    'ingredient_category_name': ingredient_category_obj.name if ingredient_category_obj else None,
                }
            physical_form_payload = None
            if physical_form_obj:
                physical_form_payload = {
                    'id': physical_form_obj.id,
                    'name': physical_form_obj.name,
                    'slug': physical_form_obj.slug,
                }
            function_names = [tag.name for tag in getattr(gi, 'functions', [])]
            application_names = [tag.name for tag in getattr(gi, 'applications', [])]
            category_tag_names = [tag.name for tag in getattr(gi, 'category_tags', [])]

            display_name = gi.name
            if ingredient_payload and physical_form_payload:
                display_name = f"{ingredient_payload['name']} ({physical_form_payload['name']})"
            elif ingredient_payload:
                display_name = ingredient_payload['name']

            item_payload = {
                'id': gi.id,
                'name': display_name,
                'text': display_name,
                'display_name': display_name,
                'raw_name': gi.name,
                'item_type': gi.item_type,
                'ingredient': ingredient_payload,
                'physical_form': physical_form_payload,
                'functions': function_names,
                'applications': application_names,
                'default_unit': gi.default_unit,
                'unit': gi.default_unit,
                'density': gi.density,
                'default_is_perishable': gi.default_is_perishable,
                'recommended_shelf_life_days': gi.recommended_shelf_life_days,
                'saponification_value': getattr(gi, 'saponification_value', None),
                'recommended_usage_rate': gi.recommended_usage_rate,
                'recommended_fragrance_load_pct': gi.recommended_fragrance_load_pct,
                'is_active_ingredient': gi.is_active_ingredient,
                'inci_name': gi.inci_name,
                'protein_content_pct': gi.protein_content_pct,
                'brewing_color_srm': gi.brewing_color_srm,
                'brewing_potential_sg': gi.brewing_potential_sg,
                'brewing_diastatic_power_lintner': gi.brewing_diastatic_power_lintner,
                'certifications': gi.certifications or [],
                'category_tags': category_tag_names,
                'ingredient_name': ingredient_payload['name'] if ingredient_payload else None,
                'physical_form_name': physical_form_payload['name'] if physical_form_payload else None,
            }
            results.append(item_payload)

            if group_mode:
                group_key = ingredient_payload['id'] if ingredient_payload else f"item-{gi.id}"
                group_entry = grouped.get(group_key)
                if not group_entry:
                    group_entry = {
                        'id': ingredient_payload['id'] if ingredient_payload else gi.id,
                        'ingredient_id': ingredient_payload['id'] if ingredient_payload else None,
                        'name': ingredient_payload['name'] if ingredient_payload else display_name,
                        'text': ingredient_payload['name'] if ingredient_payload else display_name,
                        'display_name': ingredient_payload['name'] if ingredient_payload else display_name,
                        'item_type': gi.item_type,
                        'ingredient': ingredient_payload,
                        'ingredient_category_id': ingredient_payload['ingredient_category_id'] if ingredient_payload else None,
                        'ingredient_category_name': ingredient_payload['ingredient_category_name'] if ingredient_payload else None,
                        'forms': [],
                    }
                    grouped[group_key] = group_entry

                group_entry['forms'].append({
                    'id': gi.id,
                    'name': display_name,
                    'text': display_name,
                    'display_name': display_name,
                    'raw_name': gi.name,
                    'item_type': gi.item_type,
                    'ingredient_id': ingredient_payload['id'] if ingredient_payload else None,
                    'ingredient_name': ingredient_payload['name'] if ingredient_payload else None,
                    'physical_form': physical_form_payload,
                    'physical_form_name': physical_form_payload['name'] if physical_form_payload else None,
                    'default_unit': gi.default_unit,
                    'unit': gi.default_unit,
                    'density': gi.density,
                    'default_is_perishable': gi.default_is_perishable,
                    'recommended_shelf_life_days': gi.recommended_shelf_life_days,
                    'recommended_usage_rate': gi.recommended_usage_rate,
                    'recommended_fragrance_load_pct': gi.recommended_fragrance_load_pct,
                    'aliases': gi.aliases or [],
                    'certifications': gi.certifications or [],
                    'functions': function_names,
                    'applications': application_names,
                    'inci_name': gi.inci_name,
                    'protein_content_pct': gi.protein_content_pct,
                    'brewing_color_srm': gi.brewing_color_srm,
                    'brewing_potential_sg': gi.brewing_potential_sg,
                    'brewing_diastatic_power_lintner': gi.brewing_diastatic_power_lintner,
                    'saponification_value': getattr(gi, 'saponification_value', None),
                    'iodine_value': getattr(gi, 'iodine_value', None),
                    'melting_point_c': getattr(gi, 'melting_point_c', None),
                    'flash_point_c': getattr(gi, 'flash_point_c', None),
                    'moisture_content_percent': getattr(gi, 'moisture_content_percent', None),
                    'comedogenic_rating': getattr(gi, 'comedogenic_rating', None),
                    'ph_value': getattr(gi, 'ph_value', None),
                    'category_tags': category_tag_names,
                })

        if group_mode:
            payload = {'success': True, 'results': list(grouped.values())}
        else:
            payload = {'success': True, 'results': results}

        if cache_key:
            try:
                cache.set(cache_key, payload, timeout=_global_library_cache_timeout())
            except Exception:
                current_app.logger.debug("Unable to write global library cache key %s", cache_key)
        return jsonify(payload)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@public_api_bp.route("/convert-units", methods=["POST"])
@limiter.exempt
@csrf.exempt
def public_convert_units():
    """Public unit conversion endpoint using ConversionEngine. Does not require auth."""
    try:
        data = request.get_json() or {}
        quantity = data.get('quantity')
        from_unit = (data.get('from_unit') or '').strip()
        to_unit = (data.get('to_unit') or '').strip()
        ingredient_id = data.get('ingredient_id')
        density = data.get('density')

        result = ConversionEngine.convert_units(
            quantity, from_unit, to_unit, ingredient_id=ingredient_id, density=density
        )
        return jsonify({'success': result.get('success', False), 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


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