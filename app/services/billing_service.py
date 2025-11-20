from datetime import datetime, timedelta
import logging
from collections.abc import Mapping

from flask import current_app
from sqlalchemy import select

from ..models.subscription_tier import SubscriptionTier
from ..models.models import Organization
from ..extensions import db
from ..utils.timezone_utils import TimezoneUtils

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
        return str(tier.id) if tier else 'exempt'

    @staticmethod
    def assign_tier_to_organization(organization, tier_key):
        """Assign a subscription tier to an organization. tier_key is a tier ID string."""
        try:
            tier_id = int(tier_key)
        except (TypeError, ValueError):
            tier_id = None
        tier = SubscriptionTier.query.get(tier_id) if tier_id is not None else None
        if not tier:
            # Fallback to any exempt tier
            tier = SubscriptionTier.query.filter_by(billing_provider='exempt').first()

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
                key = str(tier.id)
                if tier.is_billing_exempt:
                    # Exempt tiers
                    pricing_data['tiers'][key] = {
                        'name': tier.name,
                        'description': getattr(tier, 'description', ''),
                        'price': 'Free',
                        'billing_cycle': 'exempt',
                        'available': True,
                        'provider': 'exempt',
                        'features': [p.name for p in getattr(tier, 'permissions', [])]
                    }
                elif tier.billing_provider == 'stripe':
                    # Get live Stripe pricing
                    from .stripe_service import StripeService
                    stripe_pricing = StripeService.get_live_pricing_for_tier(tier)
                    
                    pricing_data['tiers'][key] = {
                        'name': tier.name,
                        'description': getattr(tier, 'description', ''),
                        'price': stripe_pricing['formatted_price'] if stripe_pricing else 'N/A',
                        'billing_cycle': stripe_pricing['billing_cycle'] if stripe_pricing else 'monthly',
                        'available': stripe_pricing is not None,
                        'provider': 'stripe',
                        'features': [p.name for p in getattr(tier, 'permissions', [])]
                    }
                elif tier.billing_provider == 'whop':
                    # Whop is stubbed for now
                    pricing_data['tiers'][key] = {
                        'name': tier.name,
                        'description': getattr(tier, 'description', ''),
                        'price': 'Contact Sales',
                        'billing_cycle': 'monthly',
                        'available': False,  # Disabled for now
                        'provider': 'whop',
                        'features': [p.name for p in getattr(tier, 'permissions', [])]
                    }
            
            return pricing_data
            
        except Exception as e:
            logger.error(f"Error getting comprehensive pricing: {e}")
            return {'tiers': {}, 'available': False, 'error': str(e)}

    @staticmethod
    def create_checkout_session(
        tier_key,
        user_email,
        user_name,
        success_url,
        cancel_url,
        metadata=None,
        existing_customer_id=None,
    ):
        """Create checkout session with appropriate provider. tier_key is a tier ID string."""
        try:
            tier_id = int(tier_key)
        except (TypeError, ValueError):
            tier_id = None
        tier = SubscriptionTier.query.get(tier_id) if tier_id is not None else None
        if not tier:
            logger.error(f"Tier {tier_key} not found")
            return None
            
        if tier.is_billing_exempt:
            logger.warning(f"Cannot create checkout for exempt tier {tier_key}")
            return None
            
        if tier.billing_provider == 'stripe':
            from .stripe_service import StripeService
            return StripeService.create_checkout_session_for_tier(
                tier,
                customer_email=user_email,
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata,
                client_reference_id=None,
                phone_required=True,
                allow_promo=True,
                existing_customer_id=existing_customer_id,
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

        if isinstance(organization, Mapping):
            billing_status = organization.get('billing_status') or 'active'
            is_active = organization.get('is_active', True)
            is_exempt = organization.get('is_billing_exempt', False)
            subscription_tier_id = organization.get('subscription_tier_id')
        else:
            billing_status = getattr(organization, 'billing_status', 'active') or 'active'
            is_active = getattr(organization, 'is_active', True)
            tier_obj = getattr(organization, 'subscription_tier_obj', None)
            is_exempt = tier_obj.is_billing_exempt if tier_obj else False
            subscription_tier_id = getattr(organization, 'subscription_tier_id', None)

        if not is_active:
            return False, "organization_suspended"

        if not subscription_tier_id:
            return False, "no_tier_assigned"

        if is_exempt:
            return True, "exempt_tier"

        billing_status = billing_status.lower()
        if billing_status == 'active':
            return True, "billing_active"
        if billing_status in ['payment_failed', 'past_due']:
            return False, "payment_required"
        if billing_status in ['canceled', 'cancelled']:
            return False, "subscription_canceled"
        if billing_status == 'suspended':
            return False, "organization_suspended"

        return True, "tier_valid"