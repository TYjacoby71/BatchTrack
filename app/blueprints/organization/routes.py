import logging
import re

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app.models import Role, User
from app.services.affiliate_service import AffiliateService
from app.services.integrations.connection_service import IntegrationConnectionService
from app.services.organization_route_service import OrganizationRouteService
from app.utils.permissions import (
    any_permission_required,
    has_permission,
    require_permission,
)
from app.utils.settings import is_feature_enabled

logger = logging.getLogger(__name__)


organization_bp = Blueprint("organization", __name__)


def _is_owner_user(user) -> bool:
    """Return True for current/legacy organization-owner representations."""
    return bool(
        getattr(user, "is_organization_owner", False)
        or getattr(user, "_is_organization_owner", False)
    )


def _is_protected_org_user(user) -> bool:
    """Identify users that org-admin routes should not mutate directly."""
    return bool(getattr(user, "user_type", None) == "developer" or _is_owner_user(user))


def _is_developer_user(user) -> bool:
    return bool(has_permission(user, "dev.manage_roles"))


@organization_bp.route("/dashboard")
@login_required
@require_permission("organization.view")
def dashboard():
    """Organization management dashboard"""
    # Check subscription tier first (except for developers)
    if not _is_developer_user(current_user):
        effective_tier = current_user.organization.effective_subscription_tier
        has_affiliate_access = has_permission(
            current_user, "affiliates.view_org_dashboard"
        ) or has_permission(current_user, "affiliates.view")
        if effective_tier in ["free", "solo"] and not has_affiliate_access:
            flash(
                "Organization dashboard is available with Team and Enterprise plans.",
                "info",
            )
            return redirect(url_for("settings.index"))

    from ...services.billing_service import BillingService

    pricing_data = BillingService.get_comprehensive_pricing_data()

    try:
        db_tiers = OrganizationRouteService.list_customer_facing_tiers()
        tiers_config = {
            str(t.id): {
                "name": t.name,
                "is_available": t.has_valid_integration or t.is_billing_exempt,
            }
            for t in db_tiers
        }
    except Exception:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/organization/routes.py:60",
            exc_info=True,
        )
        tiers_config = {}

    # Get organization data - handle developer customer view
    from app.utils.permissions import get_effective_organization

    organization = get_effective_organization()
    if not organization:
        if _is_developer_user(current_user):
            flash("Please select an organization first", "error")
            return redirect(url_for("developer.organizations"))
        else:
            flash("No organization found", "error")
            return redirect(url_for("app_routes.dashboard"))

    # Get organization statistics
    org_id = organization.id
    from app.services.statistics import AnalyticsDataService

    force_refresh = (request.args.get("refresh") or "").lower() in ("1", "true", "yes")
    dashboard_metrics = AnalyticsDataService.get_organization_dashboard(
        org_id, force_refresh=force_refresh
    )
    org_stats = dashboard_metrics.get("organization_stats", {})
    performance_metrics = dashboard_metrics.get("performance_metrics", {})
    top_recipes = dashboard_metrics.get("top_recipes", [])

    # Count pending invites (inactive users)
    pending_invites = OrganizationRouteService.count_pending_invites(org_id)

    permissions = OrganizationRouteService.list_active_permissions()
    permission_categories = {}
    for perm in permissions:
        category = perm.category or "general"
        if category not in permission_categories:
            permission_categories[category] = []
        permission_categories[category].append(perm)

    # Get roles for the roles tab
    roles = Role.get_organization_roles(org_id)

    # Get users for the user management tab (exclude developers from organization view)
    users = OrganizationRouteService.list_org_users(org_id)

    is_developer_user = _is_developer_user(current_user)
    affiliate_feature_visible = bool(
        is_feature_enabled("FEATURE_AFFILIATE_PROGRAM_UI") or is_developer_user
    )
    can_view_affiliate_tab = bool(
        is_developer_user
        or has_permission(current_user, "organization.manage_billing")
        or has_permission(current_user, "affiliates.view_org_dashboard")
    )
    affiliate_tab_visible = affiliate_feature_visible and can_view_affiliate_tab
    affiliate_context = {}
    if affiliate_tab_visible:
        affiliate_page = request.args.get("affiliate_page", 1, type=int)
        affiliate_context = AffiliateService.build_organization_dashboard_context(
            organization, page=affiliate_page, per_page=15
        )
    affiliate_payout_account = (
        AffiliateService.get_or_create_payout_account(organization)
        if affiliate_tab_visible
        else None
    )
    pos_integrations_enabled = bool(
        is_feature_enabled("FEATURE_ECOMMERCE_INTEGRATIONS")
        and (
            has_permission(current_user, "integrations.shopify")
            or has_permission(current_user, "integrations.marketplace")
            or has_permission(current_user, "integrations.api_access")
        )
    )
    pos_providers = (
        IntegrationConnectionService.build_pos_provider_cards(org_id=org_id)
        if pos_integrations_enabled
        else []
    )

    # Debug: Print to console to verify data
    print(f"Permission categories: {list(permission_categories.keys())}")
    print(f"Total permissions: {len(permissions)}")
    print(f"Roles count: {len(roles)}")
    print(f"Users count: {len(users)}")

    return render_template(
        "pages/organization/dashboard.html",
        pricing_data=pricing_data,
        organization=organization,
        org_stats=org_stats,
        performance_metrics=performance_metrics,
        top_recipes=top_recipes,
        pending_invites=pending_invites,
        permission_categories=permission_categories,
        roles=roles,
        users=users,
        tiers_config=tiers_config,
        affiliate_context=affiliate_context,
        affiliate_tab_visible=affiliate_tab_visible,
        affiliate_payout_account=affiliate_payout_account,
        pos_marketplaces_tab_visible=pos_integrations_enabled,
        pos_providers=pos_providers,
    )


