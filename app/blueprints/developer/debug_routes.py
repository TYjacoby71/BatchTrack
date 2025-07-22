
from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from app.models import Permission
from app.utils.permissions import has_permission, _has_tier_permission
from app.blueprints.developer.subscription_tiers import load_tiers_config

debug_bp = Blueprint('debug', __name__, url_prefix='/debug')

@debug_bp.route('/permissions')
@login_required
def debug_permissions():
    """Debug endpoint to show current user's permissions"""
    if current_user.user_type != 'developer':
        return jsonify({'error': 'Developer access only'}), 403
    
    # Get all permissions
    all_permissions = Permission.query.filter_by(is_active=True).all()
    
    # Get current tier
    current_tier = current_user.organization.effective_subscription_tier if current_user.organization else 'free'
    
    # Get tier config
    tiers_config = load_tiers_config()
    tier_data = tiers_config.get(current_tier, {})
    tier_permissions = tier_data.get('permissions', [])
    
    # Check each permission
    permission_status = {}
    for perm in all_permissions:
        permission_status[perm.name] = {
            'has_permission': has_permission(current_user, perm.name),
            'has_tier_permission': _has_tier_permission(current_user, perm.name),
            'in_tier_config': perm.name in tier_permissions,
            'description': perm.description
        }
    
    return jsonify({
        'user_type': current_user.user_type,
        'current_tier': current_tier,
        'tier_permissions': tier_permissions,
        'permission_status': permission_status
    })

@debug_bp.route('/tiers')
@login_required 
def debug_tiers():
    """Debug endpoint to show tier configuration"""
    if current_user.user_type != 'developer':
        return jsonify({'error': 'Developer access only'}), 403
        
    tiers_config = load_tiers_config()
    return jsonify(tiers_config)
