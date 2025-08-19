from datetime import datetime, timedelta
from ..models.subscription_tier import SubscriptionTier
from ..models.models import Organization
from ..extensions import db
from ..utils.timezone_utils import TimezoneUtils
import logging

logger = logging.getLogger(__name__)

class BillingService:
    """
    Clean billing service - NO hardcoded pricing
    All pricing comes from external billing providers (Stripe, Whop) or environment config
    """

    @staticmethod
    def get_tier_for_organization(organization):
        """Get the effective subscription tier for an organization"""
        if not organization or not organization.subscription_tier_id:
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
        if not organization or not organization.subscription_tier_obj:
            return False

        current_user_count = organization.users.count()
        limit = organization.subscription_tier_obj.user_limit

        if limit == -1:  # Unlimited
            return True

        return (current_user_count + count) <= limit

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
            is_customer_facing=True
        ).all()

    @staticmethod
    def get_live_pricing_data():
        """Get live pricing data from external billing providers ONLY"""
        from .stripe_service import StripeService

        # Only get pricing from actual billing providers - no fallbacks
        try:
            return StripeService.get_all_available_pricing()
        except Exception as e:
            logger.warning(f"Could not fetch live pricing: {e}")
            return {
                'tiers': [],
                'currency': 'USD',
                'billing_cycles': ['monthly', 'yearly'],
                'available': False,
                'error': 'Pricing unavailable - check billing provider configuration'
            }

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

        # Exempt tiers always have access
        if tier_obj.is_billing_exempt:
            return True, "exempt_tier"

        # Check billing status for paid tiers
        if hasattr(organization, 'billing_status'):
            if organization.billing_status == 'active':
                return True, "billing_active"
            elif organization.billing_status in ['payment_failed', 'past_due']:
                return False, "payment_required"
            elif organization.billing_status == 'canceled':
                return False, "subscription_canceled"

        return True, "tier_valid"