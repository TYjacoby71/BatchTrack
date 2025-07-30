
from datetime import datetime, timedelta
from flask import current_app
from ..models import db, Organization
from ..utils.timezone_utils import TimezoneUtils
import logging

logger = logging.getLogger(__name__)

class BillingAccessControl:
    """Centralized service for billing-based access control"""

    @staticmethod
    def check_organization_access(organization):
        """
        Check if organization has access to the system based on billing status.
        Returns (has_access: bool, reason: str)
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

        # Use resilient billing service for comprehensive check
        from .resilient_billing_service import ResilientBillingService
        return ResilientBillingService.check_organization_access(organization)

    @staticmethod
    def enforce_billing_access(organization):
        """
        Raise appropriate exceptions if organization doesn't have access.
        This should be called by middleware before permission checks.
        """
        has_access, reason = BillingAccessControl.check_organization_access(organization)
        
        if not has_access:
            from flask import abort, flash, redirect, url_for
            
            if reason == "organization_suspended":
                flash('Your organization has been suspended. Please contact support.', 'error')
                abort(403)
            elif reason in ["past_due", "unpaid", "canceled"]:
                flash('Your subscription needs attention. Please update your billing.', 'warning')
                return redirect(url_for('billing.reconciliation_needed'))
            else:
                flash('Billing verification required to access the system.', 'error')
                return redirect(url_for('billing.upgrade'))

    @staticmethod
    def sync_permissions_from_tier(organization):
        """
        Sync organization permissions based on current subscription tier.
        This should be called when tier changes via Stripe webhooks.
        """
        tier_key = organization.effective_subscription_tier
        
        # Get available permissions for this tier
        from .billing_service import BillingService
        tier_permissions = BillingService.get_tier_permissions(tier_key)
        
        # For org owner, assign all tier permissions
        owner = organization.users.filter_by(user_type='organization_owner').first()
        if owner:
            # Clear existing permissions and assign new ones
            owner.permissions.clear()
            for permission in tier_permissions:
                owner.permissions.append(permission)
        
        # For other users, validate their permissions against tier
        for user in organization.users:
            if user.user_type != 'organization_owner':
                # Remove any permissions not allowed by current tier
                allowed_permission_names = [p.name for p in tier_permissions]
                user.permissions = [p for p in user.permissions if p.name in allowed_permission_names]
        
        db.session.commit()
        logger.info(f"Synced permissions for org {organization.id} with tier {tier_key}")

    @staticmethod
    def validate_tier_permission(organization, permission_name):
        """
        Check if a permission is allowed under the organization's current tier.
        This is used when assigning permissions to users.
        """
        tier_key = organization.effective_subscription_tier
        
        from .billing_service import BillingService
        tier_permissions = BillingService.get_tier_permissions(tier_key)
        allowed_permissions = [p.name for p in tier_permissions]
        
        return permission_name in allowed_permissions
