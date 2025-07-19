
"""
Utility functions for managing exempt (gifted) accounts
"""
import logging
from ..models import db, Organization
from ..services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)

class ExemptAccountManager:
    """Manage exempt (gifted) accounts for special users"""
    
    @staticmethod
    def grant_exempt_access(organization_id, reason="Gifted account"):
        """Grant exempt access to an organization"""
        org = Organization.query.get(organization_id)
        if not org:
            return False, "Organization not found"
        
        if org.id == 1:
            return True, "Organization 1 is already reserved/exempt"
        
        # Check if already has subscription
        if hasattr(org, 'subscription') and org.subscription:
            if org.subscription.tier == 'exempt':
                return True, "Organization already has exempt access"
            else:
                # Update existing subscription to exempt
                org.subscription.tier = 'exempt'
                org.subscription.status = 'active'
                org.subscription.notes = f"{org.subscription.notes or ''}\nUpgraded to exempt: {reason}".strip()
                db.session.commit()
                return True, "Upgraded existing subscription to exempt"
        else:
            # Create new exempt subscription
            subscription = SubscriptionService.create_exempt_subscription(org, reason)
            return True, "Created new exempt subscription"
    
    @staticmethod
    def revoke_exempt_access(organization_id, new_tier='free'):
        """Revoke exempt access and set to specified tier"""
        org = Organization.query.get(organization_id)
        if not org:
            return False, "Organization not found"
        
        if org.id == 1:
            return False, "Cannot revoke exempt access from reserved organization 1"
        
        if hasattr(org, 'subscription') and org.subscription:
            if org.subscription.tier == 'exempt':
                org.subscription.tier = new_tier
                org.subscription.notes = f"{org.subscription.notes or ''}\nExempt access revoked".strip()
                db.session.commit()
                return True, f"Exempt access revoked, set to {new_tier}"
        
        return False, "Organization does not have exempt access"
    
    @staticmethod
    def list_exempt_organizations():
        """List all organizations with exempt access"""
        from ..models.subscription import Subscription
        exempt_subs = Subscription.query.filter_by(tier='exempt').all()
        return [sub.organization for sub in exempt_subs if sub.organization]
