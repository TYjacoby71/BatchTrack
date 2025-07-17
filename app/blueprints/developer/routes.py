
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import Organization, User
from app.extensions import db

developer_bp = Blueprint('developer', __name__, url_prefix='/developer')

@developer_bp.before_request
def require_developer():
    """Ensure only developers can access these routes"""
    if not current_user.is_authenticated or current_user.user_type != 'developer':
        flash('Developer access required', 'error')
        return redirect(url_for('auth.login'))

@developer_bp.route('/organizations')
@login_required
def organizations():
    """Developer dashboard for viewing and selecting organizations"""
    organizations = Organization.query.all()
    selected_org_id = session.get('dev_selected_org_id')
    selected_org = None
    
    if selected_org_id:
        selected_org = Organization.query.get(selected_org_id)
    
    return render_template('developer/organizations.html', 
                         organizations=organizations,
                         selected_org=selected_org)

@developer_bp.route('/select-org/<int:org_id>')
@login_required
def select_organization(org_id):
    """Select an organization to view as developer"""
    org = Organization.query.get_or_404(org_id)
    session['dev_selected_org_id'] = org_id
    flash(f'Now viewing data for: {org.name}', 'success')
    return redirect(url_for('app_routes.dashboard'))

@developer_bp.route('/clear-org-filter')
@login_required
def clear_organization_filter():
    """Clear organization filter and view all data"""
    session.pop('dev_selected_org_id', None)
    flash('Organization filter cleared - viewing all data', 'info')
    return redirect(url_for('app_routes.dashboard'))

@developer_bp.route('/api/organizations')
@login_required
def api_organizations():
    """API endpoint for organization data"""
    organizations = Organization.query.all()
    return jsonify({
        'organizations': [{
            'id': org.id,
            'name': org.name,
            'subscription_tier': org.subscription_tier,
            'user_count': len(org.users),
            'active_user_count': org.active_users_count
        } for org in organizations],
        'selected_org_id': session.get('dev_selected_org_id')
    })
