
import logging
from datetime import datetime, timedelta
from flask import current_app
from ..models import db, Organization
from ..utils.timezone_utils import TimezoneUtils
from .billing_service import BillingService

logger = logging.getLogger(__name__)

class OfflineBillingService:
    """Service for handling offline billing validation and sync"""

    @staticmethod
    def cache_tier_for_offline(organization):
        """Cache current tier permissions for offline use"""
        if not organization or not organization.subscription_tier_obj:
            return False

        tier_cache = {
            'tier_key': organization.subscription_tier_obj.key,
            'tier_name': organization.subscription_tier_obj.name,
            'permissions': organization.subscription_tier_obj.get_permissions(),
            'user_limit': organization.subscription_tier_obj.user_limit,
            'cached_at': TimezoneUtils.utc_now().isoformat(),
            'billing_status': organization.billing_status
        }

        organization.offline_tier_cache = tier_cache
        organization.last_online_sync = TimezoneUtils.utc_now()
        db.session.commit()
        
        logger.info(f"Cached tier data for offline use: {organization.id}")
        return True

    @staticmethod
    def validate_offline_access(organization):
        """Check if organization can access features while offline"""
        if not organization:
            return False, "No organization"

        # If online, always use live billing
        if OfflineBillingService.is_online():
            return BillingService.validate_tier_access(organization)

        # Offline validation
        if not organization.offline_tier_cache:
            return False, "No cached tier data for offline use"

        cache_date = datetime.fromisoformat(organization.offline_tier_cache['cached_at'])
        grace_period = timedelta(days=7)  # Default grace period

        if TimezoneUtils.utc_now() - cache_date > grace_period:
            return False, "Offline grace period expired"

        # Check cached billing status
        cached_status = organization.offline_tier_cache.get('billing_status', 'active')
        if cached_status != 'active':
            return False, "Cached billing status invalid"

        return True, "Offline access valid"

    @staticmethod
    def get_cached_permissions(organization):
        """Get permissions from offline cache"""
        if not organization or not organization.offline_tier_cache:
            return []
        
        return organization.offline_tier_cache.get('permissions', [])

    @staticmethod
    def is_online():
        """Check if application has internet connectivity"""
        # Simple check - in production you might ping a service
        # For now, assume we're always online in development
        return True

    @staticmethod
    def sync_billing_status():
        """Sync all organizations' billing status when coming online"""
        organizations = Organization.query.filter(
            Organization.offline_tier_cache.isnot(None)
        ).all()

        synced_count = 0
        for org in organizations:
            try:
                # Update from live billing system
                if org.stripe_customer_id:
                    # Sync with Stripe
                    pass  # Implement Stripe sync
                elif org.whop_license_key:
                    # Sync with Whop
                    pass  # Implement Whop sync
                
                # Update cache
                OfflineBillingService.cache_tier_for_offline(org)
                synced_count += 1
                
            except Exception as e:
                logger.error(f"Failed to sync billing for org {org.id}: {e}")

        logger.info(f"Synced billing for {synced_count} organizations")
        return synced_count
