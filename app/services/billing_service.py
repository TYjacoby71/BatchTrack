from datetime import datetime, timedelta
from ..models.subscription_tier import SubscriptionTier
from ..models.models import Organization
from ..extensions import db
from ..utils.timezone_utils import TimezoneUtils
import logging

logger = logging.getLogger(__name__)

class BillingService:
    """
    Unified billing service interface - routes to appropriate billing provider
    Currently supports: Stripe (active), Whop (stubbed for future)
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
        from .whop_service import WhopService

        # Only get pricing from actual billing providers - no fallbacks
        try:
            # For now, only Stripe is active - Whop is stubbed
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
    def get_comprehensive_pricing_data():
        """Get comprehensive pricing data with tier information"""
        try:
            # Get available tiers
            tiers = SubscriptionTier.query.filter_by(is_customer_facing=True).all()
            pricing_data = {'tiers': {}, 'available': True}
            
            for tier in tiers:
                if tier.is_billing_exempt:
                    # Exempt tiers
                    pricing_data['tiers'][tier.key] = {
                        'name': tier.name,
                        'description': getattr(tier, 'description', ''),
                        'price': 'Free',
                        'billing_cycle': 'exempt',
                        'available': True,
                        'provider': 'exempt',
                        'features': getattr(tier, 'features', [])
                    }
                elif tier.billing_provider == 'stripe':
                    # Get live Stripe pricing (monthly and yearly when available)
                    from .stripe_service import StripeService
                    stripe_pricing = StripeService.get_live_pricing_for_tier(tier)

                    pricing_entry = {
                        'name': tier.name,
                        'description': getattr(tier, 'description', ''),
                        'price': 'N/A',
                        'price_yearly': None,
                        'billing_cycle': 'monthly',
                        'available': stripe_pricing is not None,
                        'provider': 'stripe',
                        'features': getattr(tier, 'features', [])
                    }

                    if stripe_pricing:
                        if stripe_pricing.get('price_monthly'):
                            pricing_entry['price'] = stripe_pricing['price_monthly']
                        elif stripe_pricing.get('price_yearly'):
                            # Fall back to yearly if monthly missing
                            pricing_entry['price'] = stripe_pricing['price_yearly']
                            pricing_entry['billing_cycle'] = 'yearly'
                        if stripe_pricing.get('price_yearly'):
                            pricing_entry['price_yearly'] = stripe_pricing['price_yearly']

                    pricing_data['tiers'][tier.key] = pricing_entry
                elif tier.billing_provider == 'whop':
                    # Whop is stubbed for now
                    pricing_data['tiers'][tier.key] = {
                        'name': tier.name,
                        'description': getattr(tier, 'description', ''),
                        'price': 'Contact Sales',
                        'billing_cycle': 'monthly',
                        'available': False,  # Disabled for now
                        'provider': 'whop',
                        'features': getattr(tier, 'features', [])
                    }
            
            return pricing_data
            
        except Exception as e:
            logger.error(f"Error getting comprehensive pricing: {e}")
            return {'tiers': {}, 'available': False, 'error': str(e)}

    @staticmethod
    def create_checkout_session(tier_key, user_email, user_name, success_url, cancel_url, metadata=None):
        """Create checkout session with appropriate provider"""
        tier = SubscriptionTier.query.filter_by(key=tier_key).first()
        if not tier:
            logger.error(f"Tier {tier_key} not found")
            return None
            
        if tier.is_billing_exempt:
            logger.warning(f"Cannot create checkout for exempt tier {tier_key}")
            return None
            
        if tier.billing_provider == 'stripe':
            from .stripe_service import StripeService
            return StripeService.create_checkout_session_for_tier(
                tier, user_email, user_name, success_url, cancel_url, metadata
            )
        elif tier.billing_provider == 'whop':
            # Whop is stubbed for now
            logger.warning("Whop billing is not yet implemented")
            return None
        else:
            logger.error(f"Unknown billing provider: {tier.billing_provider}")
            return None

    @staticmethod
    def handle_webhook_event(provider, event_data):
        """Route webhook to appropriate provider"""
        if provider == 'stripe':
            from .stripe_service import StripeService
            return StripeService.handle_webhook_event(event_data)
        elif provider == 'whop':
            # Whop webhooks stubbed for now
            logger.warning("Whop webhook handling not yet implemented")
            return 200
        else:
            logger.error(f"Unknown webhook provider: {provider}")
            return 400

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
            elif organization.billing_status == 'suspended':
                return False, "organization_suspended"

        elif organization.billing_status == 'canceled':
                return False, "subscription_canceled"

        return True, "tier_valid"