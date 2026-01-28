from flask import abort, flash, redirect, url_for, request, jsonify, session, current_app
from flask_login import current_user, login_required
from functools import wraps, lru_cache
from werkzeug.exceptions import Forbidden
from typing import Iterable
from enum import Enum
from dataclasses import dataclass
from urllib.parse import urlparse
from markupsafe import Markup, escape
import logging

logger = logging.getLogger(__name__)


@dataclass
class PermissionScope:
    dev: bool = False
    customer: bool = False

    @property
    def is_dev_only(self) -> bool:
        return self.dev and not self.customer

    @property
    def is_customer_only(self) -> bool:
        return self.customer and not self.dev

    @property
    def is_shared(self) -> bool:
        return self.dev and self.customer

class AppPermission(Enum):
    """Enumeration of application permissions"""
    # Product permissions
    PRODUCT_VIEW = "product.view"
    PRODUCT_CREATE = "product.create"
    PRODUCT_EDIT = "product.edit"
    PRODUCT_DELETE = "product.delete"

    # Batch permissions
    BATCH_VIEW = "batch.view"
    BATCH_CREATE = "batch.create"
    BATCH_START = "batch.start"
    BATCH_FINISH = "batch.finish"
    BATCH_CANCEL = "batch.cancel"

    # Inventory permissions
    INVENTORY_VIEW = "inventory.view"
    INVENTORY_EDIT = "inventory.edit"
    INVENTORY_ADJUST = "inventory.adjust"
    INVENTORY_DELETE = "inventory.delete"

    # Admin permissions
    ADMIN = "admin"
    USER_MANAGEMENT = "user.management"
    ROLE_MANAGEMENT = "role.management"

    # Organization permissions
    ORGANIZATION_VIEW = "organization.view"
    ORGANIZATION_EDIT = "organization.edit"
    ORGANIZATION_BILLING = "organization.billing"

def wants_json() -> bool:
    """Check if the request wants JSON response"""
    from app.utils.http import wants_json as http_wants_json
    return http_wants_json()


def _record_required_permissions(func, permissions: Iterable[str]):
    if not permissions:
        return func
    try:
        required = set(getattr(func, "_required_permissions", set()))
        for permission in permissions:
            if permission:
                required.add(permission)
        func._required_permissions = required
    except Exception:
        pass
    return func


@lru_cache(maxsize=512)
def resolve_permission_scope(permission_name: str) -> PermissionScope:
    if not permission_name:
        return PermissionScope()
    if permission_name.startswith("dev."):
        return PermissionScope(dev=True, customer=False)
    try:
        from app.models.developer_permission import DeveloperPermission
        from app.models.permission import Permission

        dev_allowed = (
            DeveloperPermission.query.filter_by(
                name=permission_name,
                is_active=True,
            ).first()
            is not None
        )
        customer_allowed = (
            Permission.query.filter_by(
                name=permission_name,
                is_active=True,
            ).first()
            is not None
        )
        return PermissionScope(dev=dev_allowed, customer=customer_allowed)
    except Exception as exc:
        logger.warning("Permission scope lookup failed for %s: %s", permission_name, exc)
        return PermissionScope()


def clear_permission_scope_cache() -> None:
    resolve_permission_scope.cache_clear()


def permission_exists_in_catalog(permission_name: str) -> bool:
    if not permission_name:
        return False
    try:
        from app.models.developer_permission import DeveloperPermission
        from app.models.permission import Permission

        return bool(
            DeveloperPermission.query.filter_by(name=permission_name, is_active=True).first()
            or Permission.query.filter_by(name=permission_name, is_active=True).first()
        )
    except Exception as exc:
        logger.warning("Permission existence lookup failed for %s: %s", permission_name, exc)
        return False


def _default_denied_endpoint() -> str:
    if getattr(current_user, "user_type", None) == "developer":
        return "developer.dashboard"
    return "app_routes.dashboard"


def _safe_referrer() -> str | None:
    referrer = request.referrer
    if not referrer:
        return None
    try:
        ref_parts = urlparse(referrer)
        host_parts = urlparse(request.host_url)
        if ref_parts.scheme in {"http", "https"} and ref_parts.netloc == host_parts.netloc:
            return referrer
    except Exception:
        return None
    return None


