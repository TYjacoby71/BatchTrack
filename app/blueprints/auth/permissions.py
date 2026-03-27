"""Permission management routes and role helper handlers.

Synopsis:
Provide authorization management endpoints/helpers for permission matrix
editing, permission status toggling, and role maintenance behavior.

Glossary:
- Permission matrix: Combined developer/customer permission availability map.
- Catalog metadata: Consolidated permission descriptions/categories from seeder.
- Role management: Creation/update helpers for organization/system roles.
"""

import logging

from flask import jsonify, render_template, request
from flask_login import current_user, login_required

from app.models import Permission
from app.services.auth_permission_route_service import AuthPermissionRouteService
from app.utils.permissions import (
    clear_permission_scope_cache,
    has_permission,
    require_permission,
)

from . import auth_bp

logger = logging.getLogger(__name__)


def _can_manage_system_roles(user) -> bool:
    """Return True when user can manage global/system roles."""
    return has_permission(user, "dev.manage_roles")


# --- Get tier permissions ---
# Purpose: Resolve active permissions available for a subscription tier.
# Inputs: Tier key (id-like token).
# Outputs: List of active Permission rows for that tier.
def get_tier_permissions(tier_key):
    """Get all permissions available to a subscription tier (DB only)."""
    return AuthPermissionRouteService.get_tier_permissions(tier_key=tier_key)


# --- Load permission catalog ---
# Purpose: Load consolidated permission metadata for descriptions/categories.
# Inputs: None.
# Outputs: Mapping of permission name to metadata attributes.
def _load_permission_catalog():
    """Load permission metadata from the consolidated catalog."""
    try:
        from app.seeders.consolidated_permission_seeder import (
            load_consolidated_permissions,
        )

        data = load_consolidated_permissions()
    except Exception:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/auth/permissions.py:55",
            exc_info=True,
        )
        return {}

    catalog = {}
    for scope_key in ("organization_permissions", "developer_permissions"):
        for category_key, category_data in data.get(scope_key, {}).items():
            for perm in category_data.get("permissions", []):
                name = perm.get("name")
                if not name:
                    continue
                entry = catalog.setdefault(
                    name,
                    {
                        "description": perm.get("description")
                        or perm.get("display_name")
                        or name,
                        "org_category": None,
                        "dev_category": None,
                    },
                )
                if scope_key == "organization_permissions":
                    entry["org_category"] = category_key
                else:
                    entry["dev_category"] = category_key
    return catalog


# --- Resolve permission metadata ---
# Purpose: Pick description/category values for a permission and scope.
# Inputs: Permission name, catalog mapping, and org/dev category preference.
# Outputs: Tuple of (description, category).
def _resolve_permission_metadata(name, catalog, *, prefer_org: bool):
    meta = catalog.get(name, {})
    description = meta.get("description") or name
    if prefer_org:
        category = meta.get("org_category") or meta.get("dev_category") or "general"
    else:
        category = meta.get("dev_category") or meta.get("org_category") or "general"
    return description, category


# --- Manage permissions page ---
# Purpose: Render permission matrix management UI.
# Inputs: Authenticated request with dev.assign_permissions.
# Outputs: HTML response containing categorized permission registry.
@auth_bp.route("/permissions")
@require_permission("dev.assign_permissions")
def manage_permissions():
    """Show system permissions management page"""
    catalog = _load_permission_catalog()
    permission_registry = {}

    # Start with catalog entries so new permissions appear even if not seeded yet.
    for name, meta in catalog.items():
        permission_registry[name] = {
            "name": name,
            "description": meta.get("description") or name,
            "org_category": meta.get("org_category"),
            "dev_category": meta.get("dev_category"),
            "dev_enabled": False,
            "customer_enabled": False,
            "dev_active": False,
            "customer_active": False,
        }

    for perm in AuthPermissionRouteService.list_all_developer_permissions():
        if perm.name.startswith("app."):
            continue
        entry = permission_registry.setdefault(
            perm.name,
            {
                "name": perm.name,
                "description": perm.description or perm.name,
                "org_category": None,
                "dev_category": perm.category,
                "dev_enabled": False,
                "customer_enabled": False,
                "dev_active": False,
                "customer_active": False,
            },
        )
        entry["dev_enabled"] = True
        entry["dev_active"] = bool(perm.is_active)
        entry["dev_category"] = entry.get("dev_category") or perm.category
        if not entry.get("description"):
            entry["description"] = perm.description or perm.name

    for perm in AuthPermissionRouteService.list_all_permissions():
        entry = permission_registry.setdefault(
            perm.name,
            {
                "name": perm.name,
                "description": perm.description or perm.name,
                "org_category": perm.category,
                "dev_category": None,
                "dev_enabled": False,
                "customer_enabled": False,
                "dev_active": False,
                "customer_active": False,
            },
        )
        entry["customer_enabled"] = True
        entry["customer_active"] = bool(perm.is_active)
        entry["org_category"] = entry.get("org_category") or perm.category
        if not entry.get("description"):
            entry["description"] = perm.description or perm.name

    permission_categories = {}
    for entry in permission_registry.values():
        category = entry.get("org_category") or entry.get("dev_category") or "general"
        permission_categories.setdefault(category, []).append(
            {
                "name": entry["name"],
                "description": entry.get("description") or entry["name"],
                "dev_enabled": entry["dev_enabled"],
                "customer_enabled": entry["customer_enabled"],
                "active": entry["dev_active"] or entry["customer_active"],
                "customer_allowed": not entry["name"].startswith("dev."),
            }
        )

    for category in permission_categories:
        permission_categories[category].sort(key=lambda x: x["name"])
    permission_categories = dict(
        sorted(permission_categories.items(), key=lambda item: item[0])
    )

    return render_template(
        "pages/auth/permissions.html", permission_categories=permission_categories
    )


