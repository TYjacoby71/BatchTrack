
from datetime import datetime, timedelta
from flask import current_app
from ..models import db, Organization, Subscription
from ..utils.timezone_utils import TimezoneUtils
import logging

logger = logging.getLogger(__name__)

class SubscriptionService:
    """Service for managing flexible subscriptions"""
    
    @staticmethod
    def create_trial_subscription(organization, trial_days=30, trial_tier='team'):
        """Create a new trial subscription"""
        trial_end = TimezoneUtils.utc_now() + timedelta(days=trial_days)
        
        subscription = Subscription(
            organization_id=organization.id,
            tier='free',  # Base tier
            status='trialing',
            trial_start=TimezoneUtils.utc_now(),
            trial_end=trial_end,
            trial_days_remaining=trial_days,
            trial_tier=trial_tier,  # What they get during trial
            notes=f"Trial created for {trial_days} days"
        )
        
        db.session.add(subscription)
        db.session.commit()
        return subscription
    
    @staticmethod
    def extend_trial(organization, days, reason="Manual extension"):
        """Extend trial period"""
        subscription = organization.subscription
        if not subscription:
            return False
            
        return subscription.extend_trial(days, reason)
    
    @staticmethod
    def add_comp_time(organization, months, reason="Comp time"):
        """Add complimentary months"""
        subscription = organization.subscription
        if not subscription:
            return False
            
        subscription.add_comp_months(months, reason)
        return True
    
    @staticmethod
    def apply_discount(organization, percent, end_date=None, reason="Discount applied"):
        """Apply percentage discount"""
        subscription = organization.subscription
        if not subscription:
            return False
            
        subscription.apply_discount(percent, end_date, reason)
        return True
    
    @staticmethod
    def check_access(organization):
        """Check if organization has access based on subscription"""
        subscription = organization.subscription
        if not subscription:
            return False
            
        return subscription.is_active
    
    @staticmethod
    def get_effective_tier(organization):
        """Get the effective subscription tier"""
        subscription = organization.subscription
        if not subscription:
            return 'free'
            
        return subscription.effective_tier
