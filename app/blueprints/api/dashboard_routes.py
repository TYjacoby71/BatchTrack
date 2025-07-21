
from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from app.services.dashboard_alerts import DashboardAlertsService
from app.utils.permissions import require_permission

dashboard_api_bp = Blueprint('dashboard_api', __name__, url_prefix='/api')

@dashboard_api_bp.route('/dashboard-alerts')
@login_required
def get_dashboard_alerts():
    """Get dashboard alerts for current user's organization"""
    try:
        org_id = current_user.organization_id
        if not org_id:
            return jsonify({'success': False, 'error': 'No organization associated with user'}), 400
            
        alerts = DashboardAlertsService.get_alerts_for_organization(org_id)
        
        return jsonify({
            'success': True,
            'data': {
                'alerts': [alert.to_dict() for alert in alerts],
                'count': len(alerts)
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@dashboard_api_bp.route('/dismiss-alert', methods=['POST'])
@login_required 
@require_permission('alerts.dismiss')
def dismiss_alert():
    """Dismiss an alert"""
    try:
        from flask import request
        data = request.get_json()
        alert_id = data.get('alert_id')
        
        if not alert_id:
            return jsonify({'success': False, 'error': 'Alert ID required'}), 400
            
        success = DashboardAlertsService.dismiss_alert(alert_id, current_user.organization_id)
        
        if success:
            return jsonify({'success': True, 'message': 'Alert dismissed successfully'})
        else:
            return jsonify({'success': False, 'error': 'Alert not found or access denied'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
