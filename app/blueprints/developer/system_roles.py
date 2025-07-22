
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.models import Role, Permission
from app.extensions import db

system_roles_bp = Blueprint('system_roles', __name__)

@system_roles_bp.before_request
def require_developer():
    """Ensure only developers can access these routes"""
    if not current_user.is_authenticated or current_user.user_type != 'developer':
        return jsonify({'error': 'Developer access required'}), 403

@system_roles_bp.route('/system-roles')
@login_required
def manage_system_roles():
    """Manage system roles (developer only)"""
    system_roles = Role.query.filter_by(is_system_role=True).all()
    return render_template('developer/system_roles.html', roles=system_roles)

@system_roles_bp.route('/system-roles', methods=['POST'])
@login_required
def create_system_role():
    """Create new system role"""
    try:
        data = request.get_json()
        
        # Check if role name already exists
        existing_role = Role.query.filter_by(name=data['name'], is_system_role=True).first()
        if existing_role:
            return jsonify({'success': False, 'error': 'System role with this name already exists'})
        
        role = Role(
            name=data['name'],
            description=data.get('description'),
            is_system_role=True,
            organization_id=None,
            created_by=current_user.id
        )
        
        # Add permissions
        permission_ids = data.get('permission_ids', [])
        permissions = Permission.query.filter(Permission.id.in_(permission_ids)).all()
        role.permissions = permissions
        
        db.session.add(role)
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'System role "{role.name}" created successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@system_roles_bp.route('/system-roles/<int:role_id>', methods=['GET'])
@login_required
def get_system_role(role_id):
    """Get system role details"""
    role = Role.query.filter_by(id=role_id, is_system_role=True).first_or_404()
    
    return jsonify({
        'success': True,
        'role': {
            'id': role.id,
            'name': role.name,
            'description': role.description,
            'permission_ids': [perm.id for perm in role.permissions]
        }
    })

@system_roles_bp.route('/system-roles/<int:role_id>', methods=['PUT'])
@login_required
def update_system_role(role_id):
    """Update system role"""
    try:
        role = Role.query.filter_by(id=role_id, is_system_role=True).first_or_404()
        
        # Don't allow editing organization_owner role
        if role.name == 'organization_owner':
            return jsonify({'success': False, 'error': 'Cannot edit organization_owner system role'})
        
        data = request.get_json()
        
        role.name = data.get('name', role.name)
        role.description = data.get('description', role.description)
        
        # Update permissions
        if 'permission_ids' in data:
            permission_ids = data['permission_ids']
            permissions = Permission.query.filter(Permission.id.in_(permission_ids)).all()
            role.permissions = permissions
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'System role "{role.name}" updated successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@system_roles_bp.route('/system-roles/<int:role_id>', methods=['DELETE'])
@login_required
def delete_system_role(role_id):
    """Delete system role"""
    try:
        role = Role.query.filter_by(id=role_id, is_system_role=True).first_or_404()
        
        # Don't allow deleting organization_owner role
        if role.name == 'organization_owner':
            return jsonify({'success': False, 'error': 'Cannot delete organization_owner system role'})
        
        db.session.delete(role)
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'System role "{role.name}" deleted successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@system_roles_bp.route('/permissions/api')
@login_required
def get_permissions_api():
    """API endpoint for permissions grouped by category"""
    permissions = Permission.query.filter_by(is_active=True).all()
    categories = {}
    
    for perm in permissions:
        category = perm.category or 'general'
        if category not in categories:
            categories[category] = []
        categories[category].append({
            'id': perm.id,
            'name': perm.name,
            'description': perm.description,
            'tier': perm.required_subscription_tier
        })
    
    return jsonify({'categories': categories})
