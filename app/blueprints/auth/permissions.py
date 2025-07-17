
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from app.models import Permission, Role, User
from app.extensions import db
from app.utils.permissions import require_permission

@require_permission('system.admin')
@login_required
def manage_permissions():
    """Manage system permissions (system admin only)"""
    permissions = Permission.query.all()
    permission_categories = {}
    for perm in permissions:
        category = perm.category or 'general'
        if category not in permission_categories:
            permission_categories[category] = []
        permission_categories[category].append(perm)
    
    return render_template('auth/permissions.html',
                         permissions=permissions,
                         permission_categories=permission_categories)

@require_permission('organization.manage_roles')
@login_required
def manage_roles():
    """Manage roles (org owners and system admins)"""
    if current_user.user_type == 'developer':
        # System admin can see all roles
        roles = Role.query.all()
    else:
        # Organization owners see their org roles + system roles
        roles = Role.get_organization_roles(current_user.organization_id)
    
    return render_template('auth/roles.html', roles=roles)

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
        
        # Add permissions
        permission_ids = data.get('permission_ids', [])
        permissions = Permission.query.filter(Permission.id.in_(permission_ids)).all()
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