def _redirect_back():
    fallback = url_for(_default_denied_endpoint())
    referrer = _safe_referrer()
    return redirect(referrer or fallback)


def _build_upgrade_markup(upgrade_tiers):
    if not upgrade_tiers:
        return None
    tier_names = ", ".join(escape(tier.name) for tier in upgrade_tiers[:2])
    if len(upgrade_tiers) > 2:
        tier_names = f"{tier_names}, and more"
    upgrade_url = url_for("billing.upgrade")
    return Markup(
        f' <span class="ms-1">Upgrade to {tier_names} to unlock this feature.</span> '
        f'<a class="btn btn-sm btn-primary ms-2" href="{upgrade_url}">View upgrade options</a>'
    )


def _build_permission_denied_message(permission_name: str, *, reason: str | None = None, upgrade_tiers=None):
    if reason == "developer_only":
        base = "Developer access required to use this feature."
    elif reason == "organization_required":
        base = "Select an organization to access customer features."
    else:
        base = f"You don't have permission to access this feature ({permission_name})."

    upgrade_markup = _build_upgrade_markup(upgrade_tiers or [])
    if upgrade_markup:
        return Markup(escape(base)) + upgrade_markup
    return base


def _select_primary_permission(permission_names: Iterable[str]) -> tuple[str, PermissionScope]:
    permissions = [p for p in permission_names if p]
    if not permissions:
        return "unknown", PermissionScope()
    for name in permissions:
        scope = resolve_permission_scope(name)
        if scope.is_customer_only or scope.is_dev_only:
            return name, scope
    primary = permissions[0]
    return primary, resolve_permission_scope(primary)


def _permission_denied_response(permission_names: Iterable[str]):
    permission_name, scope = _select_primary_permission(permission_names)

    if scope.is_dev_only and getattr(current_user, "user_type", None) != "developer":
        message = _build_permission_denied_message(permission_name, reason="developer_only")
        if wants_json():
            return jsonify({"error": "developer_only", "message": str(message)}), 403
        flash(message, "error")
        return _redirect_back()

    if scope.is_customer_only and getattr(current_user, "user_type", None) == "developer":
        if not (session.get("dev_selected_org_id") or session.get("masquerade_org_id")):
            message = _build_permission_denied_message(permission_name, reason="organization_required")
            if wants_json():
                return jsonify({"error": "organization_required", "message": str(message)}), 403
            flash(message, "warning")
            return _redirect_back()

    upgrade_tiers = []
    try:
        organization = get_effective_organization()
        if organization and scope.customer:
            tier_permissions = AuthorizationHierarchy.get_tier_allowed_permissions(organization)
            if permission_name not in tier_permissions:
                from app.services.billing_service import BillingService

                upgrade_tiers = BillingService.get_permission_denied_upgrade_options(
                    permission_name,
                    organization,
                )
    except Exception as exc:
        logger.warning("Permission denial context failed: %s", exc)

    message = _build_permission_denied_message(permission_name, upgrade_tiers=upgrade_tiers)
    if wants_json():
        payload = {
            "error": "permission_denied",
            "permission": permission_name,
            "message": str(message),
        }
        if upgrade_tiers:
            payload["upgrade_available"] = True
            payload["upgrade_tiers"] = [tier.name for tier in upgrade_tiers]
            payload["upgrade_url"] = url_for("billing.upgrade")
        return jsonify(payload), 403
    flash(message, "error")
    return _redirect_back()

