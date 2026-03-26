from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user
from app.services.developer.system_role_service import SystemRoleService

from .decorators import require_developer_permission

system_roles_bp = Blueprint("system_roles", __name__)

# Note: Developer access is now handled by the main middleware
# The before_request decorator was causing conflicts with the main security checkpoint


@system_roles_bp.route("/system-roles")
@require_developer_permission("dev.manage_roles")
def manage_system_roles():
    """Manage system roles and developer users"""
    context = SystemRoleService.get_manage_page_context()
    return render_template(
        "developer/system_roles.html",
        roles=context["roles"],
        developer_roles=context["developer_roles"],
        developer_users=context["developer_users"],
    )


# System Role Management (Organization Roles)
@system_roles_bp.route("/system-roles", methods=["POST"])
@require_developer_permission("dev.manage_roles")
def create_system_role():
    """Create new system role (organization role)"""
    payload = SystemRoleService.create_system_role(
        request.get_json() or {}, created_by=current_user.id
    )
    return jsonify(payload)


@system_roles_bp.route("/system-roles/<int:role_id>", methods=["GET"])
@require_developer_permission("dev.manage_roles")
def get_system_role(role_id):
    """Get system role details"""
    return jsonify(SystemRoleService.get_system_role_payload(role_id))


@system_roles_bp.route("/system-roles/<int:role_id>", methods=["PUT"])
@require_developer_permission("dev.manage_roles")
def update_system_role(role_id):
    """Update system role"""
    payload = SystemRoleService.update_system_role(role_id, request.get_json() or {})
    return jsonify(payload)


@system_roles_bp.route("/system-roles/<int:role_id>", methods=["DELETE"])
@require_developer_permission("dev.manage_roles")
def delete_system_role(role_id):
    """Delete system role"""
    return jsonify(SystemRoleService.delete_system_role(role_id))


# Developer Role Management
@system_roles_bp.route("/developer-roles", methods=["POST"])
@require_developer_permission("dev.manage_roles")
def create_developer_role():
    """Create new developer role"""
    return jsonify(SystemRoleService.create_developer_role(request.get_json() or {}))


@system_roles_bp.route("/developer-roles/<int:role_id>", methods=["GET"])
@require_developer_permission("dev.manage_roles")
def get_developer_role(role_id):
    """Get developer role details"""
    return jsonify(SystemRoleService.get_developer_role_payload(role_id))


@system_roles_bp.route("/developer-roles/<int:role_id>", methods=["PUT"])
@require_developer_permission("dev.manage_roles")
def update_developer_role(role_id):
    """Update developer role"""
    payload = SystemRoleService.update_developer_role(role_id, request.get_json() or {})
    return jsonify(payload)


@system_roles_bp.route("/developer-roles/<int:role_id>", methods=["DELETE"])
@require_developer_permission("dev.manage_roles")
def delete_developer_role(role_id):
    """Delete developer role"""
    return jsonify(SystemRoleService.delete_developer_role(role_id))


# Developer User Management
@system_roles_bp.route("/developer-users", methods=["POST"])
@require_developer_permission("dev.manage_roles")
def create_developer_user():
    """Create new developer user"""
    payload = SystemRoleService.create_developer_user(
        request.get_json() or {}, assigned_by=current_user.id
    )
    return jsonify(payload)


@system_roles_bp.route("/developer-users/<int:user_id>/role", methods=["PUT"])
@require_developer_permission("dev.manage_roles")
def update_developer_user_role(user_id):
    """Update developer user's role"""
    payload = SystemRoleService.update_developer_user_role(
        user_id, request.get_json() or {}, assigned_by=current_user.id
    )
    return jsonify(payload)


@system_roles_bp.route("/developer-users/<int:user_id>/role", methods=["GET"])
@require_developer_permission("dev.manage_roles")
def get_developer_user_role(user_id):
    """Get developer user's current role"""
    return jsonify(SystemRoleService.get_developer_user_role(user_id))


@system_roles_bp.route("/developer-users/<int:user_id>", methods=["DELETE"])
@require_developer_permission("dev.manage_roles")
def delete_developer_user(user_id):
    """Delete developer user"""
    payload = SystemRoleService.delete_developer_user(
        user_id, current_user_obj=current_user
    )
    return jsonify(payload)


# API endpoints for permissions and roles data
@system_roles_bp.route("/permissions/api")
@require_developer_permission("dev.manage_roles")
def get_permissions_api():
    """API endpoint for permissions grouped by category"""
    return jsonify({"categories": SystemRoleService.get_permissions_grouped()})


@system_roles_bp.route("/developer-permissions/api")
@require_developer_permission("dev.manage_roles")
def get_developer_permissions_api():
    """API endpoint for developer permissions grouped by category"""
    return jsonify({"categories": SystemRoleService.get_developer_permissions_grouped()})


@system_roles_bp.route("/developer-roles/api")
@require_developer_permission("dev.manage_roles")
def get_developer_roles_api():
    """API endpoint for developer roles"""
    return jsonify({"roles": SystemRoleService.get_active_developer_roles_payload()})
