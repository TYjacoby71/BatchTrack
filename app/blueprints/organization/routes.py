from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app as app, abort
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
import secrets
import re
from datetime import timedelta
from app.models import User, Organization, Role, Permission
from app.extensions import db
from app.utils.permissions import require_permission, has_permission
from app.utils.timezone_utils import TimezoneUtils

organization_bp = Blueprint('organization', __name__)

@organization_bp.route('/dashboard')
@login_required
def dashboard():
    """Organization management dashboard"""
    # First check subscription tier - only team, enterprise, and exempt should have access
    effective_tier = current_user.organization.effective_subscription_tier
    if effective_tier in ['free', 'solo']:
        flash('Organization dashboard is available with Team and Enterprise plans.', 'info')
        return redirect(url_for('settings.index'))

    # Organization owners automatically have access to dashboard for allowed tiers
    if current_user.user_type == 'organization_owner' or current_user.is_organization_owner:
        pass  # Access granted
    # Developers have access
    elif current_user.user_type == 'developer':
        pass  # Access granted
    # Team members need the manage_organization permission
    else:
        if not has_permission(current_user, 'manage_organization'):
            flash('You do not have permission to access the organization dashboard.', 'error')
            return redirect(url_for('settings.index'))

    from ...services.pricing_service import PricingService
    pricing_data = PricingService.get_pricing_data()

    # Get organization data
    organization = current_user.organization

    # Get organization statistics
    from app.models import Batch
    completed_batches = Batch.query.filter_by(
        organization_id=current_user.organization_id,
        status='completed'
    ).count()

    failed_batches = Batch.query.filter_by(
        organization_id=current_user.organization_id,
        status='failed'
    ).count()

    org_stats = {
        'completed_batches': completed_batches,
        'failed_batches': failed_batches
    }

    # Count pending invites (inactive users)
    pending_invites = User.query.filter_by(
        organization_id=current_user.organization_id,
        is_active=False,
        user_type='team_member'
    ).count()

    # Get permission categories for role creation modal
    from app.models.permission import Permission
    permissions = Permission.query.filter_by(is_active=True).all()
    permission_categories = {}
    for perm in permissions:
        category = perm.category or 'general'
        if category not in permission_categories:
            permission_categories[category] = []
        permission_categories[category].append(perm)

    # Get roles for the roles tab  
    roles = Role.get_organization_roles(current_user.organization_id)

    # Get users for the user management tab (exclude developers from organization view)
    users = User.query.filter(
        User.organization_id == current_user.organization_id,
        User.user_type != 'developer'
    ).order_by(User.created_at.desc()).all()

    # Debug: Print to console to verify data
    print(f"Permission categories: {list(permission_categories.keys())}")
    print(f"Total permissions: {len(permissions)}")
    print(f"Roles count: {len(roles)}")
    print(f"Users count: {len(users)}")

    return render_template(
        'organization/dashboard.html', 
        pricing_data=pricing_data,
        organization=organization,
        org_stats=org_stats,
        pending_invites=pending_invites,
        permission_categories=permission_categories,
        roles=roles,
        users=users
    )

@organization_bp.route('/create-role', methods=['POST'])
@login_required
def create_role():
    """Create a new organization role"""
    # Check if user is organization owner or developer
    if not (current_user.user_type == 'organization_owner' or 
            current_user.is_organization_owner or 
            current_user.user_type == 'developer'):
        return jsonify({'success': False, 'error': 'Insufficient permissions'})

    try:
        data = request.get_json()

        # Get organization
        from flask import session
        if current_user.user_type == 'developer' and session.get('dev_selected_org_id'):
            from app.models import Organization
            organization = Organization.query.get(session.get('dev_selected_org_id'))
            org_id = organization.id
        else:
            org_id = current_user.organization_id

        # Create role
        role = Role(
            name=data['name'],
            description=data.get('description'),
            organization_id=org_id,
            created_by=current_user.id,
            is_system_role=False
        )

        # Add permissions
        permission_ids = data.get('permission_ids', [])
        from app.models.permission import Permission
        permissions = Permission.query.filter(Permission.id.in_(permission_ids)).all()
        role.permissions = permissions

        db.session.add(role)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Role created successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@organization_bp.route('/update-settings', methods=['POST'])
