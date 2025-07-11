from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from datetime import datetime
from flask import session

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/server-time')
def server_time():
    """Get current server time in user's timezone"""
    from ..utils.timezone_utils import TimezoneUtils

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
def dashboard_alerts():
    """Get dashboard alerts with session-based dismissals"""
    from ...services.dashboard_alerts import DashboardAlertService

    # Get dismissed alerts from session
    dismissed_alerts = session.get('dismissed_alerts', [])

    # Get alerts with dismissed ones filtered out
    alert_data = DashboardAlertService.get_dashboard_alerts(
        dismissed_alerts=dismissed_alerts
    )

    return jsonify(alert_data)

# Import sub-blueprints to register their routes
from .stock_routes import stock_api_bp
from .ingredient_routes import ingredient_api_bp
from .container_routes import container_api_bp
from .fifo_routes import fifo_api_bp
from .reservation_routes import reservation_api_bp

# Register sub-blueprints
api_bp.register_blueprint(stock_api_bp)
api_bp.register_blueprint(ingredient_api_bp)
api_bp.register_blueprint(container_api_bp)
api_bp.register_blueprint(fifo_api_bp)
api_bp.register_blueprint(reservation_api_bp)