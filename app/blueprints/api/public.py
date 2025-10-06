from flask import Blueprint, jsonify, make_response, request
from datetime import datetime, timezone
from app.extensions import limiter, csrf
from app.models.models import Unit
from app.models.global_item import GlobalItem
from app.services.unit_conversion.unit_conversion import ConversionEngine
from sqlalchemy import func, or_

public_api_bp = Blueprint("public_api", __name__)

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
        results = []
        for gi in items:
            results.append({
                'id': gi.id,
                'text': gi.name,
                'item_type': gi.item_type,
                'default_unit': gi.default_unit,
                'density': gi.density,
                'saponification_value': getattr(gi, 'saponification_value', None),
            })
        return jsonify({'success': True, 'results': results})
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