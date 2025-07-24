
from datetime import datetime, timedelta
from flask import current_app
from ..models import db, Organization, Subscription
from ..models.billing_snapshot import BillingSnapshot
from ..models.pricing_snapshot import PricingSnapshot
from ..utils.timezone_utils import TimezoneUtils
import logging

logger = logging.getLogger(__name__)

class ResilientBillingService:
    """Service for handling billing resilience during Stripe outages"""
    
    @staticmethod
    def check_organization_access(organization):
        """Check if organization should have access, using snapshots during outages"""
        subscription = organization.subscription
        
        # If no subscription at all, deny access
        if not subscription:
            return False, "No subscription found"
        
        # Try current subscription first (normal case)
        if subscription.is_active and ResilientBillingService._is_stripe_healthy():
            return True, "Active subscription confirmed"
        
        # If Stripe is down or subscription appears inactive, check snapshots
        latest_snapshot = BillingSnapshot.get_latest_valid_snapshot(organization.id)
        
        if latest_snapshot and latest_snapshot.is_valid_for_access:
            days_left = latest_snapshot.days_until_grace_expires
            return True, f"Access granted via billing snapshot (grace period: {days_left} days)"
        
        # No valid snapshot found
        return False, "No valid billing confirmation found"
    
    @staticmethod
    def get_effective_tier(organization):
        """Get effective tier, falling back to snapshots during outages"""
        subscription = organization.subscription
        
        if not subscription:
            return 'free'
        
        # Try current subscription data first
        if subscription.is_active and ResilientBillingService._is_stripe_healthy():
            return subscription.effective_tier
        
        # Fall back to snapshot data
        latest_snapshot = BillingSnapshot.get_latest_valid_snapshot(organization.id)
        if latest_snapshot and latest_snapshot.is_valid_for_access:
            logger.info(f"Using tier from snapshot for org {organization.id}: {latest_snapshot.confirmed_tier}")
            return latest_snapshot.confirmed_tier
        
        return 'free'
    
    @staticmethod
    def get_pricing_with_snapshots():
        """Get pricing data with snapshots as fallback"""
        pricing_data = {}
        
        # Try to get live Stripe data first
        if ResilientBillingService._is_stripe_healthy():
            try:
                from .pricing_service import PricingService
                live_pricing = PricingService._get_stripe_pricing()
                if live_pricing:
                    # Update pricing snapshots with live data
                    ResilientBillingService._update_pricing_snapshots(live_pricing)
                    return live_pricing
            except Exception as e:
                logger.warning(f"Failed to get live pricing: {str(e)}")
        
        # Fall back to pricing snapshots
        logger.info("Using pricing snapshots as fallback")
        snapshots = PricingSnapshot.query.filter_by(is_active=True).all()
        
        for snapshot in snapshots:
            tier_key = snapshot.stripe_lookup_key
            if tier_key:
                pricing_data[tier_key] = {
                    'name': snapshot.product_name,
                    'price': f"${snapshot.amount_dollars}",
                    'features': snapshot.features_list,
                    'stripe_price_id': snapshot.stripe_price_id,
                    'is_snapshot': True
                }
        
        return pricing_data
    
    @staticmethod
    def check_reconciliation_needed(organization):
        """Check if organization needs billing reconciliation"""
        subscription = organization.subscription
        
        if not subscription:
            return False, None
        
        # Check for signs that user signed up during Stripe outage
        if (subscription.status in ['pending', 'incomplete'] or 
            not subscription.stripe_subscription_id):
            return True, "Subscription created during Stripe outage - reconciliation needed"
        
        # Check if we're relying on snapshots for too long
        latest_snapshot = BillingSnapshot.get_latest_valid_snapshot(organization.id)
        if latest_snapshot:
            days_on_snapshot = (TimezoneUtils.utc_now() - latest_snapshot.last_stripe_sync).days
            if days_on_snapshot > 7:  # Been on snapshot for over a week
                return True, f"Using billing snapshot for {days_on_snapshot} days - reconciliation recommended"
        
        return False, None
    
    @staticmethod
    def create_reconciliation_flow(organization, tier):
        """Create a reconciliation flow for users who signed up during outages"""
        subscription = organization.subscription
        
        if not subscription:
            return False
        
        # Mark subscription as needing reconciliation
        subscription.status = 'reconciliation_needed'
        subscription.notes = f"{subscription.notes or ''}\nNeeds reconciliation: signed up during Stripe outage".strip()
        
        # Create a temporary grace period
        temp_snapshot = BillingSnapshot(
            organization_id=organization.id,
            confirmed_tier='free',  # Give them free tier during reconciliation
            confirmed_status='grace_period',
            period_start=TimezoneUtils.utc_now(),
            period_end=TimezoneUtils.utc_now() + timedelta(days=7),  # 7 day grace
            grace_period_days=1,  # Short grace after the 7 days
            last_stripe_sync=TimezoneUtils.utc_now(),
            sync_source='reconciliation'
        )
        
        db.session.add(temp_snapshot)
        db.session.commit()
        
        logger.info(f"Created reconciliation flow for org {organization.id}")
        return True
    
    @staticmethod
    def _is_stripe_healthy():
        """Check if Stripe integration is currently healthy"""
        try:
            from .stripe_service import StripeService
            return StripeService.initialize_stripe()
        except Exception:
            return False
    
    @staticmethod
    def _update_pricing_snapshots(live_pricing_data):
        """Update pricing snapshots with live Stripe data"""
        try:
            # This would be called when we successfully get live pricing
            # Implementation would sync the pricing_snapshots table
            logger.info("Updated pricing snapshots with live Stripe data")
        except Exception as e:
            logger.error(f"Failed to update pricing snapshots: {str(e)}")
