
from datetime import datetime, timedelta
from flask import current_app
from ..models import db, Organization, Subscription
from ..utils.timezone_utils import TimezoneUtils
import logging

logger = logging.getLogger(__name__)

class SubscriptionService:
    """Service for managing Stripe-based subscriptions"""
    
    @staticmethod
    def create_pending_subscription(organization, selected_tier='team'):
        """Create a pending subscription that will be activated by Stripe"""
        subscription = Subscription(
            organization_id=organization.id,
            tier='free',  # Will be updated by Stripe webhook
            status='pending',  # Waiting for Stripe checkout
            notes=f"Pending Stripe subscription for {selected_tier} tier"
        )
        
        db.session.add(subscription)
        db.session.commit()
        return subscription
    
    @staticmethod
    def check_access(organization):
        """Check if organization has access based on Stripe subscription"""
        subscription = organization.subscription
        if not subscription:
            return False
            
        # Only active and trialing statuses from Stripe allow access
        return subscription.status in ['active', 'trialing']
    
    @staticmethod
    def get_effective_tier(organization):
        """Get the effective subscription tier from Stripe data"""
        subscription = organization.subscription
        if not subscription:
            return 'free'
            
        if subscription.tier == 'exempt':
            return 'enterprise'  # Exempt accounts get enterprise features
            
        # During Stripe trials, user gets the tier they're paying for
            
        return subscription.tier
    
    @staticmethod
    def create_exempt_subscription(organization, reason="Exempt account"):
        """Create an exempt subscription for gifted accounts"""
        subscription = Subscription(
            organization_id=organization.id,
            tier='exempt',
            status='active',
            notes=f"Exempt subscription: {reason}"
        )
        
        db.session.add(subscription)
        db.session.commit()
        return subscription
    
    @staticmethod
    def is_reserved_organization(org_id):
        """Check if organization is reserved for owner/testing"""
        return org_id == 1  # Organization 1 is reserved
    
    @staticmethod
    def setup_reserved_organization():
        """Set up organization 1 as reserved for owner"""
        from ..models import Organization
        
        org = Organization.query.get(1)
        if org and (not hasattr(org, 'subscription') or not org.subscription):
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
        subscription = organization.subscription
        if not subscription:
            return {
                'has_subscription': False,
                'status': 'none',
                'tier': 'free',
                'is_active': False
            }
        
        return {
            'has_subscription': True,
            'status': subscription.status,
            'tier': subscription.effective_tier,
            'is_active': subscription.is_active,
            'stripe_subscription_id': subscription.stripe_subscription_id,
            'current_period_end': subscription.current_period_end,
            'next_billing_date': subscription.next_billing_date
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
