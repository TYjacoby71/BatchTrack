from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from datetime import datetime
from flask import session
import logging

# Configure logging
logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/', methods=['GET', 'HEAD'])
def health_check():
    """Health check endpoint for monitoring services"""
    if request.method == 'HEAD':
        return '', 200
    return jsonify({'status': 'ok', 'timestamp': datetime.utcnow().isoformat()})

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
    unit_type = request.args.get('type')
    q = (request.args.get('q') or '').strip()
    qry = Unit.scoped()
    if unit_type:
        qry = qry.filter_by(unit_type=unit_type)
    if q:
        qry = qry.filter(Unit.name.ilike(f"%{q}%"))
    units = qry.order_by(Unit.unit_type, Unit.name).limit(50).all()
    return jsonify({'success': True, 'data': [{'id': u.id, 'name': u.name, 'unit_type': u.unit_type} for u in units]})

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
        from ...extensions import db
        db.session.add(u)
        db.session.commit()
        return jsonify({'success': True, 'data': {'id': u.id, 'name': u.name, 'unit_type': u.unit_type}})
    except Exception as e:
        from ...extensions import db
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
