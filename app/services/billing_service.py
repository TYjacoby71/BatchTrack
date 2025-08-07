from datetime import datetime, timedelta
from ..models.subscription_tier import SubscriptionTier
from ..models.models import Organization
from ..extensions import db
from ..utils.timezone_utils import TimezoneUtils
import logging

logger = logging.getLogger(__name__)

class BillingService:
    """
    Comprehensive billing service handling both Stripe and Whop integrations
    with offline support and robust error handling
    """

    @staticmethod
    def get_comprehensive_pricing_data():
        """
        Get comprehensive pricing data for display in organization dashboard and settings
        Returns pricing information with fallback for offline mode
        """
        try:
            # Load tier configuration
            from ..blueprints.developer.subscription_tiers import load_tiers_config
            tiers_config = load_tiers_config()

            # Basic pricing structure - can be enhanced with Stripe/Whop data
            pricing_data = {
                'tiers': {},
                'currency': 'USD',
                'billing_cycles': ['monthly', 'yearly'],
                'available': True
            }

            # Convert tier config to pricing display format
            for tier_key, tier_info in tiers_config.items():
                pricing_data['tiers'][tier_key] = {
                    'name': tier_info.get('name', tier_key.title()),
                    'price_monthly': tier_info.get('price_monthly', 0),
                    'price_yearly': tier_info.get('price_yearly', 0),
                    'features': tier_info.get('features', []),
                    'user_limit': tier_info.get('user_limit', 1),
                    'description': tier_info.get('description', ''),
                    'popular': tier_info.get('popular', False)
                }

            return pricing_data

        except Exception as e:
            print(f"Error getting comprehensive pricing data: {str(e)}")
            # Fallback pricing data
            return {
                'tiers': {
                    'free': {'name': 'Free', 'price_monthly': 0, 'price_yearly': 0, 'features': ['Basic features'], 'user_limit': 1},
                    'team': {'name': 'Team', 'price_monthly': 29, 'price_yearly': 290, 'features': ['Team features'], 'user_limit': 10},
                    'enterprise': {'name': 'Enterprise', 'price_monthly': 99, 'price_yearly': 990, 'features': ['All features'], 'user_limit': -1}
                },
                'currency': 'USD',
                'billing_cycles': ['monthly', 'yearly'],
                'available': False,
                'error': 'Pricing data temporarily unavailable'
            }

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
            is_customer_facing=True,
            is_available=True
        ).all()

    @staticmethod
    def get_live_pricing_data():
        """Get live pricing data for signup page"""
        from .stripe_service import StripeService

        # This now calls the clean Stripe service
        return StripeService.get_all_available_pricing()

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

        # Exempt and internal tiers always have access
        if tier_obj.is_exempt_from_billing:
            return True, "exempt_tier"

        # Check if billing verification is required
        if not tier_obj.requires_billing_check:
            return True, "no_billing_required"

        # Check billing status for paid tiers
        if hasattr(organization, 'billing_status'):
            if organization.billing_status == 'active':
                return True, "billing_active"
            elif organization.billing_status in ['payment_failed', 'past_due']:
                return False, "payment_required"
            elif organization.billing_status == 'canceled':
                return False, "subscription_canceled"

        return True, "tier_valid"