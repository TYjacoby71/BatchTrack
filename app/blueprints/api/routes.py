from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from datetime import datetime, timezone
from flask import session
import logging
from app.models import InventoryItem  # Added for get_ingredients endpoint
from app import db  # Assuming db is imported from app
from app.utils.permissions import require_permission
from app.services.batchbot_service import BatchBotService, BatchBotServiceError
from app.services.batchbot_usage_service import (
    BatchBotUsageService,
    BatchBotLimitError,
    BatchBotChatLimitError,
)
from app.services.batchbot_credit_service import BatchBotCreditService
from app.services.ai import GoogleAIClientError

# Configure logging
logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/', methods=['GET', 'HEAD'])
def health_check():
    """Health check endpoint for monitoring services"""
    if request.method == 'HEAD':
        return '', 200
    return jsonify({'status': 'ok', 'timestamp': datetime.now(timezone.utc).isoformat()})

@api_bp.route('/server-time')
def server_time():
    """Get current server time in user's timezone"""
    from ...utils.timezone_utils import TimezoneUtils

    # Get current time in user's timezone
    user_time = TimezoneUtils.now()

    return jsonify({
        'current_time': user_time.isoformat(),
        'timestamp': user_time.isoformat(),
        'timezone': str(TimezoneUtils.get_user_timezone())
    })

@api_bp.route('/dismiss-alert', methods=['POST'])
def dismiss_alert():
    """Dismiss an alert for the current session"""
    from flask import request
    data = request.get_json()
    alert_type = data.get('alert_type')

    if not alert_type:
        return jsonify({'error': 'Alert type required'}), 400

    # Initialize dismissed alerts in session if not exists
    if 'dismissed_alerts' not in session:
        session['dismissed_alerts'] = []

    # Add to dismissed alerts if not already there
    if alert_type not in session['dismissed_alerts']:
        session['dismissed_alerts'].append(alert_type)
        session.permanent = True  # Make session persistent

    return jsonify({'success': True})

