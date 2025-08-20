
from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from app.services.dashboard_alerts import DashboardAlertService
from app.utils.permissions import require_permission

dashboard_api_bp = Blueprint('dashboard_api', __name__, url_prefix='/api')

@dashboard_api_bp.route('/dashboard-alerts')
@login_required
def get_dashboard_alerts():
    """Get dashboard alerts for current user's organization"""
    try:
        from flask import session
        
        # Get dismissed alerts from session
        dismissed_alerts = session.get('dismissed_alerts', [])
        
        # Get alerts from service
        alert_data = DashboardAlertService.get_dashboard_alerts(dismissed_alerts=dismissed_alerts)
        
        return jsonify({
            'success': True,
            'alerts': alert_data['alerts'],
            'total_alerts': alert_data['total_alerts'],
            'hidden_count': alert_data['hidden_count']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@dashboard_api_bp.route('/dismiss-alert', methods=['POST'])
@login_required 
def dismiss_alert():
    """Dismiss an alert"""
    try:
        from flask import request, session
        data = request.get_json()
        alert_type = data.get('alert_type')
        
        if not alert_type:
            return jsonify({'success': False, 'error': 'Alert type required'}), 400
            
        # Session-based dismissal (alerts are dismissed in session)
        if 'dismissed_alerts' not in session:
            session['dismissed_alerts'] = []
        
        if alert_type not in session['dismissed_alerts']:
            session['dismissed_alerts'].append(alert_type)
            session.permanent = True
        
        return jsonify({'success': True, 'message': 'Alert dismissed successfully'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
from flask import jsonify, session
from flask_login import login_required
from ...services.dashboard_alerts import DashboardAlertService
from . import api_bp

@api_bp.route('/dashboard-alerts')
@login_required
def get_dashboard_alerts():
    """API endpoint for dashboard alerts"""
    dismissed_alerts = session.get('dismissed_alerts', [])
    alert_data = DashboardAlertService.get_dashboard_alerts(
        max_alerts=3,
        dismissed_alerts=dismissed_alerts
    )
    return jsonify(alert_data)

@api_bp.route('/dismiss-alert', methods=['POST'])
@login_required 
def dismiss_alert():
    """API endpoint to dismiss an alert"""
    from flask import request
    
    data = request.get_json()
    alert_type = data.get('alert_type')
    
    if alert_type:
        dismissed_alerts = session.get('dismissed_alerts', [])
        if alert_type not in dismissed_alerts:
            dismissed_alerts.append(alert_type)
        session['dismissed_alerts'] = dismissed_alerts
        session.permanent = True
    
    return jsonify({'success': True})
