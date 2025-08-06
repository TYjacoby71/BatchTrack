"""
Authorization system following industry standard practices:

1. User logs in (authentication)
2. System checks subscription tier status (authorization)
3. Subscription tier dictates available permissions/features
4. Organization owner gets all tier-allowed permissions
5. Other users get permissions based on their assigned roles
"""

from flask_login import current_user
from flask import session
import logging

logger = logging.getLogger(__name__)

class AuthorizationHierarchy:
    """Handles the authorization hierarchy for the application"""

    @staticmethod
    def check_subscription_standing(organization):
        """
        Step 1: Check if subscription is in good standing
        """
        if not organization:
            return False, "No organization"

        # Exempt organizations always have access
        if organization.effective_subscription_tier == 'exempt':
            return True, "Exempt status"

        # Check if organization has valid subscription tier
        if not organization.tier:
            return False, "No subscription tier assigned"

        # Check if tier is available
        if not organization.tier.is_available:
            return False, "Subscription tier unavailable"

        # For paid tiers, check billing status
        if organization.tier.requires_stripe_billing or organization.tier.requires_whop_billing:
            if organization.subscription_status not in ['active', 'trialing']:
                return False, f"Subscription status: {organization.subscription_status}"

        return True, "Subscription in good standing"

    @staticmethod
    def get_tier_allowed_permissions(organization):
        """
        Step 2: Get all permissions allowed by subscription tier
        """
        if not organization or not organization.tier:
            return []

        # Load tier configuration to get permissions
        from ..blueprints.developer.subscription_tiers import load_tiers_config
        tiers_config = load_tiers_config()

        tier_key = organization.effective_subscription_tier
        tier_data = tiers_config.get(tier_key, {})

        return tier_data.get('permissions', [])

    @staticmethod
    def check_user_authorization(user, permission_name):
        """
        Complete authorization check following the hierarchy:
        1. Check subscription standing
        2. Check if tier allows permission
        3. Check if user role grants permission
        """

        # Developers in non-customer mode have full access
        if user.user_type == 'developer':
            selected_org_id = session.get('dev_selected_org_id')
            if not selected_org_id:
                return True  # Developer mode - full access

        # Get organization (handle developer customer view)
        from .permissions import get_effective_organization
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
        # Organization owners get all tier-allowed permissions
        if user.user_type == 'organization_owner' or user.user_type == 'developer':
            return True

        # Other users need role-based permissions
        user_roles = user.get_active_roles()
        for role in user_roles:
            if role.has_permission(permission_name):
                return True

        return False

    @staticmethod
    def get_user_effective_permissions(user):
        """Get all effective permissions for a user through the authorization hierarchy"""
        if not user or not user.is_authenticated:
            return []

        permissions = set()

        # Step 1: Developer permissions (highest priority)
        if user.user_type == 'developer':
            dev_perms = DeveloperPermission.query.filter_by(
                developer_user_id=user.id,
                is_active=True
            ).all()
            for dev_perm in dev_perms:
                permissions.add(dev_perm.permission.name)
            return list(permissions)

        # Step 2: Organization tier permissions
        if user.organization:
            tier_permissions = AuthorizationHierarchy._get_tier_permissions(user.organization.effective_subscription_tier)
            permissions.update(tier_permissions)

        # Step 3: User role permissions (filtered by tier availability)
        user_role_permissions = AuthorizationHierarchy._get_user_role_permissions(user)
        # Only include role permissions that are allowed by the tier
        for perm in user_role_permissions:
            if perm in permissions:  # Only add if tier allows it
                permissions.add(perm)

        return list(permissions)

    @staticmethod
    def check_organization_access(organization):
        """Check if organization has valid access based on subscription and billing status"""
        if not organization:
            return False, "No organization found"

        # Exempt organizations always have access
        if organization.effective_subscription_tier == 'exempt':
            return True, "Exempt organization"

        # Check subscription tier exists and is valid
        if not organization.tier:
            return False, "No valid subscription tier"

        # Check if tier is available and customer-facing
        if not organization.tier.is_available:
            return False, "Subscription tier is not available"

        # For billing-required tiers, check billing status
        if organization.tier.requires_stripe_billing or organization.tier.requires_whop_billing:
            # Check subscription status
            if organization.subscription_status not in ['active', 'trialing']:
                return False, "Subscription not active"

            # Additional billing validations can be added here
            # e.g., check for past due payments, etc.

        return True, "Active subscription"

    @staticmethod
    def get_user_effective_permissions(user):
        """
        Get all effective permissions for a user based on the authorization hierarchy
        """
        # Developers in non-customer mode have full access
        if user.user_type == 'developer':
            selected_org_id = session.get('dev_selected_org_id')
            if not selected_org_id:
                from ..models.permission import Permission
                return [p.name for p in Permission.query.filter_by(is_active=True).all()]

        # Get organization
        from .permissions import get_effective_organization
        organization = get_effective_organization()

        if not organization:
            return []

        # Check subscription standing
        subscription_ok, _ = AuthorizationHierarchy.check_subscription_standing(organization)
        if not subscription_ok:
            return []

        # Get tier-allowed permissions
        tier_permissions = AuthorizationHierarchy.get_tier_allowed_permissions(organization)

        # Organization owners get all tier-allowed permissions
        if user.user_type == 'organization_owner':
            return tier_permissions

        # Other users get intersection of tier permissions and role permissions
        user_permissions = set()
        user_roles = user.get_active_roles()

        for role in user_roles:
            role_permissions = [p.name for p in role.get_permissions()]
            # Only add permissions that are both in role AND allowed by tier
            for perm in role_permissions:
                if perm in tier_permissions:
                    user_permissions.add(perm)

        return list(user_permissions)

class FeatureGate:
    """Feature gating based on subscription tiers"""

    @staticmethod
    def is_feature_available(feature_name, organization=None):
        """Check if a feature is available to the organization's subscription tier"""
        if not organization:
            from .permissions import get_effective_organization
            organization = get_effective_organization()

        if not organization:
            return False

        # Check subscription standing first
        subscription_ok, _ = AuthorizationHierarchy.check_subscription_standing(organization)
        if not subscription_ok:
            return False

        # Load tier configuration
        from ..blueprints.developer.subscription_tiers import load_tiers_config
        tiers_config = load_tiers_config()

        tier_key = organization.effective_subscription_tier
        tier_data = tiers_config.get(tier_key, {})

        available_features = tier_data.get('features', [])
        return feature_name in available_features

    @staticmethod
    def check_usage_limits(limit_name, current_usage, organization=None):
        """Check if current usage is within subscription tier limits"""
        if not organization:
            from .permissions import get_effective_organization
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