def require_permission(permission_name: str):
    """
    Decorator to require specific permissions with proper error handling
    Single source of truth for permission checking
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **named_args):
            # Skip permissions only if explicitly disabled
            if current_app.config.get('SKIP_PERMISSIONS'):
                return f(*args, **named_args)

            # Basic auth check - check authentication first
            if not current_user.is_authenticated:
                if wants_json():
                    return jsonify({"error": "Authentication required"}), 401
                flash("Please log in to access this page.", "error")
                return redirect(url_for("auth.login"))

            # Check if user has the permission using authorization hierarchy
            if has_permission(current_user, permission_name):
                return f(*args, **named_args)

            return _permission_denied_response([permission_name])

        return _record_required_permissions(decorated_function, [permission_name])
    return decorator

# Alias for backward compatibility
permission_required = require_permission

def any_permission_required(*permission_names):
    """Decorator that requires any one of the specified permissions"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **named_args):
            if not current_user or not current_user.is_authenticated:
                if wants_json():
                    return jsonify({"error": "Authentication required"}), 401
                return current_app.login_manager.unauthorized()

            # Check if user has any of the required permissions
            if not any(has_permission(current_user, perm) for perm in permission_names):
                return _permission_denied_response(permission_names)

            return f(*args, **named_args)
        return _record_required_permissions(decorated_function, permission_names)
    return decorator

def tier_required(min_tier: str):
    """
    Decorator requiring minimum subscription tier
    Note: This is now deprecated in favor of permission-based access control.
    Use require_permission() instead for specific feature gating.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **named_args):
            # Check if this should return JSON (API endpoints)
            wants_json_response = wants_json()

            # Check authentication first, with JSON-aware response
            if not current_user.is_authenticated:
                if wants_json_response:
                    return jsonify(error="Authentication required"), 401
                # For web requests, let Flask-Login handle the redirect
                return current_app.login_manager.unauthorized()

            org = getattr(current_user, "organization", None)
            if not org:
                if wants_json_response:
                    return jsonify(error="no_organization"), 403
                raise Forbidden("No organization found.")

            # Simple tier check - just verify they have a valid tier
            # For more sophisticated access control, use permission-based decorators
            if not org.tier:
                if wants_json_response:
                    return jsonify(error="no_tier"), 403
                raise Forbidden("No subscription tier assigned.")

            # Exempt organizations have access to everything
            if org.tier.name == 'Exempt Plan':
                return f(*args, **named_args)

            # For specific tier requirements, check the tier name directly
            if min_tier and org.tier.name != min_tier:
                if wants_json_response:
                    return jsonify(error="tier_forbidden", required=min_tier, current=org.tier.name), 403
                raise Forbidden(f"Requires {min_tier} tier.")

            return f(*args, **named_args)
        return decorated_function
    return decorator

def role_required(*roles):
    """
    Decorator to require specific roles
    Allows everything during testing
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **named_args):
            # Allow everything during tests
            if current_app.config.get('TESTING', False):
                return f(*args, **named_args)

            # Basic auth check for non-test environments
            if not current_user.is_authenticated:
                abort(401)

            # TODO: Implement proper role checking
            # For now, just check if user is authenticated
            return f(*args, **named_args)
        return decorated_function
    return decorator

def has_permission(user, permission_name: str) -> bool:
    """
    Check if user has the given permission using the authorization hierarchy
    Single source of truth for permission checking logic
    """
    if not user or not hasattr(user, 'is_authenticated') or not user.is_authenticated:
        return False

    # Use the authorization hierarchy for permission checking
    return AuthorizationHierarchy.check_user_authorization(user, permission_name)

def get_user_permissions(user=None):
    """Get all permissions for the current user using authorization hierarchy"""
    if not user:
        user = current_user

    if not user or not user.is_authenticated:
        return []

    # Use the authorization hierarchy
    return AuthorizationHierarchy.get_user_effective_permissions(user)

def get_effective_organization_id():
    """Get the effective organization ID for the current user context"""
    # For developers viewing an organization
    if current_user.user_type == 'developer':
        return session.get('dev_selected_org_id')

    # For regular users
    return current_user.organization_id if current_user.organization_id else None

