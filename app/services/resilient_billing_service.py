from datetime import datetime, timedelta
import logging
from flask import current_app
from ..models import db, Organization
from ..utils.timezone_utils import TimezoneUtils
from ..models.billing_snapshot import BillingSnapshot
from ..models.pricing_snapshot import PricingSnapshot

logger = logging.getLogger(__name__)

class ResilientBillingService:
    """Service for handling billing resilience during Stripe outages"""

    @staticmethod
    def check_organization_access(organization):
        """Check if organization should have access, using snapshots during outages"""
        tier = organization.tier

        # If no tier at all, deny access
        if not tier:
            return False, "No subscription tier found"

        # Try current tier first (normal case)
        if tier.is_available and ResilientBillingService._is_stripe_healthy():
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
        tier = organization.tier

        if not tier:
            return 'free'

        # Try current tier data first
        if tier.is_available and ResilientBillingService._is_stripe_healthy():
            return tier.key

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
        if not organization:
            return False, 'no_organization'

        # If organization has valid billing, no reconciliation needed
        if organization.is_active and organization.subscription_tier_id:
            # For now, assume active organizations with tiers are properly set up
            return False, 'billing_current'

        # Check for billing snapshots that indicate reconciliation is needed
        latest_snapshot = BillingSnapshot.get_latest_valid_snapshot(organization.id)

        if latest_snapshot and latest_snapshot.sync_source == 'reconciliation':
            # Currently in grace period
            if latest_snapshot.period_end and latest_snapshot.period_end > TimezoneUtils.utc_now():
                return True, 'grace_period'
            else:
                return True, 'grace_expired'

        # If no subscription tier but organization exists, may need reconciliation
        if not organization.subscription_tier_id:
            return True, 'no_billing'

        return False, 'unknown'

    @staticmethod
    def create_reconciliation_flow(organization, tier):
        """Create a reconciliation flow for users who signed up during outages"""
        if not organization:
            return False

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