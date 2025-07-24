
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.models import Role, Permission, User, Organization
from app.models.developer_role import DeveloperRole
from app.models.developer_permission import DeveloperPermission
from app.models.user_role_assignment import UserRoleAssignment
from app.extensions import db
from werkzeug.security import generate_password_hash

system_roles_bp = Blueprint('system_roles', __name__)

@system_roles_bp.before_request
def require_developer():
    """Ensure only developers can access these routes"""
    if not current_user.is_authenticated or current_user.user_type != 'developer':
        return jsonify({'error': 'Developer access required'}), 403

@system_roles_bp.route('/system-roles')
@login_required
def manage_system_roles():
    """Manage system roles and developer users"""
    system_roles = Role.query.filter_by(is_system_role=True).all()
    developer_roles = DeveloperRole.query.filter_by(is_active=True).all()
    developer_users = User.query.filter_by(user_type='developer').all()
    
    return render_template('developer/system_roles.html', 
                         roles=system_roles,
                         developer_roles=developer_roles,
                         developer_users=developer_users)

# System Role Management (Organization Roles)
@system_roles_bp.route('/system-roles', methods=['POST'])
@login_required
def create_system_role():
    """Create new system role (organization role)"""
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
        
        data = request.get_json()
        
        # Allow editing name and description for all roles except organization_owner name
        if role.name != 'organization_owner':
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
        
        # Allow deletion of any system role (with warning for organization_owner)
        db.session.delete(role)
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'System role "{role.name}" deleted successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

# Developer Role Management
@system_roles_bp.route('/developer-roles', methods=['POST'])
@login_required
def create_developer_role():
    """Create new developer role"""
    try:
        data = request.get_json()
        
        # Check if role name already exists
        existing_role = DeveloperRole.query.filter_by(name=data['name']).first()
        if existing_role:
            return jsonify({'success': False, 'error': 'Developer role with this name already exists'})
        
        role = DeveloperRole(
            name=data['name'],
            description=data.get('description'),
            category=data.get('category', 'developer')
        )
        
        # Add permissions
        permission_ids = data.get('permission_ids', [])
        permissions = DeveloperPermission.query.filter(DeveloperPermission.id.in_(permission_ids)).all()
        role.permissions = permissions
        
        db.session.add(role)
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'Developer role "{role.name}" created successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@system_roles_bp.route('/developer-roles/<int:role_id>', methods=['GET'])
@login_required
def get_developer_role(role_id):
    """Get developer role details"""
    role = DeveloperRole.query.filter_by(id=role_id).first_or_404()
    
    return jsonify({
        'success': True,
        'role': {
            'id': role.id,
            'name': role.name,
            'description': role.description,
            'category': role.category,
            'permission_ids': [perm.id for perm in role.permissions]
        }
    })

@system_roles_bp.route('/developer-roles/<int:role_id>', methods=['PUT'])
@login_required
def update_developer_role(role_id):
    """Update developer role"""
    try:
        role = DeveloperRole.query.filter_by(id=role_id).first_or_404()
        
        data = request.get_json()
        
        role.name = data.get('name', role.name)
        role.description = data.get('description', role.description)
        role.category = data.get('category', role.category)
        
        # Update permissions
        if 'permission_ids' in data:
            permission_ids = data['permission_ids']
            permissions = DeveloperPermission.query.filter(DeveloperPermission.id.in_(permission_ids)).all()
            role.permissions = permissions
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'Developer role "{role.name}" updated successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@system_roles_bp.route('/developer-roles/<int:role_id>', methods=['DELETE'])
@login_required
def delete_developer_role(role_id):
    """Delete developer role"""
    try:
        role = DeveloperRole.query.filter_by(id=role_id).first_or_404()
        
        db.session.delete(role)
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'Developer role "{role.name}" deleted successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