def get_effective_organization():
    """Get the effective organization for the current user context"""
    from ..extensions import db

    # Always rollback any pending failed transaction first
    try:
        db.session.rollback()
    except:
        pass

    try:
        if current_user.user_type == 'developer':
            # Developers can view organizations via session
            org_id = session.get('dev_selected_org_id')
            if org_id:
                try:
                    from ..models import Organization
                    from ..extensions import db
                    org = db.session.get(Organization, org_id)
                    if not org:
                        # Organization was deleted - clear masquerade
                        session.pop('dev_selected_org_id', None)
                        session.pop('dev_masquerade_context', None)
                        return None
                    return org
                except Exception as e:
                    print(f"---!!! DEVELOPER ORG QUERY ERROR !!!---")
                    print(f"Error: {e}")
                    print("--------------------------------------")
                    try:
                        db.session.rollback()
                    except:
                        pass
                    return None
            return None
        else:
            # Regular users use their organization
            try:
                return current_user.organization
            except Exception as e:
                print(f"---!!! USER ORGANIZATION QUERY ERROR !!!---")
                print(f"Error: {e}")
                print("-------------------------------------------")
                try:
                    db.session.rollback()
                except:
                    pass
                return None
    except Exception as e:
        print(f"---!!! GENERAL ORGANIZATION ACCESS ERROR !!!---")
        print(f"Error: {e}")
        print("-----------------------------------------------")
        try:
            db.session.rollback()
        except:
            pass
        return None

def is_organization_owner():
    """Check if current user is organization owner"""
    if not current_user.is_authenticated:
        return False

    # Developers in customer view mode act as organization owners
    if current_user.user_type == 'developer':
        return session.get('dev_selected_org_id') is not None

    # Organization owners are customers with the organization_owner role
    if current_user.user_type == 'customer':
        return any(role.name == 'organization_owner' for role in current_user.get_active_roles())

    return False

def is_developer():
    """Check if current user is developer"""
    return current_user.is_authenticated and current_user.user_type == 'developer'

def has_role(role_name):
    """Check if current user has specific role"""
    if not current_user.is_authenticated:
        return False

    try:
        if hasattr(current_user, 'get_active_roles'):
            roles = current_user.get_active_roles()
            return any(role.name == role_name for role in roles)
    except Exception as e:
        print(f"Error checking role {role_name}: {e}")

    return False

def has_subscription_feature(feature):
    """Check if current user's organization has subscription feature"""
    if not current_user.is_authenticated:
        return False

    # Developers can access everything
    if current_user.user_type == 'developer':
        return True

    org_features = current_user.organization.get_subscription_features()
    return feature in org_features or 'all_features' in org_features

def _org_tier_includes_permission(organization, permission_name):
    """
    Check if organization's tier includes the specified permission
    Legacy function name for backward compatibility during transition
    """
    if not organization or not organization.tier:
        return False

    # Use the authorization hierarchy
    tier_permissions = AuthorizationHierarchy.get_tier_allowed_permissions(organization)
    return permission_name in tier_permissions