@organization_bp.route("/integrations/status")
@login_required
@require_permission("organization.view")
def integration_status():
    """Return POS/marketplace integration status for the current organization."""
    from app.utils.permissions import get_effective_organization_id

    org_id = get_effective_organization_id()
    if not org_id:
        return jsonify({"success": False, "error": "No organization selected"}), 400

    if not is_feature_enabled("FEATURE_ECOMMERCE_INTEGRATIONS"):
        return (
            jsonify({"success": False, "error": "POS integrations feature is disabled"}),
            403,
        )

    summary = IntegrationConnectionService.get_connection_summary(org_id=org_id)
    onboarding = IntegrationConnectionService.get_onboarding_summary(org_id=org_id)
    return jsonify({"success": True, "connections": summary, "onboarding": onboarding})


@organization_bp.route("/affiliate-dashboard")
@login_required
@any_permission_required("organization.manage_billing", "affiliates.view_org_dashboard")
def affiliate_dashboard():
    """Detailed organization-level affiliate analytics dashboard."""
    from app.utils.permissions import get_effective_organization

    organization = get_effective_organization()
    if not organization:
        if _is_developer_user(current_user):
            flash("Please select an organization first", "error")
            return redirect(url_for("developer.organizations"))
        flash("No organization found", "error")
        return redirect(url_for("app_routes.dashboard"))

    affiliate_page = request.args.get("page", 1, type=int)
    affiliate_context = AffiliateService.build_organization_dashboard_context(
        organization, page=affiliate_page, per_page=25
    )
    affiliate_analytics = AffiliateService.build_organization_analytics_context(
        organization
    )
    affiliate_payout_account = AffiliateService.get_or_create_payout_account(
        organization
    )

    return render_template(
        "pages/organization/affiliate_dashboard.html",
        organization=organization,
        affiliate_context=affiliate_context,
        affiliate_analytics=affiliate_analytics,
        affiliate_payout_account=affiliate_payout_account,
    )


@organization_bp.route("/create-role", methods=["POST"])
@login_required
@require_permission("organization.manage_roles")
def create_role():
    """Create a new organization role"""
    try:
        data = request.get_json()

        # Get organization
        from app.utils.permissions import get_effective_organization_id

        org_id = get_effective_organization_id()
        if not org_id:
            return jsonify({"success": False, "error": "No organization selected"})

        # Create role
        role = Role(
            name=data["name"],
            description=data.get("description"),
            organization_id=org_id,
            created_by=current_user.id,
            is_system_role=False,
        )

        # Add permissions
        permission_ids = data.get("permission_ids", [])
        permissions = OrganizationRouteService.list_permissions_by_ids(permission_ids)
        role.permissions = permissions

        OrganizationRouteService.add_entity(role)
        OrganizationRouteService.commit_session()

        return jsonify({"success": True, "message": "Role created successfully"})

    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/organization/routes.py:178",
            exc_info=True,
        )
        OrganizationRouteService.rollback_session()
        return jsonify({"success": False, "error": str(e)})


