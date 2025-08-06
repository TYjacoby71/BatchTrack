import logging
from flask import current_app
from ..models import db, SubscriptionTier, Organization
from ..utils.timezone_utils import TimezoneUtils
from ..blueprints.developer.subscription_tiers import load_tiers_config

logger = logging.getLogger(__name__)

class BillingService:
    """Service for subscription tier authorization and basic management"""

    @staticmethod
    def get_tier_for_organization(organization):
        """Get the effective subscription tier for an organization"""
        if not organization:
            return 'exempt'

        if not organization.subscription_tier_id:
            return 'exempt'

        tier = SubscriptionTier.query.get(organization.subscription_tier_id)
        return tier.key if tier else 'exempt'

    @staticmethod
    def assign_tier_to_organization(organization, tier_key):
        """Assign a subscription tier to an organization"""
        tier = SubscriptionTier.query.filter_by(key=tier_key).first()
        if not tier:
            # Fallback to exempt tier
            tier = SubscriptionTier.query.filter_by(key='exempt').first()

        if tier:
            organization.subscription_tier_id = tier.id
            db.session.commit()
            logger.info(f"Assigned tier {tier_key} to organization {organization.id}")

        return tier

    @staticmethod
    def can_add_users(organization, count=1):
        """Check if organization can add more users based on subscription tier"""
        current_user_count = organization.users.count()

        tier_obj = organization.subscription_tier_obj
        if not tier_obj:
            return False  # No tier = no access

        limit = tier_obj.user_limit
        if limit == -1:  # Unlimited
            return True

        return (current_user_count + count) <= limit

    @staticmethod
    def get_tier_permissions(tier_key):
        """Get permissions for a specific tier"""
        tier = SubscriptionTier.query.filter_by(key=tier_key).first()
        if not tier:
            return []
        return tier.get_permissions()

    @staticmethod
    def has_tier_permission(organization, permission_name):
        """Check if organization's tier has a specific permission"""
        if not organization or not organization.subscription_tier_obj:
            return False
        return organization.subscription_tier_obj.has_permission(permission_name)

    @staticmethod
    def get_available_tiers():
        """Get all available customer-facing tiers"""
        return SubscriptionTier.query.filter_by(
            is_customer_facing=True,
            is_available=True
        ).all()

    @staticmethod
    def get_simple_pricing_data():
        """Get basic pricing data for tiers - simple version for signup"""
        tiers_config = load_tiers_config()
        pricing_data = {}
        
        for tier_obj in BillingService.get_available_tiers():
            tier_config = tiers_config.get(tier_obj.key, {})
            pricing_data[tier_obj.key] = {
                'name': tier_obj.name,
                'price': tier_obj.fallback_price,
                'features': tier_config.get('features', []),
                'user_limit': tier_obj.user_limit,
                'stripe_lookup_key': tier_obj.stripe_lookup_key,
                'whop_product_key': tier_obj.whop_product_key
            }
        
        return pricing_data

    @staticmethod
    def validate_tier_access(organization):
        """Validate that organization has valid tier access"""
        if not organization:
            return False, "no_organization"

        if not organization.is_active:
            return False, "organization_suspended"

        tier_obj = organization.subscription_tier_obj
        if not tier_obj:
            return False, "no_tier_assigned"

        # If tier is exempt from billing, access is always valid
        if tier_obj.is_exempt_from_billing:
            return True, "exempt_tier"

        # For billing tiers, organization should handle validation elsewhere
        # This service only handles tier-based authorization
        return True, "tier_valid"