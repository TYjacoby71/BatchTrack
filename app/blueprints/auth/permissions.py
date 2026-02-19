from flask import jsonify, render_template, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models import DeveloperPermission, Permission, Role
from app.models.subscription_tier import SubscriptionTier
from app.utils.permissions import clear_permission_scope_cache, require_permission

from . import auth_bp


def get_tier_permissions(tier_key):
    """Get all permissions available to a subscription tier (DB only)."""
    try:
        tier_id = int(tier_key)
    except (TypeError, ValueError):
        tier_id = None
    tier = db.session.get(SubscriptionTier, tier_id) if tier_id is not None else None
    if not tier:
        return []
    return Permission.query.filter(
        Permission.name.in_([p.name for p in getattr(tier, "permissions", [])]),
        Permission.is_active,
    ).all()


def _load_permission_catalog():
    """Load permission metadata from the consolidated catalog."""
    try:
        from app.seeders.consolidated_permission_seeder import (
            load_consolidated_permissions,
        )

        data = load_consolidated_permissions()
    except Exception:
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


def _resolve_permission_metadata(name, catalog, *, prefer_org: bool):
    meta = catalog.get(name, {})
    description = meta.get("description") or name
    if prefer_org:
        category = meta.get("org_category") or meta.get("dev_category") or "general"
    else:
        category = meta.get("dev_category") or meta.get("org_category") or "general"
    return description, category


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

    for perm in DeveloperPermission.query.all():
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

    for perm in Permission.query.all():
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
        dev_perm = DeveloperPermission.query.filter_by(name=name).first()
        org_perm = Permission.query.filter_by(name=name).first()

        if dev_enabled:
            description, category = _resolve_permission_metadata(
                name, catalog, prefer_org=False
            )
            if not dev_perm:
                dev_perm = DeveloperPermission(
                    name=name,
                    description=description,
                    category=category,
                    is_active=is_active,
                )
                db.session.add(dev_perm)
            else:
                dev_perm.description = description
                dev_perm.category = category
                dev_perm.is_active = is_active
        elif dev_perm:
            dev_perm.developer_roles = []
            db.session.delete(dev_perm)

        if customer_enabled:
            description, category = _resolve_permission_metadata(
                name, catalog, prefer_org=True
            )
            if not org_perm:
                org_perm = Permission(
                    name=name,
                    description=description,
                    category=category,
                    is_active=is_active,
                )
                db.session.add(org_perm)
            else:
                org_perm.description = description
                org_perm.category = category
                org_perm.is_active = is_active
        elif org_perm:
            org_perm.roles = []
            try:
                for tier in org_perm.tiers.all():
                    org_perm.tiers.remove(tier)
            except Exception:
                pass
            db.session.delete(org_perm)

        from app.models.developer_role import DeveloperRole

        system_admin_role = DeveloperRole.query.filter_by(name="system_admin").first()
        if system_admin_role:
            system_admin_role.permissions = DeveloperPermission.query.filter_by(
                is_active=True
            ).all()

        org_owner_role = Role.query.filter_by(
            name="organization_owner", is_system_role=True
        ).first()
        if org_owner_role:
            org_owner_role.permissions = Permission.query.filter_by(
                is_active=True
            ).all()

        db.session.commit()
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
        db.session.rollback()
        return (
            jsonify(
                {"success": False, "message": f"Error updating permission: {str(e)}"}
            ),
            500,
        )


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
            permission = DeveloperPermission.query.get_or_404(permission_id)
        elif permission_table == "permission":
            permission = Permission.query.get_or_404(permission_id)
        else:
            return jsonify({"success": False, "message": "Invalid permission table"})

        permission.is_active = new_status
        db.session.commit()
        clear_permission_scope_cache()

        status_text = "activated" if new_status else "deactivated"
        return jsonify(
            {
                "success": True,
                "message": f'Permission "{permission.name}" {status_text} successfully',
            }
        )

    except Exception as e:
        db.session.rollback()
        return jsonify(
            {"success": False, "message": f"Error updating permission: {str(e)}"}
        )


@require_permission("organization.manage_roles")
@login_required
def manage_roles():
    """Manage roles (org owners and system admins)"""
    if current_user.user_type == "developer":
        # System admin can see all roles and all permissions
        roles = Role.query.all()
        available_permissions = Permission.query.filter_by(is_active=True).all()
    else:
        # Organization owners see their org roles + system roles
        roles = Role.get_organization_roles(current_user.organization_id)
        # Only show permissions available to their subscription tier
        available_permissions = get_tier_permissions(
            current_user.organization.effective_subscription_tier
        )

    return render_template(
        "pages/auth/roles.html",
        roles=roles,
        available_permissions=available_permissions,
    )


@require_permission("organization.manage_roles")
@login_required
def create_role():
    """Create new role"""
    try:
        data = request.get_json()

        role = Role(
            name=data["name"],
            description=data.get("description"),
            organization_id=(
                current_user.organization_id
                if current_user.user_type != "developer"
                else None
            ),
            created_by=current_user.id,
        )

        # Add permissions - but only allow permissions available to the organization's tier
        permission_ids = data.get("permission_ids", [])

        if current_user.user_type == "developer":
            # Developers can assign any permission
            permissions = Permission.query.filter(
                Permission.id.in_(permission_ids)
            ).all()
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
            permissions = Permission.query.filter(
                Permission.id.in_(filtered_permission_ids)
            ).all()

        role.permissions = permissions

        db.session.add(role)
        db.session.commit()

        return jsonify({"success": True, "message": "Role created successfully"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)})


@require_permission("organization.manage_roles")
@login_required
def update_role(role_id):
    """Update role"""
    try:
        role = Role.query.get_or_404(role_id)

        # Check permissions
        if role.is_system_role and current_user.user_type != "developer":
            return jsonify({"success": False, "error": "Cannot edit system roles"})

        if (
            role.organization_id != current_user.organization_id
            and current_user.user_type != "developer"
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
            permissions = Permission.query.filter(
                Permission.id.in_(permission_ids)
            ).all()
            role.permissions = permissions

        db.session.commit()

        return jsonify({"success": True, "message": "Role updated successfully"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)})