class AuthorizationHierarchy:
    """Handles the authorization hierarchy for the application"""

    @staticmethod
    def check_subscription_standing(organization):
        """
        Step 1: Check if subscription is in good standing
        """
        if not organization:
            return False, "No organization"

        # Exempt organizations have access
        if organization.effective_subscription_tier == 'exempt':
            return True, "Exempt status"

        # Strict gating: no tier means no access
        if not organization.tier:
            return False, "No subscription tier assigned"

        # Check if tier has valid integration
        if not organization.tier.has_valid_integration:
            return False, "Subscription tier unavailable"

        # For paid tiers, check billing status using org.billing_status only
        if organization.tier.requires_stripe_billing or organization.tier.requires_whop_billing:
            if getattr(organization, 'billing_status', None) in ['past_due', 'payment_failed', 'suspended', 'canceled', 'cancelled']:
                return False, f"Billing status: {organization.billing_status}"

        return True, "Subscription in good standing"

    @staticmethod
    def get_tier_allowed_permissions(organization):
        """
        Step 2: Get all permissions allowed by subscription tier
        """
        if not organization or not organization.tier:
            return []

        # Get permissions directly from the database tier relationship
        return [p.name for p in organization.tier.permissions if p.is_active]

    @staticmethod
    def check_user_authorization(user, permission_name):
        """
        Complete authorization check following the hierarchy:
        1. Check subscription standing
        2. Check if tier allows permission
        3. Check if user role grants permission
        """
        from ..extensions import db

        # Always rollback any pending failed transaction first
        try:
            db.session.rollback()
        except:
            pass

        try:
            # Developers have scoped access based on developer roles + masquerade context
            if user.user_type == 'developer':
                from app.models.developer_permission import DeveloperPermission
                from app.models.permission import Permission

                dev_scoped = permission_name.startswith('dev.')
                if not dev_scoped:
                    dev_scoped = DeveloperPermission.query.filter_by(
                        name=permission_name, is_active=True
                    ).first() is not None
                org_scoped = Permission.query.filter_by(
                    name=permission_name, is_active=True
                ).first() is not None

                if dev_scoped and user.has_developer_permission(permission_name):
                    return True

                # For organization permissions, require masquerade context
                if not org_scoped:
                    return False
                selected_org_id = session.get('dev_selected_org_id')
                if not selected_org_id:
                    return False
                # If viewing a specific organization, continue with organization checks

            # Get organization (handle developer customer view)
            organization = get_effective_organization()

            if not organization:
                return False

            # Step 1: Check subscription standing
            subscription_ok, reason = AuthorizationHierarchy.check_subscription_standing(organization)
            if not subscription_ok:
                logger.warning(f"Subscription check failed for org {organization.id}: {reason}")
                return False

            # Step 2: Check if subscription tier allows this permission
            tier_permissions = AuthorizationHierarchy.get_tier_allowed_permissions(organization)
            if permission_name not in tier_permissions:
                logger.debug(f"Permission {permission_name} not allowed by tier {organization.effective_subscription_tier}")
                return False

            # Step 3: Check user role permissions
            # Organization owners should have the organization_owner role with proper permissions
            # They still need to check permissions, but get all tier-allowed permissions
            if getattr(user, 'is_organization_owner', False):
                # Organization owners get all permissions that are allowed by their tier
                # This ensures they respect subscription tier limits but get full access within their tier
                return permission_name in tier_permissions

            # Other users need role-based permissions
            try:
                user_roles = user.get_active_roles()
                for role in user_roles:
                    if role.has_permission(permission_name):
                        # If tier exists, the gate already allowed; if no tier, allow by role
                        return True
            except Exception as role_error:
                logger.warning(f"User roles error in authorization: {role_error}")
                try:
                    db.session.rollback()
                except:
                    pass
                return False

            return False

        except Exception as e:
            print(f"---!!! AUTHORIZATION CHECK ERROR !!!---")
            print(f"Error: {e}")
            print("--------------------------------------")
            try:
                db.session.rollback()
            except:
                pass
            return False

    @staticmethod
    def get_user_effective_permissions(user):
        """
        Get all effective permissions for a user based on the authorization hierarchy
        """
        # Developers without masquerade context only see developer permissions
        if user.user_type == 'developer':
            selected_org_id = session.get('dev_selected_org_id')
            if not selected_org_id:
                return AuthorizationHierarchy.get_developer_role_permissions(user)

        # Get organization
        organization = get_effective_organization()

        if not organization:
            return []

        # Check subscription standing
        subscription_ok, _ = AuthorizationHierarchy.check_subscription_standing(organization)
        if not subscription_ok:
            return []

        # Get tier-allowed permissions (may be empty if tier missing)
        tier_permissions = AuthorizationHierarchy.get_tier_allowed_permissions(organization)

        # Add-on entitlements from:
        # 1) Included add-ons on the tier (Stripe-bypassed)
        # 2) Active organization add-ons from Stripe purchases
        addon_permissions = []
        try:
            # Included add-ons
            try:
                included = getattr(organization.tier, 'included_addons', []) if organization.tier else []
                for a in included or []:
                    if a and a.permission_name:
                        addon_permissions.append(a.permission_name)
            except Exception:
                pass
            # Purchased add-ons
            from app.models.addon import OrganizationAddon
            active_addons = OrganizationAddon.query.filter_by(organization_id=organization.id, active=True).all()
            for ent in active_addons:
                if ent.addon and ent.addon.permission_name:
                    addon_permissions.append(ent.addon.permission_name)
        except Exception as _e:
            logger.warning(f"Addon entitlement lookup failed: {_e}")

        # Organization owners get all tier-allowed + addon permissions.
        if getattr(user, 'is_organization_owner', False):
            return list(set(tier_permissions + addon_permissions))

        # Other users
        user_permissions = set()
        user_roles = user.get_active_roles()

        # Intersect role permissions with tier-allowed or addon-granted
        for role in user_roles:
            role_permissions = [p.name for p in role.get_permissions()]
            for perm in role_permissions:
                if (perm in tier_permissions) or (perm in addon_permissions):
                    user_permissions.add(perm)

        # Also, addon permissions may be independent of role if you prefer them to grant directly
        # Here we keep it conservative: role still required. If you want addons to grant directly, uncomment:
        # for perm in addon_permissions:
        #     user_permissions.add(perm)

        return list(user_permissions)

    @staticmethod
    def get_developer_role_permissions(user):
        """Get permissions from developer role assignments."""
        try:
            from app.models.developer_role import DeveloperRole
            roles = user.get_active_roles()
            permissions = set()
            for role in roles:
                if isinstance(role, DeveloperRole):
                    for perm in role.get_permissions():
                        permissions.add(perm.name)
            return list(permissions)
        except Exception as exc:
            logger.warning(f"Developer permission lookup failed: {exc}")
            return []

    @staticmethod
    def check_organization_access(organization):
        """Check if organization has valid access based on subscription and billing status"""
        if not organization:
            return False, "No organization found"

        # Exempt organizations have access
        if organization.effective_subscription_tier == 'exempt':
            return True, "Exempt organization"

        # Check subscription tier exists and is valid
        if not organization.tier:
            return False, "No valid subscription tier"

        # Check if tier has valid integration setup
        if not organization.tier.has_valid_integration:
            return False, "Subscription tier integration not configured"

        # For billing-required tiers, check billing_status only
        if organization.tier.requires_stripe_billing or organization.tier.requires_whop_billing:
            if getattr(organization, 'billing_status', None) in ['past_due', 'payment_failed', 'suspended', 'canceled', 'cancelled']:
                return False, "Subscription not active"

            # Additional billing validations can be added here
            # e.g., check for past due payments, etc.

        return True, "Active subscription"

