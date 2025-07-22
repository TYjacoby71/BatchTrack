from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from ...models import Organization, User, Batch, Recipe, InventoryItem
from ...extensions import db
from ...utils.permissions import require_permission

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/organizations')
@login_required
@require_permission('system.admin')
def list_organizations():
    """List all organizations for system admin"""
    organizations = Organization.query.all()
    return render_template('admin/organizations.html', organizations=organizations)

@admin_bp.route('/organizations/<int:org_id>')
@login_required
@require_permission('system.admin')
def view_organization(org_id):
    """View specific organization details"""
    org = Organization.query.get_or_404(org_id)
    users = User.query.filter_by(organization_id=org_id).all()
    return render_template('admin/organization_detail.html', organization=org, users=users)