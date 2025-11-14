from datetime import datetime, timedelta
import logging
from collections.abc import Mapping

from flask import current_app
from sqlalchemy import select

from ..models.subscription_tier import SubscriptionTier
from ..models.models import Organization
from ..extensions import db, cache
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
            BillingService.invalidate_organization_cache(organization.id)

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
    def create_checkout_session(tier_key, user_email, user_name, success_url, cancel_url, metadata=None):
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
        if isinstance(organization, Mapping):
            return BillingService._validate_snapshot(organization)

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

    @staticmethod
    def _validate_snapshot(snapshot):
        if not snapshot:
            return False, "no_organization"

        if not snapshot.get('is_active', True):
            return False, "organization_suspended"

        if snapshot.get('is_billing_exempt', False):
            return True, "exempt_tier"

        billing_status = snapshot.get('billing_status', 'active') or 'active'

        if billing_status == 'active':
            return True, "billing_active"
        if billing_status in ['payment_failed', 'past_due']:
            return False, "payment_required"
        if billing_status == 'canceled':
            return False, "subscription_canceled"
        if billing_status == 'suspended':
            return False, "organization_suspended"

        return True, "tier_valid"

    @staticmethod
    def get_organization_billing_snapshot(organization_id):
        """Fetch and cache the billing snapshot for an organization."""
        if not organization_id:
            return None

        cache_key = f"billing:snapshot:{organization_id}"
        snapshot = None

        if cache:
            snapshot = cache.get(cache_key)
            if snapshot is not None:
                return snapshot

        stmt = (
            select(
                Organization.id.label('organization_id'),
                Organization.is_active,
                Organization.billing_status,
                Organization.subscription_tier_id,
                SubscriptionTier.billing_provider,
            )
            .join(SubscriptionTier, SubscriptionTier.id == Organization.subscription_tier_id, isouter=True)
            .where(Organization.id == organization_id)
        )

        try:
            row = db.session.execute(stmt).mappings().one_or_none()
        except Exception as exc:
            logger.warning("Could not load billing snapshot for org %s: %s", organization_id, exc)
            return None

        if not row:
            return None

        snapshot = {
            'organization_id': row.get('organization_id'),
            'is_active': row.get('is_active', True),
            'billing_status': row.get('billing_status') or 'active',
            'subscription_tier_id': row.get('subscription_tier_id'),
            'is_billing_exempt': row.get('billing_provider') == 'exempt',
        }

        if cache:
            timeout = current_app.config.get('BILLING_STATUS_CACHE_TTL', 120)
            try:
                cache.set(cache_key, snapshot, timeout=timeout)
            except Exception as exc:  # pragma: no cover - cache backend failures should not break app
                logger.debug("Failed to cache billing snapshot for org %s: %s", organization_id, exc)

        return snapshot

    @staticmethod
    def invalidate_organization_cache(organization_id):
        if not organization_id or not cache:
            return
        cache_key = f"billing:snapshot:{organization_id}"
        try:
            cache.delete(cache_key)
        except Exception as exc:  # pragma: no cover
            logger.debug("Failed to invalidate billing cache for org %s: %s", organization_id, exc)