class FeatureGate:
    """Feature gating based on subscription tiers"""

    @staticmethod
    def is_feature_available(feature_name, organization=None):
        """Check if a feature is available to the organization's subscription tier"""
        if not organization:
            organization = get_effective_organization()

        if not organization:
            return False

        # Check subscription standing first
        subscription_ok, _ = AuthorizationHierarchy.check_subscription_standing(organization)
        if not subscription_ok:
            return False

        # Get available features from organization's tier
        tier_key = organization.effective_subscription_tier
        available_features = organization.get_subscription_features()
        return feature_name in available_features

    @staticmethod
    def check_usage_limits(limit_name, current_usage, organization=None):
        """Check if current usage is within subscription tier limits"""
        if not organization:
            organization = get_effective_organization()

        if not organization or not organization.tier:
            return False, "No subscription tier"

        # Example limit checks
        if limit_name == 'users':
            max_users = organization.tier.user_limit
            if max_users == -1:  # Unlimited
                return True, "Unlimited"
            return current_usage <= max_users, f"Limit: {max_users}"

        # Add other limit checks as needed
        return True, "No limits defined"

# Legacy compatibility functions
def require_permission_with_org_scoping(permission_name, require_org_scoping=True):
    """Legacy compatibility - use require_permission instead"""
    return require_permission(permission_name)

def require_organization_scoping(f):
    """Legacy compatibility - organization scoping is handled automatically"""
    return f

def require_system_admin(f):
    """Legacy compatibility - use require_permission('dev.system_admin') instead"""
    return require_permission('dev.system_admin')(f)

def require_organization_owner(f):
    """Legacy compatibility - check in the function itself"""
    @wraps(f)
    def decorated_function(*args, **named_args):
        if not is_organization_owner():
            abort(403)
        return f(*args, **named_args)
    return decorated_function