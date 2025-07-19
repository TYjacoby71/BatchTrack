
"""
Trial and Billing Management Service

Handles trial periods, billing conversions, and subscription management.
"""
from datetime import datetime, timedelta
from flask import current_app
from ..models import db, Organization, User
from ..utils.timezone_utils import TimezoneUtils
import logging

logger = logging.getLogger(__name__)

class TrialManagementService:
    """Service for managing trial periods and billing transitions"""
    
    @staticmethod
    def check_expired_trials():
        """Check for expired trials and convert to paid or suspend"""
        today = TimezoneUtils.utc_now().date()
        
        # Find organizations with expired trials
        expired_orgs = Organization.query.filter(
            Organization.subscription_tier == 'trial',
            Organization.trial_end_date <= today,
            Organization.is_active == True
        ).all()
        
        logger.info(f"Found {len(expired_orgs)} expired trials to process")
        
        for org in expired_orgs:
            try:
                if org.billing_info and org.stripe_customer_id:
                    # Convert to paid subscription
                    TrialManagementService._convert_to_paid(org)
                else:
                    # Suspend organization for missing billing
                    TrialManagementService._suspend_for_billing(org)
                    
            except Exception as e:
                logger.error(f"Error processing expired trial for org {org.id}: {str(e)}")
                continue
                
        db.session.commit()
        return len(expired_orgs)
    
    @staticmethod
    def _convert_to_paid(organization):
        """Convert trial organization to paid subscription"""
        # In production, this would:
        # 1. Create subscription in payment processor
        # 2. Charge the stored payment method
        # 3. Set up recurring billing
        
        organization.subscription_tier = 'solo'  # Default tier
        organization.subscription_status = 'active'
        organization.next_billing_date = TimezoneUtils.utc_now() + timedelta(days=30)
        
        # Send welcome email to paid subscriber
        TrialManagementService._send_conversion_email(organization, success=True)
        
        logger.info(f"Converted organization {organization.id} to paid subscription")
    
    @staticmethod
    def _suspend_for_billing(organization):
        """Suspend organization for missing billing information"""
        organization.subscription_status = 'past_due'
        organization.is_active = False  # Suspend access
        
        # Send billing reminder email
        TrialManagementService._send_conversion_email(organization, success=False)
        
        logger.info(f"Suspended organization {organization.id} for missing billing")
    
    @staticmethod
    def _send_conversion_email(organization, success=True):
        """Send email about trial conversion"""
        # This would integrate with your email service
        # For now, just log the action
        if success:
            logger.info(f"Would send welcome email to {organization.contact_email}")
        else:
            logger.info(f"Would send billing reminder to {organization.contact_email}")
    
    @staticmethod
    def get_trial_status(organization):
        """Get trial status information for an organization"""
        if organization.subscription_tier != 'trial':
            return {'is_trial': False}
            
        if not organization.trial_end_date:
            return {'is_trial': False}
            
        today = TimezoneUtils.utc_now().date()
        trial_end = organization.trial_end_date.date()
        days_remaining = (trial_end - today).days
        
        return {
            'is_trial': True,
            'trial_end_date': trial_end,
            'days_remaining': max(0, days_remaining),
            'is_expired': days_remaining < 0,
            'requires_billing': not bool(organization.billing_info)
        }
    
    @staticmethod
    def extend_trial(organization_id, additional_days, reason=None):
        """Extend trial period for an organization"""
        org = Organization.query.get(organization_id)
        if not org:
            return False
            
        if org.subscription_tier == 'trial' and org.trial_end_date:
            org.trial_end_date += timedelta(days=additional_days)
            db.session.commit()
            
            logger.info(f"Extended trial for org {org.id} by {additional_days} days. Reason: {reason}")
            return True
            
        return False

# CLI command to check expired trials (run this daily via cron)
def check_expired_trials_command():
    """CLI command to process expired trials"""
    with current_app.app_context():
        processed = TrialManagementService.check_expired_trials()
        print(f"Processed {processed} expired trials")
        return processed