# --- Update permission matrix ---
# Purpose: Create/update/remove permission availability across dev/customer scopes.
# Inputs: JSON payload with permission name, scope flags, and active toggle.
# Outputs: JSON success/error response after persistence operations.
@auth_bp.route("/permissions/update", methods=["POST"])
@require_permission("dev.assign_permissions")
def update_permission_matrix():
    """Update permission availability for dev/customer scopes."""
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    dev_enabled = bool(data.get("dev_enabled"))
    customer_enabled = bool(data.get("customer_enabled"))
    is_active = bool(data.get("is_active"))

    if not name:
        return (
            jsonify({"success": False, "message": "Permission name is required"}),
            400,
        )
    if name.startswith("dev.") and customer_enabled:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Developer permissions cannot be customer-scoped",
                }
            ),
            400,
        )

    catalog = _load_permission_catalog()

    try:
        dev_description, dev_category = _resolve_permission_metadata(
            name, catalog, prefer_org=False
        )
        org_description, org_category = _resolve_permission_metadata(
            name, catalog, prefer_org=True
        )
        AuthPermissionRouteService.upsert_permission_matrix_entry(
            name=name,
            dev_enabled=dev_enabled,
            customer_enabled=customer_enabled,
            is_active=is_active,
            dev_description=dev_description,
            dev_category=dev_category,
            org_description=org_description,
            org_category=org_category,
        )
        clear_permission_scope_cache()

        return jsonify(
            {
                "success": True,
                "permission": {
                    "name": name,
                    "dev_enabled": dev_enabled,
                    "customer_enabled": customer_enabled,
                    "active": is_active if (dev_enabled or customer_enabled) else False,
                    "customer_allowed": not name.startswith("dev."),
                },
            }
        )
    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/auth/permissions.py:299",
            exc_info=True,
        )
        AuthPermissionRouteService.rollback_session()
        return (
            jsonify(
                {"success": False, "message": f"Error updating permission: {str(e)}"}
            ),
            500,
        )


# --- Toggle permission status ---
# Purpose: Flip active state for one developer or organization permission row.
# Inputs: JSON payload with permission id, table name, and target status.
# Outputs: JSON success/error response after update.
@auth_bp.route("/permissions/toggle-status", methods=["POST"])
@require_permission("dev.assign_permissions")
def toggle_permission_status():
    """Toggle active/inactive status of a permission"""
    data = request.get_json()
    permission_id = data.get("permission_id")
    permission_table = data.get("table")
    new_status = data.get("is_active")

    try:
        if permission_table == "developer_permission":
            permission = AuthPermissionRouteService.get_developer_permission_or_404(
                permission_id=permission_id
            )
        elif permission_table == "permission":
            permission = AuthPermissionRouteService.get_permission_or_404(
                permission_id=permission_id
            )
        else:
            return jsonify({"success": False, "message": "Invalid permission table"})

        AuthPermissionRouteService.set_permission_active_status(
            permission=permission,
            is_active=new_status,
        )
        clear_permission_scope_cache()

        status_text = "activated" if new_status else "deactivated"
        return jsonify(
            {
                "success": True,
                "message": f'Permission "{permission.name}" {status_text} successfully',
            }
        )

    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/auth/permissions.py:342",
            exc_info=True,
        )
        AuthPermissionRouteService.rollback_session()
        return jsonify(
            {"success": False, "message": f"Error updating permission: {str(e)}"}
        )


