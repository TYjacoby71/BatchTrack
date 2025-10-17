
import logging
from datetime import datetime, timedelta
from ..models.subscription_tier import SubscriptionTier
from ..models.models import Organization
from ..extensions import db

logger = logging.getLogger(__name__)

class OfflineBillingService:
    """Deprecated: offline billing is disabled. Retained for backwards import compatibility."""
    
    @staticmethod
    def sync_tier_permissions(organization):
        """Sync tier permissions for offline organizations"""
        return False
    
    @staticmethod
    def validate_offline_access(organization):
        """Validate offline access without pricing checks"""
        return False, "offline_disabled"
    
    @staticmethod
    def get_offline_tier_info(tier_key):
        """Get tier info for offline mode - structure only, no pricing"""
        return None
    
    @staticmethod
    def cache_tier_structure(organization):
        """Cache tier structure for offline use - NO PRICING"""
        return False
