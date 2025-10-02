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
        db.session.add(u)
        db.session.commit()
        return jsonify({'success': True, 'data': {'id': u.id, 'name': u.name, 'unit_type': u.unit_type}})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/category-visibility/<int:category_id>')
@login_required
def get_category_visibility_api(category_id):
    """Get visibility settings for a category by ID"""
    try:
        from app.models.category import IngredientCategory

        category = IngredientCategory.query.get_or_404(category_id)

        # Check if user has access to this category
        if category.organization_id and category.organization_id != current_user.organization_id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        visibility = {
            'show_saponification_value': getattr(category, 'show_saponification_value', False),
            'show_iodine_value': getattr(category, 'show_iodine_value', False),
            'show_melting_point': getattr(category, 'show_melting_point', False),
            'show_flash_point': getattr(category, 'show_flash_point', False),
            'show_ph_value': getattr(category, 'show_ph_value', False),
            'show_moisture_content': getattr(category, 'show_moisture_content', False),
            'show_shelf_life_months': getattr(category, 'show_shelf_life_months', False),
            'show_comedogenic_rating': getattr(category, 'show_comedogenic_rating', False)
        }

        return jsonify({'success': True, 'visibility': visibility})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/containers/suggestions', methods=['GET'])
@login_required
def get_container_suggestions():
    """Return distinct container field suggestions (material/type/style/color) and curated list for materials.

    Query params:
      - field: one of material|type|style|color (optional; default returns all)
      - q: optional search prefix to filter suggestions
      - limit: max suggestions per field (default 20)
    """
    try:
        field = (request.args.get('field') or '').strip().lower()
        q = (request.args.get('q') or '').strip().lower()
        limit = max(1, min(int(request.args.get('limit', 20)), 100))

        # Map to model columns
        field_map = {
            'material': GlobalItem.container_material,
            'type': GlobalItem.container_type,
            'style': GlobalItem.container_style,
            'color': GlobalItem.container_color,
        }

        def fetch_distinct(col):
            qry = db.session.query(col).filter(
                GlobalItem.item_type.in_(['container', 'packaging']),
                col.isnot(None),
                col != ''
            )
            if q:
                qry = qry.filter(col.ilike(f"%{q}%"))
            values = [r[0] for r in qry.distinct().order_by(col.asc()).limit(limit).all()]
            return values

        # Curated materials baseline
        curated_materials = [
            'Glass', 'PET Plastic', 'HDPE Plastic', 'PP Plastic', 'Aluminum', 'Tin', 'Steel', 'Paperboard', 'Cardboard'
        ]
        if q:
            curated_materials = [m for m in curated_materials if q.lower() in m.lower()]
        curated_materials = curated_materials[:limit]

        if field in field_map:
            values = fetch_distinct(field_map[field])
            return jsonify({'success': True, 'field': field, 'suggestions': values, 'curated_materials': curated_materials})

        # Return all fields
        payload = {
            'material': fetch_distinct(field_map['material']),
            'type': fetch_distinct(field_map['type']),
            'style': fetch_distinct(field_map['style']),
            'color': fetch_distinct(field_map['color']),
            'curated_materials': curated_materials,
        }
        return jsonify({'success': True, 'suggestions': payload})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500