@login_required
def update_organization_settings():
    """Update organization settings (organization owners only)"""

    # Check permissions - only organization owners can update
    if not (current_user.user_type == 'organization_owner' or 
            current_user.is_organization_owner):
        return jsonify({'success': False, 'error': 'Insufficient permissions'})

    try:
        data = request.get_json()
        organization = current_user.organization

        if not organization:
            return jsonify({'success': False, 'error': 'No organization found'})

        # Update organization fields
        if 'name' in data and data['name'].strip():
            organization.name = data['name'].strip()

        if 'contact_email' in data:
            # If contact_email is empty, use current user's email as default
            contact_email = data['contact_email'].strip() if data['contact_email'] else current_user.email
            organization.contact_email = contact_email

        if 'timezone' in data:
            organization.timezone = data['timezone']

        db.session.commit()

        return jsonify({'success': True, 'message': 'Organization settings updated successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@organization_bp.route('/invite-user', methods=['POST'])
@login_required
def invite_user():
    """Invite a new user to the organization"""
    # Check if user is organization owner - developers can access for testing but normal team members cannot
    if not (current_user.user_type == 'organization_owner' or 
            current_user.is_organization_owner or 
            current_user.user_type == 'developer'):
        return jsonify({'success': False, 'error': 'Insufficient permissions to invite users'})
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

        if role.name in ['developer', 'organization_owner']:
            return jsonify({'success': False, 'error': 'Cannot assign system or organization owner roles to invited users'})

        # Check if user should be added as inactive due to subscription limits
        force_inactive = data.get('force_inactive', False)
        will_be_inactive = force_inactive or not current_user.organization.can_add_users()

        if not current_user.organization.can_add_users() and not force_inactive:
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

        # Create new user (inactive if subscription limit reached)
        new_user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            organization_id=current_user.organization_id,
            is_active=not will_be_inactive,  # Inactive if subscription limit reached
            user_type='team_member'
        )
        new_user.set_password(temp_password)

        db.session.add(new_user)
        db.session.commit()

        # Assign role using the new role assignment system
        new_user.assign_role(role, assigned_by=current_user)

        # TODO: In a real implementation, send email with login details
        # For now, we'll return the credentials directly

        status_message = "User invited successfully!"
        if will_be_inactive:
            status_message += " User added as inactive due to subscription limits."

        return jsonify({
            'success': True, 
            'message': f'{status_message} Login details - Username: {username}, Temporary password: {temp_password}',
            'user_data': {
                'username': username,
                'email': email,
                'full_name': new_user.full_name,
                'role': role.name,
                'temp_password': temp_password,  # Remove this in production
                'is_active': new_user.is_active
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
def add_user():
    """Add a new user to the organization (org owners only) - legacy endpoint"""
    # Check if user is organization owner - developers can access for testing but normal team members cannot
    if not (current_user.user_type == 'organization_owner' or 
            current_user.is_organization_owner or 
            current_user.user_type == 'developer'):
        return jsonify({'success': False, 'error': 'Insufficient permissions to add users'})
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

# User Management Routes

@organization_bp.route('/user/<int:user_id>', methods=['GET'])
@login_required
def get_user(user_id):
    """Get user details for editing"""
    user = User.query.filter_by(
        id=user_id, 
        organization_id=current_user.organization_id
    ).first()

    if not user:
        return jsonify({'success': False, 'error': 'User not found'})

    # Don't allow editing of developers or other org owners (except self)
    if user.user_type in ['developer', 'organization_owner'] and user.id != current_user.id:
        return jsonify({'success': False, 'error': 'Cannot edit system users or other organization owners'})

    # Get user's role assignments
    role_assignments = []
    for assignment in user.role_assignments:
        if assignment.is_active:
            role_assignments.append({
                'role_id': assignment.role_id,
                'role_name': assignment.role.name,
                'assigned_at': assignment.assigned_at.isoformat() if assignment.assigned_at else None
            })

    return jsonify({
        'success': True,
        'user': {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'phone': user.phone,
            'is_active': user.is_active,
            'user_type': user.user_type,
            'role_assignments': role_assignments
        }
    })

@organization_bp.route('/user/<int:user_id>', methods=['PUT'])
@login_required
def update_user(user_id):
    """Update user details (organization owners only)"""

    # Check permissions - only organization owners can update
    if not (current_user.user_type == 'organization_owner' or 
            current_user.is_organization_owner):
        return jsonify({'success': False, 'error': 'Insufficient permissions'})

    try:
        data = request.get_json()

        # Get user from same organization
        user = User.query.filter_by(
            id=user_id, 
            organization_id=current_user.organization_id
        ).first()

        if not user:
            return jsonify({'success': False, 'error': 'User not found'})

        # Don't allow editing of developers or other org owners (except self)
        if user.user_type in ['developer', 'organization_owner'] and user.id != current_user.id:
            return jsonify({'success': False, 'error': 'Cannot edit system users or other organization owners'})

        # Update user fields
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'email' in data:
            user.email = data['email']
        if 'phone' in data:
            user.phone = data['phone']
        if 'role_id' in data:
            # Validate role exists and is not developer role
            role = Role.query.filter_by(id=data['role_id']).first()
            if role and role.name not in ['developer', 'organization_owner']:
                user.role_id = data['role_id']

        # Handle status changes - check subscription limits for activation
        if 'is_active' in data:
            new_status = data['is_active']
            if new_status and not user.is_active:  # Activating user
                if not current_user.organization.can_add_users():
                    current_count = current_user.organization.active_users_count
                    max_users = current_user.organization.get_max_users()
                    return jsonify({
                        'success': False, 
                        'error': f'Cannot activate user. Organization has reached user limit ({current_count}/{max_users}) for {current_user.organization.subscription_tier} subscription'
                    })
            user.is_active = new_status

        db.session.commit()

        return jsonify({
            'success': True, 
            'message': f'User {user.full_name} updated successfully'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@organization_bp.route('/user/<int:user_id>/toggle-status', methods=['POST'])
@login_required
def toggle_user_status(user_id):
    """Toggle user active/inactive status (organization owners only)"""

    # Check permissions - only organization owners can toggle status
    if not (current_user.user_type == 'organization_owner' or 
            current_user.is_organization_owner):
        return jsonify({'success': False, 'error': 'Insufficient permissions'})

    try:
        # Get user from same organization
        user = User.query.filter_by(
            id=user_id, 
            organization_id=current_user.organization_id
        ).first()

        if not user:
            return jsonify({'success': False, 'error': 'User not found'})

        # Don't allow toggling status of developers, org owners, or self
        if user.user_type in ['developer', 'organization_owner']:
            return jsonify({'success': False, 'error': 'Cannot change status of system users or organization owners'})

        if user.id == current_user.id:
            return jsonify({'success': False, 'error': 'Cannot change your own status'})

        # Toggle status
        new_status = not user.is_active

        # If activating, check subscription limits
        if new_status and not user.is_active:
            if not current_user.organization.can_add_users():
                current_count = current_user.organization.active_users_count
                max_users = current_user.organization.get_max_users()
                return jsonify({
                    'success': False, 
                    'error': f'Cannot activate user. Organization has reached user limit ({current_count}/{max_users}) for {current_user.organization.subscription_tier} subscription'
                })

        user.is_active = new_status
        db.session.commit()

        status_text = 'activated' if new_status else 'deactivated'
        return jsonify({
            'success': True, 
            'message': f'User {user.full_name} {status_text} successfully'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@organization_bp.route('/user/<int:user_id>', methods=['DELETE'])
@login_required
def delete_user(user_id):
    """Delete user permanently (organization owners only)"""

    # Check permissions - only organization owners can delete
    if not (current_user.user_type == 'organization_owner' or 
            current_user.is_organization_owner):
        return jsonify({'success': False, 'error': 'Insufficient permissions'})

    try:
        # Get user from same organization
        user = User.query.filter_by(
            id=user_id, 
            organization_id=current_user.organization_id
        ).first()

        if not user:
            return jsonify({'success': False, 'error': 'User not found'})

        # Don't allow deleting developers, org owners, or self
        if user.user_type in ['developer', 'organization_owner']:
            return jsonify({'success': False, 'error': 'Cannot delete system users or organization owners'})

        if user.id == current_user.id:
            return jsonify({'success': False, 'error': 'Cannot delete yourself'})

        username = user.username
        full_name = user.full_name

        # Soft delete the user (preserves all historical data)
        user.soft_delete(deleted_by_user=current_user)

        return jsonify({
            'success': True, 
            'message': f'User {full_name} ({username}) removed successfully (can be restored if needed)'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@organization_bp.route('/user/<int:user_id>/restore', methods=['POST'])
@login_required
def restore_user(user_id):
    """Restore a soft-deleted user (organization owners only)"""

    # Check permissions - only organization owners can restore
    if not (current_user.user_type == 'organization_owner' or 
            current_user.is_organization_owner):
        return jsonify({'success': False, 'error': 'Insufficient permissions'})

    try:
        # Get user from same organization (including deleted users)
        user = User.query.filter_by(
            id=user_id, 
            organization_id=current_user.organization_id
        ).first()

        if not user:
            return jsonify({'success': False, 'error': 'User not found'})

        if not user.is_deleted:
            return jsonify({'success': False, 'error': 'User is not deleted'})

        username = user.username
        full_name = user.full_name

        # Restore the user
        user.restore(restored_by_user=current_user)

        return jsonify({
            'success': True, 
            'message': f'User {full_name} ({username}) restored successfully (needs manual activation and role assignment)'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})