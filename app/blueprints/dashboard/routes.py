
from flask import Blueprint, render_template, jsonify, session
from flask_login import login_required, current_user
from app.services.dashboard_alerts import dashboard_alert_service
from app.utils.permissions import require_permission

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard', template_folder='templates')

@dashboard_bp.route('/')
@login_required
def index():
    """Main dashboard view"""
    try:
        # Get dismissed alerts from session
        dismissed_alerts = session.get('dismissed_alerts', [])
        
        # Get dashboard alerts
        alert_data = dashboard_alert_service.get_dashboard_alerts(
            organization_id=current_user.organization_id,
            dismissed_alerts=dismissed_alerts,
            max_alerts=5
        )
        
        return render_template('dashboard.html', alert_data=alert_data)
        
    except Exception as e:
        dashboard_alert_service.handle_service_error(e, "dashboard_index")
        # Fallback to empty alerts
        alert_data = {'alerts': [], 'total_alerts': 0, 'hidden_count': 0}
        return render_template('dashboard.html', alert_data=alert_data)

@dashboard_bp.route('/api/alerts')
@login_required
def api_alerts():
    """API endpoint for dashboard alerts"""
    try:
        dismissed_alerts = session.get('dismissed_alerts', [])
        
        alert_data = dashboard_alert_service.get_dashboard_alerts(
            organization_id=current_user.organization_id,
            dismissed_alerts=dismissed_alerts
        )
        
        return jsonify({
            'success': True,
            'data': alert_data
        })
        
    except Exception as e:
        dashboard_alert_service.handle_service_error(e, "api_alerts")
        return jsonify({'success': False, 'error': str(e)}), 500

@dashboard_bp.route('/api/refresh-alerts', methods=['POST'])
@login_required
def refresh_alerts():
    """Refresh dashboard alerts cache"""
    try:
        dashboard_alert_service.clear_organization_cache(current_user.organization_id)
        
        return jsonify({
            'success': True,
            'message': 'Alerts cache refreshed'
        })
        
    except Exception as e:
        dashboard_alert_service.handle_service_error(e, "refresh_alerts")
        return jsonify({'success': False, 'error': str(e)}), 500
