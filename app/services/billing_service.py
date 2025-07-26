
import logging
from flask import current_app
from ..models import db, Organization, Permission
from ..blueprints.developer.subscription_tiers import load_tiers_config
from ..utils.timezone_utils import TimezoneUtils

logger = logging.getLogger(__name__)

class BillingService:
    """Service for managing billing business logic"""

    @staticmethod
    def get_tier_permissions(tier_key):
        """Get all permissions for a subscription tier"""
        tiers_config = load_tiers_config()
        tier_data = tiers_config.get(tier_key, {})
        permission_names = tier_data.get('permissions', [])

        # Get actual permission objects
        permissions = Permission.query.filter(Permission.name.in_(permission_names)).all()
        return permissions

    @staticmethod
    def user_has_tier_permission(user, permission_name):
        """Check if user has permission based on their subscription tier"""
        if user.user_type == 'developer':
            return True  # Developers have all permissions

        if not user.organization:
            return False

        # Get organization's subscription tier
        current_tier = user.organization.effective_subscription_tier

        # Get tier permissions
        tiers_config = load_tiers_config()
        tier_data = tiers_config.get(current_tier, {})
        tier_permissions = tier_data.get('permissions', [])

        return permission_name in tier_permissions

    @staticmethod
    def get_available_tiers(customer_facing=True, active=True):
        """Get available subscription tiers with filtering"""
        tiers_config = load_tiers_config()
        
        available_tiers = {}
        for tier_key, tier_data in tiers_config.items():
            # Skip if tier_data is not a dictionary
            if not isinstance(tier_data, dict):
                continue
                
            # Apply filters
            if customer_facing and not tier_data.get('is_customer_facing', True):
                continue
            if active and not tier_data.get('is_available', True):
                continue

            available_tiers[tier_key] = tier_data

        return available_tiers

    @staticmethod
    def build_price_key(tier, billing_cycle='monthly'):
        """Build consistent price key for tiers"""
        if billing_cycle == 'yearly':
            return f"{tier}_yearly"
        return tier

    @staticmethod
    def validate_tier_availability(tier):
        """Validate if a tier is available for purchase"""
        available_tiers = BillingService.get_available_tiers()
        return tier in available_tiers

    @staticmethod
    def check_subscription_access(organization):
        """Check if organization has subscription access"""
        if not organization:
            return False, "No organization found"

        # Use resilient billing service for comprehensive check
        from .resilient_billing_service import ResilientBillingService
        return ResilientBillingService.check_organization_access(organization)

    @staticmethod
    def get_subscription_status_summary(organization):
        """Get comprehensive subscription status for display"""
        if not organization:
            return {
                'has_subscription': False,
                'tier': 'free',
                'status': 'none',
                'is_active': False
            }

        # Get current tier
        current_tier = organization.effective_subscription_tier
        
        # Check if subscription is active
        has_access, reason = BillingService.check_subscription_access(organization)

        return {
            'has_subscription': bool(organization.tier),
            'tier': current_tier,
            'status': 'active' if has_access else 'inactive',
            'is_active': has_access,
            'reason': reason,
            'max_users': organization.get_max_users(),
            'current_users': organization.active_users_count
        }