@api_bp.route('/dashboard-alerts')
@login_required
def get_dashboard_alerts():
    """Get dashboard alerts for current user's organization"""
    try:
        from flask import session
        from ...services.dashboard_alerts import DashboardAlertService
        import logging

        # Get dismissed alerts from session
        dismissed_alerts = session.get('dismissed_alerts', [])

        # Get alerts from service
        alert_data = DashboardAlertService.get_dashboard_alerts(dismissed_alerts=dismissed_alerts)

        # Log for debugging
        logging.info(f"Dashboard alerts requested - found {len(alert_data.get('alerts', []))} alerts")

        return jsonify({
            'success': True,
            'alerts': alert_data['alerts'],
            'total_alerts': alert_data['total_alerts'],
            'hidden_count': alert_data['hidden_count']
        })

    except Exception as e:
        logging.error(f"Error getting dashboard alerts: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Stock checking is now handled by the dedicated stock_routes.py blueprint
# All stock check requests should use /api/check-stock endpoint

# Import sub-blueprints to register their routes

from .ingredient_routes import ingredient_api_bp
from .container_routes import container_api_bp
from .reservation_routes import reservation_api_bp
from app.models.product_category import ProductCategory
from app.models.unit import Unit
from ...utils.unit_utils import get_global_unit_list

# Register sub-blueprints

api_bp.register_blueprint(ingredient_api_bp, url_prefix='/ingredients')
api_bp.register_blueprint(container_api_bp)
api_bp.register_blueprint(reservation_api_bp)

@api_bp.route('/inventory/item/<int:item_id>', methods=['GET'])
@login_required
def get_inventory_item(item_id):
    """Get inventory item details for editing"""
    from ...models import InventoryItem

    item = InventoryItem.query.filter_by(
        id=item_id,
        organization_id=current_user.organization_id
    ).first_or_404()

    return jsonify({
        'id': item.id,
        'name': item.name,
        'quantity': item.quantity,
        'unit': item.unit,
        'type': item.type,
        'cost_per_unit': item.cost_per_unit,
        'notes': getattr(item, 'notes', None),
        'density': item.density,
        'category_id': item.category_id,
        'global_item_id': item.global_item_id,
        'is_perishable': item.is_perishable,
        'shelf_life_days': item.shelf_life_days,
        'capacity': getattr(item, 'capacity', None),
        'capacity_unit': getattr(item, 'capacity_unit', None)
    })


@api_bp.route('/categories/<int:cat_id>', methods=['GET'])
@login_required
def get_category(cat_id):
    c = ProductCategory.query.get_or_404(cat_id)
    return jsonify({'id': c.id, 'name': c.name, 'is_typically_portioned': bool(c.is_typically_portioned)})


@api_bp.route('/unit-search', methods=['GET'])
@login_required
def list_units():
    """Unified unit search using get_global_unit_list (standard + org custom)."""
    unit_type = (request.args.get('type') or request.args.get('unit_type') or '').strip()
    q = (request.args.get('q') or '').strip()
    try:
        units = get_global_unit_list() or []
    except Exception:
        units = []

    if unit_type:
        units = [u for u in units if getattr(u, 'unit_type', None) == unit_type]
    if q:
        q_lower = q.lower()
        units = [u for u in units if (getattr(u, 'name', '') or '').lower().find(q_lower) != -1]

    try:
        units.sort(key=lambda u: (str(getattr(u, 'unit_type', '') or ''), str(getattr(u, 'name', '') or '')))
    except Exception:
        pass

    results = units[:50]
    return jsonify({'success': True, 'data': [
        {
            'id': getattr(u, 'id', None),
            'name': getattr(u, 'name', ''),
            'unit_type': getattr(u, 'unit_type', None),
            'symbol': getattr(u, 'symbol', None),
            'is_custom': getattr(u, 'is_custom', False)
        } for u in results
    ]})

@api_bp.route('/units', methods=['POST'])
@login_required
def create_unit():
    try:
        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        unit_type = (data.get('unit_type') or 'count').strip()
        if not name:
            return jsonify({'success': False, 'error': 'Name is required'}), 400
        # Prevent duplicates within standard scope
        existing = Unit.query.filter(Unit.name.ilike(name)).first()
        if existing:
            return jsonify({'success': True, 'data': {'id': existing.id, 'name': existing.name, 'unit_type': existing.unit_type}})
        u = Unit(name=name, unit_type=unit_type, conversion_factor=1.0, base_unit='Piece', is_active=True, is_custom=False, is_mapped=True, organization_id=None)
        db.session.add(u)
        db.session.commit()
        return jsonify({'success': True, 'data': {'id': u.id, 'name': u.name, 'unit_type': u.unit_type}})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/containers/suggestions', methods=['GET'])
@login_required
def get_container_suggestions():
    """Return container field suggestions from curated master lists.

    Query params:
      - field: one of material|type|style|color (optional; default returns all)
      - q: optional search prefix to filter suggestions
      - limit: max suggestions per field (default 20)
    """
    try:
        field = (request.args.get('field') or '').strip().lower()
        q = (request.args.get('q') or '').strip().lower()
        limit = max(1, min(int(request.args.get('limit', 20)), 100))

        # Load master lists from settings - single source of truth
        from app.blueprints.developer.routes import load_curated_container_lists
        curated_lists = load_curated_container_lists()

        def filter_list(items):
            if q:
                filtered = [item for item in items if q.lower() in item.lower()]
            else:
                filtered = items[:]
            return filtered[:limit]

        if field in ['material', 'type', 'style', 'color']:
            field_key = field + 's' if field != 'material' else 'materials'
            suggestions = filter_list(curated_lists.get(field_key, []))
            return jsonify({
                'success': True, 
                'field': field, 
                'suggestions': suggestions
            })

        # Return all fields
        payload = {
            'material': filter_list(curated_lists['materials']),
            'type': filter_list(curated_lists['types']),
            'style': filter_list(curated_lists['styles']),
            'color': filter_list(curated_lists['colors'])
        }
        return jsonify({'success': True, 'suggestions': payload})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Added timezone endpoint
@api_bp.route('/timezone', methods=['GET'])
def get_timezone():
    """Get server timezone info"""
    from datetime import datetime
    import pytz

    server_tz = current_app.config.get('TIMEZONE', 'UTC')
    now_utc = datetime.now(timezone.utc)

    return jsonify({
        'server_timezone': server_tz,
        'utc_time': now_utc.isoformat(),
        'available_timezones': pytz.all_timezones_set
    })

# Added ingredients endpoint for unit converter
@api_bp.route('/ingredients', methods=['GET'])
@login_required
def get_ingredients():
    """Get user's ingredients for unit converter"""
    try:
        ingredients = InventoryItem.query.filter_by(
            organization_id=current_user.organization_id,
            type='ingredient'
        ).order_by(InventoryItem.name).all()

        return jsonify([{
            'id': ing.id,
            'name': ing.name,
            'density': ing.density,
            'type': ing.type,
            'unit': ing.unit
        } for ing in ingredients])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/unit-converter', methods=['POST'])
@login_required
@require_permission('inventory.view')
def unit_converter():
    """Unit conversion endpoint for the modal."""
    try:
        data = request.get_json() or {}
        from_amount = float(data.get('from_amount', 0))
        from_unit = data.get('from_unit', '')
        to_unit = data.get('to_unit', '')
        ingredient_id = data.get('ingredient_id')

        if not all([from_amount, from_unit, to_unit]):
            return jsonify({'success': False, 'error': 'Missing required parameters'})

        # Get ingredient for density if needed
        ingredient = None
        if ingredient_id:
            ingredient = db.session.get(InventoryItem, ingredient_id)

        # Perform conversion using unit conversion service
        from app.services.unit_conversion import UnitConversionService
        result = UnitConversionService.convert_with_density(
            from_amount, from_unit, to_unit, 
            density=ingredient.density if ingredient else None
        )

        if result['success']:
            return jsonify({
                'success': True,
                'result': result['converted_amount'],
                'from_amount': from_amount,
                'from_unit': from_unit,
                'to_unit': to_unit
            })
        else:
            return jsonify({'success': False, 'error': result.get('error', 'Conversion failed')})

    except Exception as e:
        current_app.logger.error(f"Unit converter API error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@api_bp.route('/batchbot/chat', methods=['POST'])
@login_required
def batchbot_chat():
    data = request.get_json() or {}
    prompt = (data.get('prompt') or '').strip()
    history = data.get('history') or []
    metadata = data.get('metadata') or {}

    if not prompt:
        return jsonify({'success': False, 'error': 'Prompt is required.'}), 400

    try:
        service = BatchBotService(current_user)
        response = service.chat(prompt=prompt, history=history, metadata=metadata)
        return jsonify({
            'success': True,
            'message': response.text,
            'tool_results': response.tool_results,
            'usage': response.usage,
            'quota': _serialize_quota(response.quota, response.credits),
        })
    except BatchBotLimitError as exc:
        return jsonify({
            'success': False,
            'error': str(exc),
            'limit': {
                'allowed': exc.allowed,
                'used': exc.used,
                'window_end': exc.window_end.isoformat(),
            },
        }), 429
    except BatchBotChatLimitError as exc:
        return jsonify({
            'success': False,
            'error': str(exc),
            'chat_limit': {
                'allowed': exc.limit,
                'used': exc.used,
                'window_end': exc.window_end.isoformat(),
            },
        }), 429
    except BatchBotServiceError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except GoogleAIClientError as exc:
        current_app.logger.exception("BatchBot AI failure")
        return jsonify({'success': False, 'error': str(exc)}), 502
    except Exception:
        current_app.logger.exception("Unexpected BatchBot failure")
        return jsonify({'success': False, 'error': 'Unexpected BatchBot failure.'}), 500


@api_bp.route('/batchbot/usage', methods=['GET'])
@login_required
def batchbot_usage():
    org = getattr(current_user, 'organization', None)
    if not org:
        return jsonify({'success': False, 'error': 'Organization is required.'}), 400

    snapshot = BatchBotUsageService.get_usage_snapshot(org)
    credit_snapshot = BatchBotCreditService.snapshot(org)
    return jsonify({'success': True, 'quota': _serialize_quota(snapshot, credit_snapshot)})


def _serialize_quota(snapshot, credits=None):
    return {
        'allowed': snapshot.allowed,
        'used': snapshot.used,
        'remaining': snapshot.remaining,
        'window_start': snapshot.window_start.isoformat(),
        'window_end': snapshot.window_end.isoformat(),
        'chat_limit': snapshot.chat_limit,
        'chat_used': snapshot.chat_used,
        'chat_remaining': snapshot.chat_remaining,
        'credits': {
            'total': getattr(credits, "total", None),
            'remaining': getattr(credits, "remaining", None),
            'next_expiration': getattr(credits, "expires_next", None).isoformat() if getattr(credits, "expires_next", None) else None,
        } if credits else None,
    }