# --- Manage roles page ---
# Purpose: Render role-management page with allowed permission choices.
# Inputs: Authenticated user context and role-management permission.
# Outputs: HTML response containing scoped roles and permissions.
@require_permission("organization.manage_roles")
@login_required
def manage_roles():
    """Manage roles (org owners and system admins)"""
    if _can_manage_system_roles(current_user):
        # System admin can see all roles and all permissions
        roles = AuthPermissionRouteService.list_all_roles()
        available_permissions = AuthPermissionRouteService.list_active_permissions()
    else:
        # Organization owners see their org roles + system roles
        roles = AuthPermissionRouteService.list_organization_roles(
            organization_id=current_user.organization_id
        )
        # Only show permissions available to their subscription tier
        available_permissions = get_tier_permissions(
            current_user.organization.effective_subscription_tier
        )

    return render_template(
        "pages/auth/roles.html",
        roles=roles,
        available_permissions=available_permissions,
    )


# --- Create role ---
# Purpose: Persist a new role with scoped permission assignments.
# Inputs: JSON payload with role data and permission ids.
# Outputs: JSON success/error response after create attempt.
@require_permission("organization.manage_roles")
@login_required
def create_role():
    """Create new role"""
    try:
        data = request.get_json()

        role_organization_id = (
            current_user.organization_id
            if not _can_manage_system_roles(current_user)
            else None
        )

        # Add permissions - but only allow permissions available to the organization's tier
        permission_ids = data.get("permission_ids", [])

        if _can_manage_system_roles(current_user):
            # Developers can assign any permission
            permissions = AuthPermissionRouteService.list_permissions_by_ids(
                permission_ids=permission_ids
            )
        else:
            # Organization users can only assign permissions included in their tier
            available_permissions = get_tier_permissions(
                current_user.organization.effective_subscription_tier
            )
            available_permission_ids = [p.id for p in available_permissions]
            # Filter requested permissions to only include those available to the tier
            filtered_permission_ids = [
                pid for pid in permission_ids if pid in available_permission_ids
            ]
            permissions = AuthPermissionRouteService.list_permissions_by_ids(
                permission_ids=filtered_permission_ids
            )
        AuthPermissionRouteService.create_role_with_permissions(
            name=data["name"],
            description=data.get("description"),
            organization_id=role_organization_id,
            created_by=current_user.id,
            permissions=permissions,
        )

        return jsonify({"success": True, "message": "Role created successfully"})

    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/auth/permissions.py:427",
            exc_info=True,
        )
        AuthPermissionRouteService.rollback_session()
        return jsonify({"success": False, "error": str(e)})


# --- Update role ---
# Purpose: Update role identity fields and assigned permissions.
# Inputs: Role id plus JSON payload with updated fields.
# Outputs: JSON success/error response after update attempt.
@require_permission("organization.manage_roles")
@login_required
def update_role(role_id):
    """Update role"""
    try:
        role = AuthPermissionRouteService.get_role_or_404(role_id=role_id)

        # Check permissions
        if role.is_system_role and not _can_manage_system_roles(current_user):
            return jsonify({"success": False, "error": "Cannot edit system roles"})

        if (
            role.organization_id != current_user.organization_id
            and not _can_manage_system_roles(current_user)
        ):
            return jsonify(
                {
                    "success": False,
                    "error": "Cannot edit roles from other organizations",
                }
            )

        data = request.get_json()

        role.name = data.get("name", role.name)
        role.description = data.get("description", role.description)

        # Update permissions
        if "permission_ids" in data:
            permission_ids = data["permission_ids"]
            permissions = AuthPermissionRouteService.list_permissions_by_ids(
                permission_ids=permission_ids
            )
        else:
            permissions = None
        AuthPermissionRouteService.update_role_with_permissions(
            role=role,
            name=data.get("name"),
            description=data.get("description"),
            permissions=permissions,
        )

        return jsonify({"success": True, "message": "Role updated successfully"})

    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/auth/permissions.py:475",
            exc_info=True,
        )
        AuthPermissionRouteService.rollback_session()
        return jsonify({"success": False, "error": str(e)})
