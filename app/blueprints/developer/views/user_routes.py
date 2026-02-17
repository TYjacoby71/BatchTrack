"""Developer user-management routes.

Synopsis:
Exposes developer endpoints for viewing, updating, soft deleting, and hard
deleting customer users plus developer-role editing endpoints.

Glossary:
- User modal payload: JSON shape consumed by developer user-management dialogs.
- Hard-delete endpoint: Permanent user removal API with integrity safeguards.
"""

from __future__ import annotations

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from app.models import User
from app.services.developer.user_service import UserService

from ..decorators import require_developer_permission
from ..routes import developer_bp


# --- Render users dashboard ---
# Purpose: Show developer-facing user management page.
# Inputs: Authenticated developer session.
# Outputs: Rendered HTML view with customer/developer user lists.
@developer_bp.route("/users")
@require_developer_permission("dev.manage_users")
def users():
    """User management dashboard."""
    customer_page = request.args.get("customer_page", 1, type=int) or 1
    developer_page = request.args.get("developer_page", 1, type=int) or 1
    per_page = request.args.get("per_page", 25, type=int) or 25

    customer_page = max(customer_page, 1)
    developer_page = max(developer_page, 1)
    per_page = max(10, min(per_page, 100))

    customer_users_pagination = UserService.list_customer_users_paginated(
        page=customer_page, per_page=per_page
    )
    developer_users_pagination = UserService.list_developer_users_paginated(
        page=developer_page, per_page=per_page
    )

    return render_template(
        "developer/users.html",
        customer_users_pagination=customer_users_pagination,
        developer_users_pagination=developer_users_pagination,
        customer_page=customer_page,
        developer_page=developer_page,
        per_page=per_page,
    )


# --- Update current developer profile ---
# Purpose: Apply self-profile edits from developer user-management page.
# Inputs: JSON body with profile fields.
# Outputs: JSON success/error payload with HTTP status.
@developer_bp.route("/api/profile/update", methods=["POST"])
@require_developer_permission("dev.manage_users")
def update_developer_profile():
    """Update currently authenticated developer profile."""
    data = request.get_json() or {}
    success, message = UserService.update_own_profile(current_user, data)
    status = 200 if success else 400
    payload = {"success": success}
    if success:
        payload["message"] = message
    else:
        payload["error"] = message
    return jsonify(payload), status


# --- Toggle user active status ---
# Purpose: Activate/deactivate a selected user from developer tools.
# Inputs: URL user_id.
# Outputs: Redirect with flash status message.
@developer_bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@require_developer_permission("dev.manage_users")
def toggle_user_active(user_id):
    """Toggle user active status."""
    user = User.query.get_or_404(user_id)
    success, message = UserService.toggle_user_active(user)
    flash(message, "success" if success else "error")
    return redirect(url_for("developer.users"))


# --- Get customer user details ---
# Purpose: Return editable JSON payload for non-developer users.
# Inputs: URL user_id.
# Outputs: JSON response with normalized user modal fields.
@developer_bp.route("/api/user/<int:user_id>")
@require_developer_permission("dev.manage_users")
def get_user_details(user_id):
    """Get detailed user information for editing."""
    user = User.query.get_or_404(user_id)
    if user.user_type == "developer":
        return jsonify(
            {
                "success": False,
                "error": "Cannot edit developer users through this endpoint",
            }
        )

    user_data = UserService.serialize_user(user)
    user_data["is_organization_owner"] = getattr(user, "is_organization_owner", False)
    user_data["_is_organization_owner"] = getattr(user, "_is_organization_owner", False)
    user_data["display_role"] = user.display_role
    if user.organization:
        user_data["organization"] = {
            "id": user.organization.id,
            "name": user.organization.name,
        }

    return jsonify({"success": True, "user": user_data})


# --- Get developer user details ---
# Purpose: Return developer-user payload including role assignments.
# Inputs: URL user_id.
# Outputs: JSON response for developer-role edit modal.
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
    assignments = (
        UserRoleAssignment.query.filter_by(user_id=user_id, is_active=True)
        .filter(UserRoleAssignment.developer_role_id.isnot(None))
        .all()
    )
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
        "last_login": (
            user.last_login.strftime("%Y-%m-%d %H:%M") if user.last_login else None
        ),
        "created_at": user.created_at.strftime("%Y-%m-%d") if user.created_at else None,
        "roles": roles_data,
    }
    return jsonify({"success": True, "user": user_data})


# --- Update customer user ---
# Purpose: Apply customer-user edits from developer UI.
# Inputs: JSON body with user_id + editable fields.
# Outputs: JSON success/error payload with HTTP status.
@developer_bp.route("/api/user/update", methods=["POST"])
@require_developer_permission("dev.manage_users")
def update_user():
    """Update user information."""
    data = request.get_json() or {}
    user = User.query.get_or_404(data.get("user_id"))
    success, message = UserService.update_user(user, data)
    status = 200 if success else 400
    return jsonify({"success": success, "message": message}), status


# --- Update developer user ---
# Purpose: Apply developer profile/role edits from developer UI.
# Inputs: JSON body with user_id + role assignments.
# Outputs: JSON success/error payload with HTTP status.
@developer_bp.route("/api/developer-user/update", methods=["POST"])
@require_developer_permission("dev.manage_roles")
def update_developer_user():
    """Update developer user information."""
    data = request.get_json() or {}
    user = User.query.get_or_404(data.get("user_id"))
    success, message = UserService.update_developer_user(user, data)
    status = 200 if success else 400
    return jsonify({"success": success, "message": message}), status


# --- Reset user password ---
# Purpose: Reset selected user password from developer controls.
# Inputs: JSON body containing user_id and new_password.
# Outputs: JSON success/error payload with HTTP status.
@developer_bp.route("/api/user/reset-password", methods=["POST"])
@require_developer_permission("dev.manage_users")
def reset_user_password():
    """Reset user password."""
    data = request.get_json() or {}
    user = User.query.get_or_404(data.get("user_id"))
    success, message = UserService.reset_password(user, data.get("new_password"))
    status = 200 if success else 400
    return jsonify({"success": success, "message": message}), status


# --- Soft delete user endpoint ---
# Purpose: Soft delete a user while preserving historical records.
# Inputs: JSON body containing user_id.
# Outputs: JSON success/error payload with HTTP status.
@developer_bp.route("/api/user/soft-delete", methods=["POST"])
@require_developer_permission("dev.manage_users")
def soft_delete_user():
    """Soft delete a user."""
    data = request.get_json() or {}
    user = User.query.get_or_404(data.get("user_id"))
    success, message = UserService.soft_delete_user(user)
    status = 200 if success else 400
    return jsonify({"success": success, "message": message}), status


# --- Hard delete user endpoint ---
# Purpose: Permanently delete a user with integrity-preserving cleanup.
# Inputs: JSON body containing user_id.
# Outputs: JSON success/error payload with HTTP status.
@developer_bp.route("/api/user/hard-delete", methods=["POST"])
@require_developer_permission("dev.manage_users")
def hard_delete_user():
    """Hard delete a user while preserving tenant data integrity."""
    data = request.get_json() or {}
    user = User.query.get_or_404(data.get("user_id"))
    success, message = UserService.hard_delete_user(user)
    status = 200 if success else 400
    return jsonify({"success": success, "message": message}), status
