# Updated SubscriptionService methods for SubscriptionTier and related models

from datetime import datetime, timedelta
from flask import current_app
from ..models import db, Organization, Subscription
from ..utils.timezone_utils import TimezoneUtils
import logging

logger = logging.getLogger(__name__)

class SubscriptionService:
    """Service for managing subscriptions and billing"""

    @staticmethod
    def create_subscription_for_organization(organization, tier_key='free'):
        """Assign a subscription tier to an organization"""
        # Find the tier by key
        tier = SubscriptionTier.query.filter_by(key=tier_key).first()
        if not tier:
            # Create a free tier if it doesn't exist
            tier = SubscriptionTier.query.filter_by(key='free').first()

        if tier:
            organization.subscription_tier_id = tier.id
            db.session.commit()

        return tier

    @staticmethod
    def get_tier_permissions(tier_key):
        """Get permissions for a subscription tier"""
        tier = SubscriptionTier.query.filter_by(key=tier_key).first()
        if tier:
            return tier.get_permissions()
        return []

    @staticmethod
    def can_add_users(organization, count=1):
        """Check if organization can add more users based on subscription tier"""
        current_user_count = organization.users.count()

        tier_obj = organization.subscription_tier_obj
        if not tier_obj:
            return current_user_count + count <= 1  # Default to 1 user

        limit = tier_obj.user_limit

        if limit == -1:  # Unlimited
            return True

        return (current_user_count + count) <= limit
```@staticmethod
    def create_pending_subscription(organization, selected_tier='team'):
        """Create a pending subscription that will be activated by Stripe"""
        # Find the SubscriptionTier by key
        tier = SubscriptionTier.query.filter_by(key=selected_tier).first()
        if not tier:
            tier = SubscriptionTier.query.filter_by(key='free').first() # Default free tier

        if tier:
            organization.subscription_tier_id = tier.id
            db.session.commit()

        # No actual subscription is created in this method with the new model
        return tier # Return the tier instead.

    @staticmethod
    def check_access(organization):
        """Check if organization has access based on Stripe data"""
        tier = organization.subscription_tier_obj
        if not tier:
            return False

        # Access is based on the tier's status.
        return tier.is_active

    @staticmethod
    def get_effective_tier(organization):
        """Get the effective subscription tier from Stripe data"""
        tier = organization.subscription_tier_obj
        if not tier:
            return 'free'

        return tier.key  # Return the key as the tier name

    @staticmethod
    def create_exempt_subscription(organization, reason="Exempt account"):
        """Create an exempt subscription for gifted accounts"""
        # Find or create the "exempt" tier
        exempt_tier = SubscriptionTier.query.filter_by(key='exempt').first()
        if not exempt_tier:
             exempt_tier = SubscriptionTier(
                key='exempt',
                name='Exempt',
                price=0,
                currency='USD',
                interval='month',
                is_active=True,
                user_limit=-1,  # Unlimited users
                product_id="exempt",
                price_id="exempt",
                lookup_key="exempt"
             )
             db.session.add(exempt_tier)
             db.session.commit()


        organization.subscription_tier_id = exempt_tier.id
        db.session.commit()
        return exempt_tier

    @staticmethod
    def is_reserved_organization(org_id):
        """Check if organization is reserved for owner/testing"""
        return org_id == 1  # Organization 1 is reserved

    @staticmethod
    def setup_reserved_organization():
        """Set up organization 1 as reserved for owner"""
        from ..models import Organization

        org = Organization.query.get(1)
        if org and org.subscription_tier_id is None:
            # Create exempt subscription for org 1
            subscription = SubscriptionService.create_exempt_subscription(
                org,
                "Reserved organization for owner/testing"
            )
            logger.info(f"Created exempt subscription for reserved organization {org.id}")
            return subscription
        return None

    @staticmethod
    def get_subscription_status(organization):
        """Get subscription status information"""
        tier = organization.subscription_tier_obj
        if not tier:
            return {
                'has_subscription': False,
                'status': 'none',
                'tier': 'free',
                'is_active': False
            }

        return {
            'has_subscription': True,
            'status': 'active' if tier.is_active else 'inactive',
            'tier': tier.key,
            'is_active': tier.is_active,
            'stripe_subscription_id': tier.stripe_subscription_id,
            'current_period_end': tier.current_period_end,
            'next_billing_date': tier.next_billing_date
        }

    @staticmethod
    def validate_permission_for_tier(organization, permission_name):
        """Validate if permission is allowed for organization's subscription tier"""
        from ..blueprints.developer.subscription_tiers import load_tiers_config

        effective_tier = SubscriptionService.get_effective_tier(organization)
        tiers_config = load_tiers_config()

        if effective_tier not in tiers_config:
            logger.warning(f"Unknown subscription tier: {effective_tier}")
            return False

        tier_permissions = tiers_config[effective_tier].get('permissions', [])
        is_allowed = permission_name in tier_permissions

        if not is_allowed:
            logger.info(f"Permission '{permission_name}' denied for tier '{effective_tier}'")

        return is_allowed