
import logging
from datetime import datetime, timedelta
from ..models.subscription_tier import SubscriptionTier
from ..models.models import Organization
from ..extensions import db

logger = logging.getLogger(__name__)

class OfflineBillingService:
    """
    Offline billing service - NO pricing information stored
    Works purely with tier assignments and billing provider verification
    """
    
    @staticmethod
    def sync_tier_permissions(organization):
        """Sync tier permissions for offline organizations"""
        try:
            if not organization or not organization.subscription_tier_obj:
                logger.warning(f"No valid tier for organization {organization.id if organization else 'None'}")
                return False
                
            tier = organization.subscription_tier_obj
            
            # For offline mode, we only care about tier structure, not pricing
            logger.info(f"Organization {organization.id} has tier {tier.key} with {len(tier.permissions)} permissions")
            
            # Update last sync time
            organization.last_online_sync = datetime.utcnow()
            db.session.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Error syncing tier permissions for org {organization.id if organization else 'None'}: {e}")
            return False
    
    @staticmethod
    def validate_offline_access(organization):
        """Validate offline access without pricing checks"""
        if not organization:
            return False, "no_organization"
            
        if not organization.subscription_tier_obj:
            return False, "no_tier_assigned"
            
        tier = organization.subscription_tier_obj
        
        # Exempt tiers always work offline
        if tier.is_exempt_from_billing:
            return True, "exempt_tier"
            
        # For paid tiers, we need to check if they have valid billing integration
        # but we don't check pricing - that's handled by the billing provider
        if tier.has_valid_integration:
            return True, "valid_integration"
            
        return False, "invalid_tier_configuration"
    
    @staticmethod
    def get_offline_tier_info(tier_key):
        """Get tier info for offline mode - structure only, no pricing"""
        tier = SubscriptionTier.query.filter_by(key=tier_key).first()
        if not tier:
            return None
            
        return {
            'key': tier.key,
            'name': tier.name,
            'description': tier.description,
            'user_limit': tier.user_limit,
            'permissions': tier.get_permission_names(),
            'billing_provider': tier.billing_provider,
            'is_billing_exempt': tier.is_billing_exempt,
            'requires_online_verification': not tier.is_billing_exempt
        }
    
    @staticmethod
    def cache_tier_structure(organization):
        """Cache tier structure for offline use - NO PRICING"""
        try:
            if not organization.subscription_tier_obj:
                return False
                
            tier_info = OfflineBillingService.get_offline_tier_info(
                organization.subscription_tier_obj.key
            )
            
            if tier_info:
                # Store tier structure cache (no pricing)
                organization.offline_tier_cache = tier_info
                organization.last_online_sync = datetime.utcnow()
                db.session.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error caching tier structure: {e}")
            
        return False
