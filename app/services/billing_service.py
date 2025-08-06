
from datetime import datetime, timedelta
from ..models.subscription_tier import SubscriptionTier
from ..models.models import Organization
from ..extensions import db
from ..utils.timezone_utils import TimezoneUtils
import logging

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
    def get_live_pricing_data():
        """Get live pricing data for signup page - always fetch from Stripe"""
        from .stripe_service import StripeService
        
        pricing_data = {}
        
        for tier_obj in BillingService.get_available_tiers():
            # Always fetch live pricing from Stripe
            live_price = None
            if tier_obj.stripe_lookup_key:
                try:
                    live_price = StripeService.get_price_for_lookup_key(tier_obj.stripe_lookup_key)
                except Exception as e:
                    logger.warning(f"Failed to fetch Stripe price for {tier_obj.key}: {e}")
            
            pricing_data[tier_obj.key] = {
                'name': tier_obj.name,
                'price': live_price or 'Contact for pricing',  # Show contact if Stripe fails
                'features': tier_obj.get_permissions(),
                'user_limit': tier_obj.user_limit,
                'stripe_lookup_key': tier_obj.stripe_lookup_key,
                'whop_product_key': tier_obj.whop_product_key,
                'description': tier_obj.description,
                'billing_cycle': 'month'  # Default billing cycle
            }

        return pricing_data
    
    @staticmethod
    def generate_offline_license(organization):
        """Generate offline license data for downloaded desktop app"""
        if not organization or not organization.subscription_tier_obj:
            return None
            
        # Cache current tier data for offline use
        license_data = {
            'organization_id': organization.id,
            'organization_name': organization.name,
            'tier_key': organization.subscription_tier_obj.key,
            'tier_name': organization.subscription_tier_obj.name,
            'permissions': organization.subscription_tier_obj.get_permissions(),
            'user_limit': organization.subscription_tier_obj.user_limit,
            'issued_at': TimezoneUtils.utc_now().isoformat(),
            'expires_at': (TimezoneUtils.utc_now() + timedelta(days=30)).isoformat(),
            'billing_status': organization.billing_status if hasattr(organization, 'billing_status') else 'active'
        }
        
        # Store in organization for offline access
        organization.offline_tier_cache = license_data
        organization.last_online_sync = TimezoneUtils.utc_now()
        db.session.commit()
        
        logger.info(f"Generated offline license for organization {organization.id}")
        return license_data

    @staticmethod
    def validate_offline_license(organization):
        """Validate cached offline license"""
        if not organization or not organization.offline_tier_cache:
            return False, "No offline license available"
        
        try:
            expires_at = datetime.fromisoformat(organization.offline_tier_cache['expires_at'])
            if TimezoneUtils.utc_now() > expires_at:
                return False, "Offline license expired"
                
            billing_status = organization.offline_tier_cache.get('billing_status', 'active')
            if billing_status != 'active':
                return False, "Billing status invalid"
                
            return True, "Offline license valid"
            
        except Exception as e:
            logger.error(f"Error validating offline license: {e}")
            return False, "License validation failed"

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