# Developer User Management
@system_roles_bp.route('/developer-users', methods=['POST'])
@login_required
def create_developer_user():
    """Create new developer user"""
    try:
        data = request.get_json()
        
        # Check if username already exists
        existing_user = User.query.filter_by(username=data['username']).first()
        if existing_user:
            return jsonify({'success': False, 'error': 'Username already exists'})
        
        # Check if email already exists
        if data.get('email'):
            existing_email = User.query.filter_by(email=data['email']).first()
            if existing_email:
                return jsonify({'success': False, 'error': 'Email already exists'})
        
        user = User(
            username=data['username'],
            password_hash=generate_password_hash(data['password']),
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            email=data.get('email'),
            user_type='developer',
            organization_id=None,  # Developers don't belong to organizations
            is_active=True
        )
        
        db.session.add(user)
        db.session.flush()  # Get user ID
        
        # Assign developer role if specified
        developer_role_id = data.get('developer_role_id')
        if developer_role_id:
            developer_role = DeveloperRole.query.filter_by(id=developer_role_id).first()
            if developer_role:
                assignment = UserRoleAssignment(
                    user_id=user.id,
                    developer_role_id=developer_role.id,
                    organization_id=None,
                    assigned_by=current_user.id,
                    is_active=True
                )
                db.session.add(assignment)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'Developer user "{user.username}" created successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@system_roles_bp.route('/developer-users/<int:user_id>/role', methods=['PUT'])
@login_required
def update_developer_user_role(user_id):
    """Update developer user's role"""
    try:
        user = User.query.filter_by(id=user_id, user_type='developer').first_or_404()
        
        data = request.get_json()
        developer_role_id = data.get('developer_role_id')
        
        # Deactivate existing developer role assignments
        existing_assignments = UserRoleAssignment.query.filter_by(
            user_id=user.id,
            is_active=True
        ).filter(UserRoleAssignment.developer_role_id.isnot(None)).all()
        
        for assignment in existing_assignments:
            assignment.is_active = False
        
        # Add new role if specified
        if developer_role_id:
            developer_role = DeveloperRole.query.filter_by(id=developer_role_id).first()
            if developer_role:
                assignment = UserRoleAssignment(
                    user_id=user.id,
                    developer_role_id=developer_role.id,
                    organization_id=None,
                    assigned_by=current_user.id,
                    is_active=True
                )
                db.session.add(assignment)
        
        db.session.commit()
        
        role_name = developer_role.name if developer_role_id else "No role"
        return jsonify({'success': True, 'message': f'Developer user "{user.username}" assigned to role: {role_name}'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@system_roles_bp.route('/developer-users/<int:user_id>/role', methods=['GET'])
@login_required
def get_developer_user_role(user_id):
    """Get developer user's current role"""
    try:
        user = User.query.filter_by(id=user_id, user_type='developer').first_or_404()
        
        # Get current active developer role assignment
        assignment = UserRoleAssignment.query.filter_by(
            user_id=user.id,
            is_active=True
        ).filter(UserRoleAssignment.developer_role_id.isnot(None)).first()
        
        current_role_id = assignment.developer_role_id if assignment else None
        
        return jsonify({
            'success': True,
            'current_role_id': current_role_id
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@system_roles_bp.route('/developer-users/<int:user_id>', methods=['DELETE'])
@login_required
def delete_developer_user(user_id):
    """Delete developer user"""
    try:
        user = User.query.filter_by(id=user_id, user_type='developer').first_or_404()
        
        # Don't allow deleting current user
        if user.id == current_user.id:
            return jsonify({'success': False, 'error': 'Cannot delete your own account'})
        
        # Soft delete the user
        user.soft_delete(deleted_by_user=current_user)
        
        return jsonify({'success': True, 'message': f'Developer user "{user.username}" deleted successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

# API endpoints for permissions and roles data
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
            'description': perm.description
        })
    
    return jsonify({'categories': categories})

@system_roles_bp.route('/developer-permissions/api')
@login_required
def get_developer_permissions_api():
    """API endpoint for developer permissions grouped by category"""
    permissions = DeveloperPermission.query.filter_by(is_active=True).all()
    categories = {}
    
    for perm in permissions:
        category = perm.category or 'general'
        if category not in categories:
            categories[category] = []
        categories[category].append({
            'id': perm.id,
            'name': perm.name,
            'description': perm.description
        })
    
    return jsonify({'categories': categories})

@system_roles_bp.route('/developer-roles/api')
@login_required
def get_developer_roles_api():
    """API endpoint for developer roles"""
    roles = DeveloperRole.query.filter_by(is_active=True).all()
    
    return jsonify({
        'roles': [{
            'id': role.id,
            'name': role.name,
            'description': role.description,
            'category': role.category
        } for role in roles]
    })
