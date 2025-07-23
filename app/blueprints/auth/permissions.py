from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from app.models import Permission, Role, User
from app.extensions import db
from app.utils.permissions import require_permission
from app.blueprints.developer.subscription_tiers import load_tiers_config

def get_tier_permissions(tier_key):
    """Get all permissions available to a subscription tier"""
    tiers_config = load_tiers_config()
    tier_data = tiers_config.get(tier_key, {})
    permission_names = tier_data.get('permissions', [])

    # Get actual permission objects
    permissions = Permission.query.filter(
        Permission.name.in_(permission_names),
        Permission.is_active == True
    ).all()
    return permissions

@require_permission('dev.system_admin')
@login_required
def manage_permissions():
    """Show system permissions management page"""
    # Get both developer permissions and organization permissions
    dev_permissions = DeveloperPermission.query.all()
    org_permissions = Permission.query.all()

    # Combine all permissions with type indicator
    all_permissions = []

    # Add developer permissions
    for perm in dev_permissions:
        all_permissions.append({
            'id': perm.id,
            'name': perm.name,
            'description': perm.description,
            'category': perm.category or 'general',
            'is_active': perm.is_active,
            'type': 'developer',
            'table': 'developer_permission'
        })

    # Add organization permissions
    for perm in org_permissions:
        all_permissions.append({
            'id': perm.id,
            'name': perm.name,
            'description': perm.description,
            'category': perm.category or 'general',
            'is_active': perm.is_active,
            'type': 'organization',
            'table': 'permission'
        })

    # Organize by category
    permission_categories = {}
    for perm in all_permissions:
        category = perm['category']
        if category not in permission_categories:
            permission_categories[category] = []
        permission_categories[category].append(perm)

    # Sort categories and permissions within each category
    for category in permission_categories:
        permission_categories[category].sort(key=lambda x: x['name'])

    return render_template('auth/permissions.html', 
                         permission_categories=permission_categories)

@require_permission('dev.system_admin')
@login_required
def toggle_permission_status():
    """Toggle active/inactive status of a permission"""
    data = request.get_json()
    permission_id = data.get('permission_id')
    permission_table = data.get('table')
    new_status = data.get('is_active')

    try:
        if permission_table == 'developer_permission':
            permission = DeveloperPermission.query.get_or_404(permission_id)
        elif permission_table == 'permission':
            permission = Permission.query.get_or_404(permission_id)
        else:
            return jsonify({'success': False, 'message': 'Invalid permission table'})

        permission.is_active = new_status
        db.session.commit()

        status_text = 'activated' if new_status else 'deactivated'
        return jsonify({
            'success': True, 
            'message': f'Permission "{permission.name}" {status_text} successfully'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error updating permission: {str(e)}'})

@require_permission('organization.manage_roles')
@login_required
def manage_roles():
    """Manage roles (org owners and system admins)"""
    if current_user.user_type == 'developer':
        # System admin can see all roles and all permissions
        roles = Role.query.all()
        available_permissions = Permission.query.filter_by(is_active=True).all()
    else:
        # Organization owners see their org roles + system roles
        roles = Role.get_organization_roles(current_user.organization_id)
        # Only show permissions available to their subscription tier
        available_permissions = get_tier_permissions(current_user.organization.effective_subscription_tier)

    return render_template('auth/roles.html', roles=roles, available_permissions=available_permissions)

@require_permission('organization.manage_roles')
@login_required
def create_role():
    """Create new role"""
    try:
        data = request.get_json()

        role = Role(
            name=data['name'],
            description=data.get('description'),
            organization_id=current_user.organization_id if current_user.user_type != 'developer' else None,
            created_by=current_user.id
        )

        # Add permissions - but only allow permissions available to the organization's tier
        permission_ids = data.get('permission_ids', [])

        if current_user.user_type == 'developer':
            # Developers can assign any permission
            permissions = Permission.query.filter(Permission.id.in_(permission_ids)).all()
        else:
            # Organization users can only assign permissions included in their tier
            available_permissions = get_tier_permissions(current_user.organization.effective_subscription_tier)
            available_permission_ids = [p.id for p in available_permissions]
            # Filter requested permissions to only include those available to the tier
            filtered_permission_ids = [pid for pid in permission_ids if pid in available_permission_ids]
            permissions = Permission.query.filter(Permission.id.in_(filtered_permission_ids)).all()

        role.permissions = permissions

        db.session.add(role)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Role created successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@require_permission('organization.manage_roles')
@login_required
def update_role(role_id):
    """Update role"""
    try:
        role = Role.query.get_or_404(role_id)

        # Check permissions
        if role.is_system_role and current_user.user_type != 'developer':
            return jsonify({'success': False, 'error': 'Cannot edit system roles'})

        if role.organization_id != current_user.organization_id and current_user.user_type != 'developer':
            return jsonify({'success': False, 'error': 'Cannot edit roles from other organizations'})

        data = request.get_json()

        role.name = data.get('name', role.name)
        role.description = data.get('description', role.description)

        # Update permissions
        if 'permission_ids' in data:
            permission_ids = data['permission_ids']
            permissions = Permission.query.filter(Permission.id.in_(permission_ids)).all()
            role.permissions = permissions

        db.session.commit()

        return jsonify({'success': True, 'message': 'Role updated successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})