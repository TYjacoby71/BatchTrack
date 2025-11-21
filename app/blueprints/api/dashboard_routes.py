from flask import Blueprint, jsonify, request, session
from flask_login import login_required, current_user
from app.services.dashboard_alerts import DashboardAlertService
from app.utils.permissions import require_permission
from app.extensions import db
from app.models.batch import Batch
from app.models.models import User
from app.models.inventory import InventoryItem
from app.utils.timezone_utils import TimezoneUtils
from datetime import datetime, timedelta
import logging

dashboard_api_bp = Blueprint('dashboard_api', __name__, url_prefix='/api')

@dashboard_api_bp.route('/dashboard-alerts')
@login_required
def get_dashboard_alerts():
    """Get dashboard alerts for current user's organization"""
    try:
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

@dashboard_api_bp.route('/dismiss-alert', methods=['POST'])
@login_required 
def dismiss_alert():
    """Dismiss an alert"""
    try:
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

@dashboard_api_bp.route('/clear-dismissed-alerts', methods=['POST'])
@login_required 
def clear_dismissed_alerts():
    """Clear all dismissed alerts from session"""
    try:
        session.pop('dismissed_alerts', None)
        return jsonify({'success': True, 'message': 'All dismissed alerts cleared'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@dashboard_api_bp.route('/batches')
@dashboard_api_bp.route('/dashboard/batches')
@login_required
def get_dashboard_batches():
    """Get batches summary for dashboard"""
    try:
        # Get batches for the user's organization
        org_filter = {}
        if hasattr(current_user, 'organization_id') and current_user.organization_id:
            org_filter['organization_id'] = current_user.organization_id

        batches = Batch.query.filter_by(**org_filter).limit(50).all()
        
        # Convert batches to dictionaries for JSON serialization
        batch_list = []
        for batch in batches:
            batch_data = {
                'id': batch.id,
                'name': batch.name,
                'status': batch.status,
                'created_at': batch.created_at.isoformat() if batch.created_at else None,
                'updated_at': batch.updated_at.isoformat() if batch.updated_at else None,
            }
            batch_list.append(batch_data)

        # Calculate stats
        completed_today = [b for b in batches if b.status == 'completed' and b.updated_at and b.updated_at.date() == datetime.utcnow().date()]

        return jsonify({
            'batches': batch_list,
            'stats': {
                'total_batches': len(batch_list),
                'active_batches': len([b for b in batch_list if b['status'] == 'in_progress']),
                'completed_today': len(completed_today)
            }
        })

    except Exception as e:
        logging.error(f"Error getting dashboard batches: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@dashboard_api_bp.route('/inventory')
@dashboard_api_bp.route('/dashboard/inventory')
@login_required
def get_dashboard_inventory():
    """Get inventory summary for dashboard"""
    try:
        # Get inventory items for the user's organization
        org_filter = {}
        if hasattr(current_user, 'organization_id') and current_user.organization_id:
            org_filter['organization_id'] = current_user.organization_id

        inventory_items = InventoryItem.query.filter_by(**org_filter).limit(50).all()

        items = []
        for item in inventory_items:
            items.append({
                'id': item.id,
                'name': item.name,
                'category': item.category,
                'quantity': float(item.quantity) if item.quantity else 0.0,
                'unit': item.unit.name if item.unit else 'units',
                'last_updated': item.updated_at.isoformat() if item.updated_at else None
            })

        return jsonify({
            'inventory': items,
            'stats': {
                'total_items': len(items),
                'low_stock': len([i for i in items if i['quantity'] < 10]),
                'categories': len(set(i['category'] for i in items if i['category']))
            }
        })

    except Exception as e:
        logging.error(f"Error getting dashboard inventory: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500