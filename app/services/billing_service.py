
import logging
from datetime import datetime, timedelta
from flask import current_app
from ..models import db, Organization, Permission
from ..blueprints.developer.subscription_tiers import load_tiers_config
from ..utils.timezone_utils import TimezoneUtils
from ..models.billing_snapshot import BillingSnapshot
from ..models.pricing_snapshot import PricingSnapshot

logger = logging.getLogger(__name__)

class BillingService:
    """Consolidated service for all billing business logic and resilience"""

    @staticmethod
    def get_tier_permissions(tier_key):
        """Get all permissions for a subscription tier"""
        tiers_config = load_tiers_config()
        tier_data = tiers_config.get(tier_key, {})
        permission_names = tier_data.get('permissions', [])

        # Get actual permission objects
        permissions = Permission.query.filter(Permission.name.in_(permission_names)).all()
        return permissions

    @staticmethod
    def user_has_tier_permission(user, permission_name):
        """Check if user has permission based on their subscription tier"""
        if user.user_type == 'developer':
            return True  # Developers have all permissions

        if not user.organization:
            return False

        # Get organization's subscription tier
        current_tier = user.organization.effective_subscription_tier

        # Get tier permissions
        tiers_config = load_tiers_config()
        tier_data = tiers_config.get(current_tier, {})
        tier_permissions = tier_data.get('permissions', [])

        return permission_name in tier_permissions

    @staticmethod
    def get_available_tiers(customer_facing=True, active=True):
        """Get available subscription tiers with filtering"""
        tiers_config = load_tiers_config()

        available_tiers = {}
        for tier_key, tier_data in tiers_config.items():
            # Skip if tier_data is not a dictionary
            if not isinstance(tier_data, dict):
                continue

            # Apply filters
            if customer_facing and not tier_data.get('is_customer_facing', True):
                continue
            if active and not tier_data.get('is_available', True):
                continue

            available_tiers[tier_key] = tier_data

        return available_tiers

    @staticmethod
    def validate_tier_availability(tier_key):
        """Validate that a tier is available for purchase"""
        available_tiers = BillingService.get_available_tiers()
        if tier_key not in available_tiers:
            return False

        # All available tiers are ready for checkout
        return True

    @staticmethod
    def build_price_key(tier, billing_cycle='monthly'):
        """Build Stripe price lookup key from tier and billing cycle"""
        if billing_cycle == 'yearly':
            return f"batchtrack_{tier}_yearly"
        else:
            return f"batchtrack_{tier}_monthly"

    @staticmethod
    def check_organization_access(organization):
        """
        Check if organization should have access, using snapshots during outages.
        Consolidated method that includes resilient billing logic.
        """
        if not organization:
            return False, "No organization found"

        # Exempt organizations always have access
        if organization.effective_subscription_tier == 'exempt':
            return True, "exempt"

        # Developer accounts bypass billing checks
        if organization.id == 1:  # Reserved dev org
            return True, "developer"

        # Check if organization is active
        if not organization.is_active:
            return False, "organization_suspended"

        tier = organization.tier

        # If no tier at all, deny access
        if not tier:
            return False, "No subscription tier found"

        # Try current tier first (normal case)
        if tier.is_available and BillingService._is_stripe_healthy():
            return True, "Active subscription confirmed"

        # If Stripe is down or subscription appears inactive, check snapshots
        latest_snapshot = BillingSnapshot.get_latest_valid_snapshot(organization.id)

        if latest_snapshot and latest_snapshot.is_valid_for_access:
            days_left = latest_snapshot.days_until_grace_expires
            return True, f"Access granted via billing snapshot (grace period: {days_left} days)"

        # No valid snapshot found
        return False, "No valid billing confirmation found"

    @staticmethod
    def check_subscription_access(organization):
        """Alias for check_organization_access for backward compatibility"""
        return BillingService.check_organization_access(organization)

    @staticmethod
    def get_effective_tier(organization):
        """Get effective tier, falling back to snapshots during outages"""
        if not organization:
            return 'exempt'

        tier = organization.tier

        if not tier:
            return 'exempt'

        # Try current tier data first
        if tier.is_available and BillingService._is_stripe_healthy():
            return tier.key

        # Fall back to snapshot data
        latest_snapshot = BillingSnapshot.get_latest_valid_snapshot(organization.id)
        if latest_snapshot and latest_snapshot.is_valid_for_access:
            logger.info(f"Using tier from snapshot for org {organization.id}: {latest_snapshot.confirmed_tier}")
            return latest_snapshot.confirmed_tier

        return 'exempt'

    @staticmethod
    def get_pricing_with_snapshots():
        """Get pricing data with snapshots as fallback for offline usage"""
        pricing_data = {}

        # Try to get live Stripe data first
        if BillingService._is_stripe_healthy():
            try:
                from .pricing_service import PricingService
                live_pricing = PricingService._get_stripe_pricing()
                if live_pricing:
                    # Update pricing snapshots with live data
                    BillingService._update_pricing_snapshots(live_pricing)
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
            confirmed_tier='exempt',  # Give them exempt tier during reconciliation
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
    def create_billing_snapshot(organization, stripe_subscription=None):
        """Create a billing snapshot for offline resilience"""
        if not organization or not organization.tier:
            return None

        snapshot = BillingSnapshot(
            organization_id=organization.id,
            confirmed_tier=organization.tier.key,
            confirmed_status='active',
            period_start=TimezoneUtils.utc_now(),
            period_end=TimezoneUtils.utc_now() + timedelta(days=30),  # Default 30-day period
            stripe_subscription_id=stripe_subscription.id if stripe_subscription else None,
            stripe_customer_id=stripe_subscription.customer if stripe_subscription else None,
            last_stripe_sync=TimezoneUtils.utc_now(),
            sync_source='manual'
        )

        db.session.add(snapshot)
        db.session.commit()

        logger.info(f"Created billing snapshot for org {organization.id}")
        return snapshot

    @staticmethod
    def get_subscription_status_summary(organization):
        """Get comprehensive subscription status for display"""
        if not organization:
            return {
                'has_subscription': False,
                'tier': 'exempt',
                'status': 'none',
                'is_active': False
            }

        # Get current tier
        current_tier = BillingService.get_effective_tier(organization)

        # Check if subscription is active
        has_access, reason = BillingService.check_organization_access(organization)

        return {
            'has_subscription': bool(organization.tier),
            'tier': current_tier,
            'status': 'active' if has_access else 'inactive',
            'is_active': has_access,
            'reason': reason,
            'max_users': organization.get_max_users(),
            'current_users': organization.active_users_count
        }

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
            # Update existing snapshots or create new ones
            for tier_key, pricing_info in live_pricing_data.items():
                # Find existing snapshot or create new one
                snapshot = PricingSnapshot.query.filter_by(
                    stripe_lookup_key=tier_key
                ).first()

                if not snapshot:
                    snapshot = PricingSnapshot(stripe_lookup_key=tier_key)
                    db.session.add(snapshot)

                # Update snapshot data
                snapshot.product_name = pricing_info.get('name', '')
                snapshot.unit_amount = int(float(pricing_info.get('price', '$0').replace('$', '')) * 100)
                snapshot.currency = 'usd'
                snapshot.features = '\n'.join(pricing_info.get('features', []))
                snapshot.last_stripe_sync = TimezoneUtils.utc_now()
                snapshot.is_active = True

            db.session.commit()
            logger.info("Updated pricing snapshots with live Stripe data")
        except Exception as e:
            logger.error(f"Failed to update pricing snapshots: {str(e)}")
