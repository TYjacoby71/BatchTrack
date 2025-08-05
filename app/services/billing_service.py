
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

        # Get organization's effective tier using standardized method
        current_tier = BillingService.get_effective_tier(user.organization)

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
            return False, "no_organization"

        # Get normalized tier key
        tier_key = BillingService._get_tier_key(organization)

        # Exempt organizations always have access
        if tier_key == 'exempt':
            return True, "exempt"

        # Developer accounts bypass billing checks
        if organization.id == 1:  # Reserved dev org
            return True, "developer"

        # Check if organization is active
        if not organization.is_active:
            return False, "organization_suspended"

        # If no tier at all, deny access
        if not tier_key or tier_key == 'none':
            return False, "no_subscription"

        # Try current tier first (normal case)
        if BillingService._is_stripe_healthy() and organization.tier:
            return True, "active_subscription"

        # If Stripe is down, check snapshots
        latest_snapshot = BillingSnapshot.get_latest_valid_snapshot(organization.id)

        if latest_snapshot and latest_snapshot.is_valid_for_access:
            days_left = latest_snapshot.days_until_grace_expires
            return True, f"snapshot_grace_{days_left}_days"

        # No valid confirmation found
        return False, "billing_unconfirmed"

    

    @staticmethod
    def _get_tier_key(organization):
        """Internal helper to get consistent tier key from organization"""
        if not organization:
            return 'exempt'
        
        if hasattr(organization, 'tier') and organization.tier:
            return organization.tier.key
        
        return 'exempt'

    @staticmethod
    def get_effective_tier(organization):
        """Get effective tier, falling back to snapshots during outages"""
        if not organization:
            return 'exempt'

        tier_key = BillingService._get_tier_key(organization)

        if tier_key == 'exempt':
            return 'exempt'

        # Try current tier data first
        if BillingService._is_stripe_healthy() and organization.tier:
            return tier_key

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

    # Reconciliation methods removed - no more fallback logic

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
                'status': 'inactive',
                'is_active': False,
                'reason': 'no_organization'
            }

        # Get current tier and access status
        current_tier = BillingService.get_effective_tier(organization)
        has_access, reason = BillingService.check_organization_access(organization)

        return {
            'has_subscription': bool(organization.tier),
            'tier': current_tier,
            'status': 'active' if has_access else 'inactive',
            'is_active': has_access,
            'reason': reason,
            'max_users': organization.get_max_users() if hasattr(organization, 'get_max_users') else 0,
            'current_users': organization.active_users_count if hasattr(organization, 'active_users_count') else 0
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
