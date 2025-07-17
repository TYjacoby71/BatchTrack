
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from ...extensions import db
from ...models import User, Organization
from ...utils.permissions import require_permission
from ...models.role import Role
from ...models.permission import Permission
import re
import secrets

organization_bp = Blueprint('organization', __name__)

@organization_bp.route('/dashboard')
@login_required
def dashboard():
    """Organization dashboard for managing users, roles, and settings (organization owners only)"""

    # Check if user is organization owner - developers can access for testing but normal team members cannot
    if not (current_user.user_type == 'organization_owner' or 
            current_user.is_organization_owner or 
            current_user.user_type == 'developer'):
        abort(403)

    # Get organization data
    organization = current_user.organization
    if not organization:
        flash('No organization found', 'error')
        return redirect(url_for('settings.index'))

    # Get users for this organization, explicitly excluding developers
    users = User.query.filter(
        User.organization_id == current_user.organization_id,
        User.user_type != 'developer'
    ).all()

    # Get organization-appropriate roles (exclude developer role)
    roles = Role.query.filter(Role.name != 'developer').all()
    for role in roles:
        # Add assigned users count to each role
        role.assigned_users = User.query.filter_by(role_id=role.id, organization_id=organization.id).all()

    # Get permissions grouped by category
    permissions = Permission.query.all()
    permission_categories = {}
    for perm in permissions:
        category = perm.category or 'general'
        if category not in permission_categories:
            permission_categories[category] = []
        permission_categories[category].append(perm)

    # Get some basic metrics
    total_batches = 0  # You can add actual batch count logic here if needed
    pending_invites = 0  # You can add actual pending invites count here if needed
    recent_activity = []  # You can add actual recent activity here if needed

    return render_template('settings/org_dashboard.html',
                         organization=organization,
                         users=users,
                         roles=roles,
                         permissions=permissions,
                         permission_categories=permission_categories,
                         total_batches=total_batches,
                         pending_invites=pending_invites,
                         recent_activity=recent_activity)

@organization_bp.route('/invite-user', methods=['POST'])
@login_required
@require_permission('organization.manage')
def invite_user():
    """Invite a new user to the organization"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'})

        # Validate required fields
        email = data.get('email', '').strip()
        role_id = data.get('role_id')
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        phone = data.get('phone', '').strip()

        if not email or not role_id:
            return jsonify({'success': False, 'error': 'Email and role are required'})

        # Validate email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return jsonify({'success': False, 'error': 'Invalid email format'})

        # Check if user already exists (by email or username)
        existing_user = User.query.filter(
            (User.email == email) | (User.username == email)
        ).first()
        if existing_user:
            return jsonify({'success': False, 'error': 'User with this email already exists'})

        # Validate role exists and is not developer role
        role = Role.query.filter_by(id=role_id).first()
        if not role:
            return jsonify({'success': False, 'error': 'Invalid role selected'})
        
        if role.name == 'developer':
            return jsonify({'success': False, 'error': 'Cannot assign developer role to organization users'})

        # Check if organization can add more users
        if not current_user.organization.can_add_users():
            current_count = current_user.organization.active_users_count
            max_users = current_user.organization.get_max_users()
            return jsonify({
                'success': False, 
                'error': f'Organization has reached user limit ({current_count}/{max_users}) for {current_user.organization.subscription_tier} subscription'
            })

        # Generate a unique username from email
        username = email.split('@')[0]
        counter = 1
        original_username = username
        while User.query.filter_by(username=username).first():
            username = f"{original_username}{counter}"
            counter += 1

        # Create new user with temporary password
        temp_password = secrets.token_urlsafe(12)

        # Create new user
        new_user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role_id=role_id,
            organization_id=current_user.organization_id,
            is_active=True,
            user_type='team_member',
            is_owner=False
        )
        new_user.set_password(temp_password)

        db.session.add(new_user)
        db.session.commit()

        # TODO: In a real implementation, send email with login details
        # For now, we'll return the credentials directly
        
        return jsonify({
            'success': True, 
            'message': f'User invited successfully! Login details - Username: {username}, Temporary password: {temp_password}',
            'user_data': {
                'username': username,
                'email': email,
                'full_name': new_user.full_name,
                'role': role.name,
                'temp_password': temp_password  # Remove this in production
            }
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error inviting user: {str(e)}")  # For debugging
        return jsonify({'success': False, 'error': f'Failed to invite user: {str(e)}'})

@organization_bp.route('/update', methods=['POST'])
@login_required
def update_organization():
    """Update organization settings"""
    
    # Check permissions
    if not (current_user.user_type == 'organization_owner' or 
            current_user.is_organization_owner or 
            current_user.user_type == 'developer'):
        return jsonify({'success': False, 'error': 'Insufficient permissions'})
        
    try:
        data = request.get_json()
        organization = current_user.organization

        # Update organization fields
        if 'name' in data:
            organization.name = data['name']

        # Add other organization settings here as needed

        db.session.commit()

        return jsonify({'success': True, 'message': 'Organization settings updated'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@organization_bp.route('/export/<report_type>')
@login_required
def export_report(report_type):
    """Export various organization reports"""
    
    # Check permissions - only org owners and developers can export
    if not (current_user.user_type == 'organization_owner' or 
            current_user.is_organization_owner or 
            current_user.user_type == 'developer'):
        abort(403)
        
    try:
        if report_type == 'users':
            # Export users CSV - exclude developers from org exports
            users = User.query.filter(
                User.organization_id == current_user.organization_id,
                User.user_type != 'developer'
            ).all()
            flash('User export functionality coming soon', 'info')
        elif report_type == 'batches':
            flash('Batch export functionality coming soon', 'info')
        elif report_type == 'inventory':
            flash('Inventory export functionality coming soon', 'info')
        elif report_type == 'products':
            flash('Product export functionality coming soon', 'info')
        elif report_type == 'activity':
            flash('Activity export functionality coming soon', 'info')
        else:
            flash('Unknown report type', 'error')

        return redirect(url_for('organization.dashboard'))

    except Exception as e:
        flash(f'Export error: {str(e)}', 'error')
        return redirect(url_for('organization.dashboard'))

@organization_bp.route('/add-user', methods=['POST'])
@login_required
@require_permission('organization.manage')
def add_user():
    """Add a new user to the organization (org owners only) - legacy endpoint"""
    try:
        data = request.get_json()

        # Validate required fields
        username = data.get('username')
        email = data.get('email') 
        password = data.get('password')
        role_id = data.get('role_id')

        if not all([username, email, password, role_id]):
            return jsonify({'success': False, 'error': 'All fields are required'})

        # Check if user already exists
        if User.query.filter_by(username=username).first():
            return jsonify({'success': False, 'error': 'Username already exists'})

        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'error': 'Email already exists'})

        # Check if organization can add more users
        if not current_user.organization.can_add_users():
            return jsonify({'success': False, 'error': 'Organization has reached user limit for current subscription'})

        # Create new user
        new_user = User(
            username=username,
            email=email,
            role_id=role_id,
            organization_id=current_user.organization_id,
            is_active=True,
            user_type='team_member'
        )
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        return jsonify({'success': True, 'message': 'User added successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

# Management route removed - use dashboard instead