@organization_bp.route("/update-settings", methods=["POST"])
@login_required
@require_permission("organization.edit")
def update_organization_settings():
    """Update organization settings"""

    try:
        data = request.get_json()
        organization = current_user.organization

        if not organization:
            return jsonify({"success": False, "error": "No organization found"})

        # Update organization fields
        if "name" in data and data["name"].strip():
            organization.name = data["name"].strip()

        if "contact_email" in data:
            # If contact_email is empty, use current user's email as default
            contact_email = (
                data["contact_email"].strip()
                if data["contact_email"]
                else current_user.email
            )
            organization.contact_email = contact_email

        if "timezone" in data:
            organization.timezone = data["timezone"]

        # Inventory cost method toggle
        method = data.get("inventory_cost_method")
        if method in ["fifo", "average"]:
            # Only update if changed
            if getattr(organization, "inventory_cost_method", None) != method:
                organization.inventory_cost_method = method
                from app.utils.timezone_utils import TimezoneUtils as _TZ

                organization.inventory_cost_method_changed_at = _TZ.utc_now()

        OrganizationRouteService.commit_session()

        return jsonify(
            {"success": True, "message": "Organization settings updated successfully"}
        )

    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/organization/routes.py:237",
            exc_info=True,
        )
        OrganizationRouteService.rollback_session()
        return jsonify({"success": False, "error": str(e)}), 500


@organization_bp.route("/update-tier", methods=["POST"])
@login_required
@require_permission("organization.manage_billing")
def update_subscription_tier():
    """Update organization subscription tier (support/developer only)."""

    if not _is_developer_user(current_user):
        return jsonify(
            {
                "success": False,
                "error": "Only support users can update subscription tiers",
            }
        )

    try:
        data = request.get_json()
        tier_key = data.get("subscription_tier")

        if not tier_key:
            return jsonify({"success": False, "error": "Subscription tier is required"})

        # Get organization (handle developer customer view)
        from app.utils.permissions import get_effective_organization

        organization = get_effective_organization()
        if not organization:
            return jsonify({"success": False, "error": "No organization selected"})

        try:
            _tier_id = int(tier_key)
        except (TypeError, ValueError):
            _tier_id = None
        if not _tier_id or not OrganizationRouteService.get_subscription_tier(_tier_id):
            return jsonify({"success": False, "error": "Invalid subscription tier"})

        # Update or create subscription
        from ...models.subscription import Subscription

        subscription = organization.subscription
        if not subscription:
            subscription = Subscription(
                organization_id=organization.id, tier=tier_key, status="active"
            )
            OrganizationRouteService.add_entity(subscription)
        else:
            subscription.tier = tier_key
            subscription.status = "active"

        OrganizationRouteService.commit_session()

        return jsonify(
            {"success": True, "message": f"Subscription tier updated to {tier_key}"}
        )

    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/organization/routes.py:297",
            exc_info=True,
        )
        OrganizationRouteService.rollback_session()
        return jsonify({"success": False, "error": str(e)}), 500


