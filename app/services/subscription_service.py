
from datetime import datetime, timedelta
from flask import current_app
from ..models import db, Organization, SubscriptionTier
from ..utils.timezone_utils import TimezoneUtils
import logging

logger = logging.getLogger(__name__)

class SubscriptionService:
    """Service for managing subscriptions and billing"""

    @staticmethod
    def create_subscription_for_organization(organization, tier_key='exempt'):
        """Assign a subscription tier to an organization"""
        # Find the tier by key
        tier = SubscriptionTier.query.filter_by(key=tier_key).first()
        if not tier:
            # If tier doesn't exist, assign exempt as fallback
            tier = SubscriptionTier.query.filter_by(key='exempt').first()

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
            return False  # No tier = no access

        limit = tier_obj.user_limit

        if limit == -1:  # Unlimited
            return True

        return (current_user_count + count) <= limit

    @staticmethod
    def create_pending_subscription(organization, selected_tier):
        """Create a pending subscription that will be activated by Stripe"""
        # Find the SubscriptionTier by key
        tier = SubscriptionTier.query.filter_by(key=selected_tier).first()
        if not tier:
            logger.warning(f"Tier '{selected_tier}' not found")
            return None

        organization.subscription_tier_id = tier.id
        db.session.commit()

        return tier

    @staticmethod
    def check_access(organization):
        """Check if organization has access based on tier configuration"""
        tier = organization.subscription_tier_obj
        if not tier:
            return False

        # Access is based on the tier's availability and status
        return tier.is_available

    @staticmethod
    def get_effective_tier(organization):
        """Get the effective subscription tier"""
        tier = organization.subscription_tier_obj
        if not tier:
            return None

        return tier.key

    @staticmethod
    def create_exempt_subscription(organization, reason="Exempt account"):
        """Create an exempt subscription - only hardcoded tier allowed"""
        # Find the "exempt" tier (should be seeded)
        exempt_tier = SubscriptionTier.query.filter_by(key='exempt').first()
        if not exempt_tier:
            logger.error("Exempt tier not found - ensure seeding is complete")
            return None

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
                'tier': None,
                'is_active': False
            }

        return {
            'has_subscription': True,
            'status': tier.status or 'active',
            'tier': tier.key,
            'is_active': tier.is_available,
            'stripe_subscription_id': tier.stripe_subscription_id,
            'current_period_end': tier.current_period_end,
            'next_billing_date': tier.next_billing_date
        }

    @staticmethod
    def validate_permission_for_tier(organization, permission_name):
        """Validate if permission is allowed for organization's subscription tier"""
        tier = organization.subscription_tier_obj
        if not tier:
            logger.warning(f"No tier found for organization {organization.id}")
            return False

        # Check if tier has the permission
        has_permission = tier.has_permission(permission_name)
        
        if not has_permission:
            logger.info(f"Permission '{permission_name}' denied for tier '{tier.key}'")

        return has_permission
