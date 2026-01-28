from __future__ import annotations

from flask import flash, jsonify, redirect, render_template, request, url_for
from app.models import User
from app.services.developer.user_service import UserService

from ..decorators import require_developer_permission
from ..routes import developer_bp


@developer_bp.route("/users")
@require_developer_permission("dev.manage_users")
def users():
    """User management dashboard."""
    customer_users = UserService.list_customer_users()
    developer_users = UserService.list_developer_users()
    return render_template(
        "developer/users.html",
        customer_users=customer_users,
        developer_users=developer_users,
    )


@developer_bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@require_developer_permission("dev.manage_users")
def toggle_user_active(user_id):
    """Toggle user active status."""
    user = User.query.get_or_404(user_id)
    success, message = UserService.toggle_user_active(user)
    flash(message, "success" if success else "error")
    return redirect(url_for("developer.users"))


@developer_bp.route("/api/user/<int:user_id>")
@require_developer_permission("dev.manage_users")
def get_user_details(user_id):
    """Get detailed user information for editing."""
    user = User.query.get_or_404(user_id)
    if user.user_type == "developer":
        return jsonify({"success": False, "error": "Cannot edit developer users through this endpoint"})

    user_data = UserService.serialize_user(user)
    user_data["is_organization_owner"] = getattr(user, "is_organization_owner", False)
    user_data["_is_organization_owner"] = getattr(user, "_is_organization_owner", False)
    user_data["display_role"] = user.display_role
    if user.organization:
        user_data["organization"] = {"id": user.organization.id, "name": user.organization.name}

    return jsonify({"success": True, "user": user_data})


@developer_bp.route("/api/developer-user/<int:user_id>")
@require_developer_permission("dev.manage_roles")
def get_developer_user_details(user_id):
    """Get detailed developer user information for editing."""
    user = User.query.get_or_404(user_id)
    if user.user_type != "developer":
        return jsonify({"success": False, "error": "User is not a developer"})

    from app.models.developer_role import DeveloperRole
    from app.models.user_role_assignment import UserRoleAssignment

    all_roles = DeveloperRole.query.filter_by(is_active=True).all()
    assignments = UserRoleAssignment.query.filter_by(
        user_id=user_id, is_active=True
    ).filter(UserRoleAssignment.developer_role_id.isnot(None)).all()
    assigned_role_ids = {assignment.developer_role_id for assignment in assignments}

    roles_data = [
        {
            "id": role.id,
            "name": role.name,
            "description": role.description,
            "assigned": role.id in assigned_role_ids,
        }
        for role in all_roles
    ]

    user_data = {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "phone": user.phone,
        "is_active": user.is_active,
        "last_login": user.last_login.strftime("%Y-%m-%d %H:%M") if user.last_login else None,
        "created_at": user.created_at.strftime("%Y-%m-%d") if user.created_at else None,
        "roles": roles_data,
    }
    return jsonify({"success": True, "user": user_data})


@developer_bp.route("/api/user/update", methods=["POST"])
@require_developer_permission("dev.manage_users")
def update_user():
    """Update user information."""
    data = request.get_json() or {}
    user = User.query.get_or_404(data.get("user_id"))
    success, message = UserService.update_user(user, data)
    status = 200 if success else 400
    return jsonify({"success": success, "message": message}), status


@developer_bp.route("/api/developer-user/update", methods=["POST"])
@require_developer_permission("dev.manage_roles")
def update_developer_user():
    """Update developer user information."""
    data = request.get_json() or {}
    user = User.query.get_or_404(data.get("user_id"))
    success, message = UserService.update_developer_user(user, data)
    status = 200 if success else 400
    return jsonify({"success": success, "message": message}), status


@developer_bp.route("/api/user/reset-password", methods=["POST"])
@require_developer_permission("dev.manage_users")
def reset_user_password():
    """Reset user password."""
    data = request.get_json() or {}
    user = User.query.get_or_404(data.get("user_id"))
    success, message = UserService.reset_password(user, data.get("new_password"))
    status = 200 if success else 400
    return jsonify({"success": success, "message": message}), status


@developer_bp.route("/api/user/soft-delete", methods=["POST"])
@require_developer_permission("dev.manage_users")
def soft_delete_user():
    """Soft delete a user."""
    data = request.get_json() or {}
    user = User.query.get_or_404(data.get("user_id"))
    success, message = UserService.soft_delete_user(user)
    status = 200 if success else 400
    return jsonify({"success": success, "message": message}), status