@organization_bp.route("/invite-user", methods=["POST"])
@login_required
@require_permission("organization.manage_users")
def invite_user():
    """Invite a new user to the organization"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"})

        # Validate required fields
        email = User.normalize_email(data.get("email"))
        role_id = data.get("role_id")
        first_name = data.get("first_name", "").strip()
        last_name = data.get("last_name", "").strip()
        phone = data.get("phone", "").strip()

        if not email or not role_id:
            return jsonify({"success": False, "error": "Email and role are required"})

        # Validate email format
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, email):
            return jsonify({"success": False, "error": "Invalid email format"})

        # Check if user already exists (by email or username)
        if User.email_exists(email):
            return jsonify(
                {"success": False, "error": "User with this email already exists"}
            )

        # Validate role exists and is not developer role
        role = OrganizationRouteService.get_scoped_role(role_id)
        if not role:
            return jsonify({"success": False, "error": "Invalid role selected"})

        if role.is_system_role:
            return jsonify(
                {
                    "success": False,
                    "error": "Cannot assign system or organization owner roles to invited users",
                }
            )

        # Check if user should be added as inactive due to subscription limits
        force_inactive = data.get("force_inactive", False)
        (force_inactive or not current_user.organization.can_add_users())

        if not current_user.organization.can_add_users() and not force_inactive:
            current_count = current_user.organization.active_users_count
            max_users = current_user.organization.get_max_users()
            return jsonify(
                {
                    "success": False,
                    "error": f"Organization has reached user limit ({current_count}/{max_users}) for {current_user.organization.subscription_tier} subscription",
                }
            )

        # Delegate to service for invite orchestration
        from app.services.user_invite_service import UserInviteService

        result = UserInviteService.invite_user(
            organization=current_user.organization,
            email=email,
            role_id=role_id,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            force_inactive=force_inactive,
        )

        if not result.success:
            return jsonify({"success": False, "error": result.message})

        invited = result.user
        return jsonify(
            {
                "success": True,
                "message": result.message,
                "user_data": {
                    "username": invited.username,
                    "email": invited.email,
                    "full_name": invited.full_name,
                    "role": role.name,
                    "is_active": invited.is_active,
                },
            }
        )

    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/organization/routes.py:413",
            exc_info=True,
        )
        OrganizationRouteService.rollback_session()
        print(f"Error inviting user: {str(e)}")  # For debugging
        return jsonify({"success": False, "error": f"Failed to invite user: {str(e)}"})


@organization_bp.route("/update", methods=["POST"])
@login_required
@require_permission("organization.edit")
def update_organization():
    """Update organization settings"""

    try:
        data = request.get_json()
        organization = current_user.organization

        # Update organization fields
        if "name" in data:
            organization.name = data["name"]

        # Add other organization settings here as needed

        OrganizationRouteService.commit_session()

        return jsonify({"success": True, "message": "Organization settings updated"})

    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/organization/routes.py:447",
            exc_info=True,
        )
        OrganizationRouteService.rollback_session()
        return jsonify({"success": False, "error": str(e)})


@organization_bp.route("/export/<report_type>")
@login_required
@require_permission("reports.export")
def export_report(report_type):
    """Export various organization reports"""

    try:
        if report_type == "users":
            # Export users CSV - exclude developers from org exports
            OrganizationRouteService.list_export_users(current_user.organization_id)
            flash("User export functionality coming soon", "info")
        elif report_type == "batches":
            flash("Batch export functionality coming soon", "info")
        elif report_type == "inventory":
            flash("Inventory export functionality coming soon", "info")
        elif report_type == "products":
            flash("Product export functionality coming soon", "info")
        elif report_type == "activity":
            flash("Activity export functionality coming soon", "info")
        else:
            flash("Unknown report type", "error")

        return redirect(url_for("organization.dashboard"))

    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/organization/routes.py:487",
            exc_info=True,
        )
        flash(f"Export error: {str(e)}", "error")
        return redirect(url_for("organization.dashboard"))


@organization_bp.route("/add-user", methods=["POST"])
@login_required
@require_permission("organization.manage_users")
def add_user():
    """Add a new user to the organization (org owners only) - legacy endpoint"""
    """Add a new user to the organization - legacy endpoint"""
    try:
        data = request.get_json()

        # Validate required fields
        username = User.normalize_username(data.get("username"))
        email = User.normalize_email(data.get("email"))
        password = data.get("password")
        role_id = data.get("role_id")

        if not all([username, email, password, role_id]):
            return jsonify({"success": False, "error": "All fields are required"})

        # Check if user already exists
        if User.username_exists(username):
            return jsonify({"success": False, "error": "Username already exists"})

        if User.email_exists(email):
            return jsonify({"success": False, "error": "Email already exists"})

        # Check if organization can add more users
        if not current_user.organization.can_add_users():
            return jsonify(
                {
                    "success": False,
                    "error": "Organization has reached user limit for current subscription",
                }
            )

        # Create new user
        new_user = User(
            username=username,
            email=email,
            role_id=role_id,
            organization_id=current_user.organization_id,
            is_active=True,
            user_type="customer",
        )
        new_user.set_password(password)

        OrganizationRouteService.add_entity(new_user)
        OrganizationRouteService.commit_session()

        return jsonify({"success": True, "message": "User added successfully"})

    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/organization/routes.py:551",
            exc_info=True,
        )
        OrganizationRouteService.rollback_session()
        return jsonify({"success": False, "error": str(e)})


# User Management Routes


@organization_bp.route("/user/<int:user_id>", methods=["GET"])
@login_required
@require_permission("organization.manage_users")
def get_user(user_id):
    """Get user details for editing"""
    user = OrganizationRouteService.get_user_in_org(
        user_id, current_user.organization_id
    )

    if not user:
        return jsonify({"success": False, "error": "User not found"})

    # Don't allow editing of developers or other org owners (except self)
    if _is_protected_org_user(user) and user.id != current_user.id:
        return jsonify(
            {
                "success": False,
                "error": "Cannot edit system users or other organization owners",
            }
        )

    # Get user's role assignments
    role_assignments = []
    for assignment in user.role_assignments:
        if assignment.is_active:
            role_assignments.append(
                {
                    "role_id": assignment.role_id,
                    "role_name": assignment.role.name,
                    "assigned_at": (
                        assignment.assigned_at.isoformat()
                        if assignment.assigned_at
                        else None
                    ),
                }
            )

    return jsonify(
        {
            "success": True,
            "user": {
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "phone": user.phone,
                "is_active": user.is_active,
                "user_type": user.user_type,
                "role_assignments": role_assignments,
            },
        }
    )


@organization_bp.route("/user/<int:user_id>", methods=["PUT"])
@login_required
@require_permission("organization.manage_users")
def update_user(user_id):
    """Update user details"""

    try:
        data = request.get_json()

        # Get user from same organization
        user = OrganizationRouteService.get_user_in_org(
            user_id, current_user.organization_id
        )

        if not user:
            return jsonify({"success": False, "error": "User not found"})

        # Don't allow editing of developers or other org owners (except self)
        if _is_protected_org_user(user) and user.id != current_user.id:
            return jsonify(
                {
                    "success": False,
                    "error": "Cannot edit system users or other organization owners",
                }
            )

        # Update user fields
        if "first_name" in data:
            user.first_name = data["first_name"]
        if "last_name" in data:
            user.last_name = data["last_name"]
        if "email" in data:
            user.email = data["email"]
        if "phone" in data:
            user.phone = data["phone"]
        if "role_id" in data:
            # Validate role exists and is not developer role
            role = OrganizationRouteService.get_scoped_role(data["role_id"])
            if role and not role.is_system_role:
                user.role_id = data["role_id"]

        # Handle organization owner flag with single owner constraint and role transfer
        if "is_organization_owner" in data:
            new_owner_status = data["is_organization_owner"]

            if new_owner_status and not user.is_organization_owner:
                # User is being made an organization owner
                # First, remove organization owner status and role from all other users in this org
                other_owners = OrganizationRouteService.list_other_org_owners(
                    user.organization_id, user.id
                )
                org_owner_role = OrganizationRouteService.get_org_owner_role()

                for other_owner in other_owners:
                    other_owner.is_organization_owner = False
                    # Remove the organization owner role from other owners
                    if org_owner_role:
                        other_owner.remove_role(org_owner_role)

                # Now set this user as the owner and assign the role
                user.is_organization_owner = True

                # Ensure the organization owner role is assigned
                if org_owner_role:
                    user.assign_role(org_owner_role, assigned_by=current_user)

            elif not new_owner_status and user.is_organization_owner:
                # User is being removed as organization owner
                user.is_organization_owner = False

                # Remove the organization owner role
                org_owner_role = OrganizationRouteService.get_org_owner_role()
                if org_owner_role:
                    user.remove_role(org_owner_role)

        # Handle status changes - check subscription limits for activation
        if "is_active" in data:
            new_status = data["is_active"]
            if new_status and not user.is_active:  # Activating user
                if not current_user.organization.can_add_users():
                    current_count = current_user.organization.active_users_count
                    max_users = current_user.organization.get_max_users()
                    return jsonify(
                        {
                            "success": False,
                            "error": f"Cannot activate user. Organization has reached user limit ({current_count}/{max_users}) for {current_user.organization.subscription_tier} subscription",
                        }
                    )
            user.is_active = new_status

        OrganizationRouteService.commit_session()

        return jsonify(
            {"success": True, "message": f"User {user.full_name} updated successfully"}
        )

    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/organization/routes.py:734",
            exc_info=True,
        )
        OrganizationRouteService.rollback_session()
        return jsonify({"success": False, "error": str(e)})


@organization_bp.route("/user/<int:user_id>/toggle-status", methods=["POST"])
@login_required
@require_permission("organization.manage_users")
def toggle_user_status(user_id):
    """Toggle user active/inactive status"""

    try:
        # Get user from same organization
        user = OrganizationRouteService.get_user_in_org(
            user_id, current_user.organization_id
        )

        if not user:
            return jsonify({"success": False, "error": "User not found"})

        # Don't allow toggling status of developers, org owners, or self
        if _is_protected_org_user(user):
            return jsonify(
                {
                    "success": False,
                    "error": "Cannot change status of system users or organization owners",
                }
            )

        if user.id == current_user.id:
            return jsonify({"success": False, "error": "Cannot change your own status"})

        # Toggle status
        new_status = not user.is_active

        # If activating, check subscription limits
        if new_status and not user.is_active:
            if not current_user.organization.can_add_users():
                current_count = current_user.organization.active_users_count
                max_users = current_user.organization.get_max_users()
                return jsonify(
                    {
                        "success": False,
                        "error": f"Cannot activate user. Organization has reached user limit ({current_count}/{max_users}) for {current_user.organization.subscription_tier} subscription",
                    }
                )

        user.is_active = new_status
        OrganizationRouteService.commit_session()

        status_text = "activated" if new_status else "deactivated"
        return jsonify(
            {
                "success": True,
                "message": f"User {user.full_name} {status_text} successfully",
            }
        )

    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/organization/routes.py:799",
            exc_info=True,
        )
        OrganizationRouteService.rollback_session()
        return jsonify({"success": False, "error": str(e)})


@organization_bp.route("/user/<int:user_id>", methods=["DELETE"])
@login_required
@require_permission("organization.manage_users")
def delete_user(user_id):
    """Delete user permanently"""

    try:
        # Get user from same organization
        user = OrganizationRouteService.get_user_in_org(
            user_id, current_user.organization_id
        )

        if not user:
            return jsonify({"success": False, "error": "User not found"})

        # Don't allow deleting developers, org owners, or self
        if _is_protected_org_user(user):
            return jsonify(
                {
                    "success": False,
                    "error": "Cannot delete system users or organization owners",
                }
            )

        if user.id == current_user.id:
            return jsonify({"success": False, "error": "Cannot delete yourself"})

        username = user.username
        full_name = user.full_name

        # Soft delete the user (preserves all historical data)
        user.soft_delete(deleted_by_user=current_user)

        return jsonify(
            {
                "success": True,
                "message": f"User {full_name} ({username}) removed successfully (can be restored if needed)",
            }
        )

    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/organization/routes.py:851",
            exc_info=True,
        )
        OrganizationRouteService.rollback_session()
        return jsonify({"success": False, "error": str(e)})


@organization_bp.route("/user/<int:user_id>/restore", methods=["POST"])
@login_required
@require_permission("organization.manage_users")
def restore_user(user_id):
    """Restore a soft-deleted user"""

    try:
        # Get user from same organization (including deleted users)
        user = OrganizationRouteService.get_user_in_org(
            user_id, current_user.organization_id
        )

        if not user:
            return jsonify({"success": False, "error": "User not found"})

        if not user.is_deleted:
            return jsonify({"success": False, "error": "User is not deleted"})

        username = user.username
        full_name = user.full_name

        # Restore the user
        user.restore(restored_by_user=current_user)

        return jsonify(
            {
                "success": True,
                "message": f"User {full_name} ({username}) restored successfully (needs manual activation and role assignment)",
            }
        )

    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/organization/routes.py:894",
            exc_info=True,
        )
        OrganizationRouteService.rollback_session()
        return jsonify({"success": False, "error": str(e)})
