
import logging
import stripe
import os
import json
from datetime import datetime, timedelta
from flask import current_app
from ..models import db, Organization, Permission, SubscriptionTier
from ..blueprints.developer.subscription_tiers import load_tiers_config
from ..utils.timezone_utils import TimezoneUtils
from ..models.billing_snapshot import BillingSnapshot
from ..models.pricing_snapshot import PricingSnapshot

logger = logging.getLogger(__name__)

class BillingService:
    """Consolidated service for all billing, subscription, and pricing logic"""

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
        Check if organization should have access, supporting both Stripe and Whop.
        """
        if not organization:
            return False, "no_organization"

        # Get normalized tier key
        tier_key = BillingService._get_tier_key(organization)

        # Exempt organizations always have access
        if tier_key == 'exempt':
            return True, "exempt"

        # Developer accounts bypass billing checks
        if BillingService.is_reserved_organization(organization.id):
            return True, "developer"

        # Check if organization is active
        if not organization.is_active:
            return False, "organization_suspended"

        # If no tier at all, deny access
        if not tier_key or tier_key == 'none':
            return False, "no_subscription"

        # Check Whop access first (preferred)
        if hasattr(organization, 'whop_license_key') and organization.whop_license_key:
            from ..services.whop_service import WhopService
            has_whop_access, whop_reason = WhopService.check_whop_access(organization)
            if has_whop_access:
                return True, "whop_verified"
            else:
                return False, whop_reason

        # Fall back to Stripe logic for legacy users
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

    # ============================================================================
    # SUBSCRIPTION MANAGEMENT (consolidated from SubscriptionService)
    # ============================================================================

    @staticmethod
    def create_subscription_for_organization(organization, tier_key='exempt'):
        """Assign a subscription tier to an organization"""
        # Find the tier by key
        tier = SubscriptionTier.query.filter_by(key=tier_key).first()
        if not tier:
            # If tier doesn't exist, assign exempt as fallback
            tier = SubscriptionTier.query.filter_by(key='exempt').first()

        if tier:
            organization.subscription_tier_id = tier.id
            db.session.commit()

        return tier

    @staticmethod
    def can_add_users(organization, count=1):
        """Check if organization can add more users based on subscription tier"""
        current_user_count = organization.users.count()

        tier_obj = organization.subscription_tier_obj
        if not tier_obj:
            return False  # No tier = no access

        limit = tier_obj.user_limit

        if limit == -1:  # Unlimited
            return True

        return (current_user_count + count) <= limit

    @staticmethod
    def create_pending_subscription(organization, selected_tier):
        """Create a pending subscription that will be activated by Stripe"""
        # Find the SubscriptionTier by key
        tier = SubscriptionTier.query.filter_by(key=selected_tier).first()
        if not tier:
            logger.warning(f"Tier '{selected_tier}' not found")
            return None

        organization.subscription_tier_id = tier.id
        db.session.commit()

        return tier

    @staticmethod
    def create_exempt_subscription(organization, reason="Exempt account"):
        """Create an exempt subscription - only hardcoded tier allowed"""
        # Find the "exempt" tier (should be seeded)
        exempt_tier = SubscriptionTier.query.filter_by(key='exempt').first()
        if not exempt_tier:
            logger.error("Exempt tier not found - ensure seeding is complete")
            return None

        organization.subscription_tier_id = exempt_tier.id
        db.session.commit()
        return exempt_tier

    @staticmethod
    def is_reserved_organization(org_id):
        """Check if organization is reserved for owner/testing"""
        return org_id == 1  # Organization 1 is reserved

    @staticmethod
    def setup_reserved_organization():
        """Set up organization 1 as reserved for owner"""
        from ..models import Organization

        org = Organization.query.get(1)
        if org and org.subscription_tier_id is None:
            # Create exempt subscription for org 1
            subscription = BillingService.create_exempt_subscription(
                org,
                "Reserved organization for owner/testing"
            )
            logger.info(f"Created exempt subscription for reserved organization {org.id}")
            return subscription
        return None

    @staticmethod
    def validate_permission_for_tier(organization, permission_name):
        """Validate if permission is allowed for organization's subscription tier"""
        tier = organization.subscription_tier_obj
        if not tier:
            logger.warning(f"No tier found for organization {organization.id}")
            return False

        # Check if tier has the permission
        has_permission = tier.has_permission(permission_name)
        
        if not has_permission:
            logger.info(f"Permission '{permission_name}' denied for tier '{tier.key}'")

        return has_permission

    # Trial Management Methods
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
                    BillingService._convert_to_paid(org)
                else:
                    # Suspend organization for missing billing
                    BillingService._suspend_for_billing(org)
                    
            except Exception as e:
                logger.error(f"Error processing expired trial for org {org.id}: {str(e)}")
                continue
                
        db.session.commit()
        return len(expired_orgs)

    @staticmethod
    def _convert_to_paid(organization):
        """Convert trial organization to paid subscription"""
        organization.subscription_tier = 'solo'  # Default tier
        organization.subscription_status = 'active'
        organization.next_billing_date = TimezoneUtils.utc_now() + timedelta(days=30)
        
        # Send welcome email to paid subscriber
        BillingService._send_conversion_email(organization, success=True)
        
        logger.info(f"Converted organization {organization.id} to paid subscription")
    
    @staticmethod
    def _suspend_for_billing(organization):
        """Suspend organization for missing billing information"""
        organization.subscription_status = 'past_due'
        organization.is_active = False  # Suspend access
        
        # Send billing reminder email
        BillingService._send_conversion_email(organization, success=False)
        
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

    # ============================================================================
    # PRICING MANAGEMENT (consolidated from PricingService)
    # ============================================================================

    @staticmethod
    def get_comprehensive_pricing_data():
        """Get comprehensive pricing data from Stripe with graceful fallbacks"""
        final_pricing_data = {}

        # Always try to get live Stripe data first
        try:
            pricing_data = BillingService._get_stripe_pricing()
            if pricing_data:
                final_pricing_data.update(pricing_data)
                logger.info(f"Successfully retrieved pricing for {len(pricing_data)} tiers from Stripe")
        except Exception as e:
            logger.error(f"Failed to get Stripe pricing data: {str(e)}")

        # If we don't have complete data, try cached snapshots for missing tiers
        all_tiers = BillingService._load_tiers_config()
        missing_tiers = []

        for tier_key, tier_data in all_tiers.items():
            if not isinstance(tier_data, dict):
                continue
            if not (tier_data.get('is_customer_facing', True) and tier_data.get('is_available', True)):
                continue
            if tier_key not in final_pricing_data:
                missing_tiers.append(tier_key)

        if missing_tiers:
            logger.info(f"Trying cached snapshots for missing tiers: {missing_tiers}")
            try:
                snapshot_data = BillingService._get_snapshot_pricing_data()
                for tier_key in missing_tiers:
                    if tier_key in snapshot_data:
                        final_pricing_data[tier_key] = snapshot_data[tier_key]
                        logger.info(f"Retrieved tier {tier_key} from cached snapshots")
            except Exception as e:
                logger.error(f"Failed to get cached pricing data: {str(e)}")

        # For any remaining missing tiers, use configuration fallback
        still_missing = [tier for tier in missing_tiers if tier not in final_pricing_data]
        if still_missing:
            logger.info(f"Using configuration fallback for remaining tiers: {still_missing}")
            fallback_data = BillingService._get_fallback_pricing()
            for tier_key in still_missing:
                if tier_key in fallback_data:
                    final_pricing_data[tier_key] = fallback_data[tier_key]
                    logger.info(f"Using fallback data for tier {tier_key}")

        logger.info(f"Final pricing data assembled for {len(final_pricing_data)} tiers")
        return final_pricing_data

    @staticmethod
    def _load_tiers_config():
        """Load subscription tiers configuration from JSON file"""
        config_file = 'subscription_tiers.json'
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return json.load(f)

        # Return empty dict if no config exists - should be created via admin interface
        logger.warning("No subscription_tiers.json found - tiers should be configured via developer interface")
        return {}

    @staticmethod
    def _get_fallback_pricing():
        """Get fallback pricing from local configuration for customer-facing and available tiers only"""
        # Load dynamic tiers configuration
        all_tiers = BillingService._load_tiers_config()

        # Filter to only customer-facing and available tiers
        pricing_data = {}
        for tier_key, tier_data in all_tiers.items():
            # Skip if tier_data is not a dictionary
            if not isinstance(tier_data, dict):
                continue
            if tier_data.get('is_customer_facing', True) and tier_data.get('is_available', True):
                # Use stripe pricing if available, otherwise fallback to configured pricing
                monthly_price = (tier_data.get('stripe_price_monthly') or 
                               tier_data.get('price_display') or 
                               tier_data.get('fallback_price_monthly', '$0'))
                yearly_price = (tier_data.get('stripe_price_yearly') or 
                              tier_data.get('price_yearly_display') or 
                              tier_data.get('fallback_price_yearly', '$0'))

                pricing_data[tier_key] = {
                    'price': monthly_price,
                    'price_yearly': yearly_price,
                    'features': tier_data.get('fallback_features', tier_data.get('stripe_features', [])),
                    'name': tier_data.get('name', tier_key.title()),
                    'description': tier_data.get('description', f"Perfect for {tier_key} operations"),
                    'user_limit': tier_data.get('user_limit', 1),
                    'stripe_lookup_key': tier_data.get('stripe_lookup_key', ''),
                    'is_stripe_ready': tier_data.get('is_stripe_ready', False),
                    'is_fallback': True
                }

        return pricing_data

    @staticmethod
    def _get_stripe_pricing():
        """Get comprehensive pricing data from Stripe for customer-facing and available tiers only"""
        # Check if Stripe is configured
        stripe_secret = os.environ.get('STRIPE_SECRET_KEY') or current_app.config.get('STRIPE_SECRET_KEY')
        if not stripe_secret:
            logger.warning("Stripe API key not configured")
            return {}

        # Set the API key
        stripe.api_key = stripe_secret

        # Load dynamic tiers configuration
        all_tiers = BillingService._load_tiers_config()

        # Start with fallback data structure - ensure we always have something for each tier
        pricing_data = {}
        successful_tiers = 0

        for tier_key, tier_data in all_tiers.items():
            # Skip if tier_data is not a dictionary
            if not isinstance(tier_data, dict):
                continue
            if not (tier_data.get('is_customer_facing', True) and tier_data.get('is_available', True)):
                continue

            lookup_key = tier_data.get('stripe_lookup_key')
            if not lookup_key:
                logger.info(f"Tier {tier_key} has no Stripe lookup key - using fallback only")
                continue

            logger.info(f"Looking up Stripe product for tier {tier_key} with lookup_key: {lookup_key}")

            try:
                # Search for prices using lookup key, then get the product
                prices = stripe.Price.list(lookup_keys=[lookup_key], limit=1, active=True)

                logger.info(f"Found {len(prices.data)} prices for lookup_key: {lookup_key}")

                if prices.data:
                    price = prices.data[0]
                    product = stripe.Product.retrieve(price.product)

                    pricing_data[tier_key] = {
                        'name': product.name or tier_data.get('name', tier_key.title()),
                        'price': f"${price.unit_amount / 100:.0f}",
                        'features': tier_data.get('fallback_features', []),
                        'description': product.description or tier_data.get('description', f"Perfect for {tier_key} operations"),
                        'user_limit': tier_data.get('user_limit', 1),
                        'stripe_lookup_key': lookup_key,
                        'stripe_price_id_monthly': price.id if price.recurring and price.recurring.interval == 'month' else None,
                        'stripe_product_id': product.id,
                        'requires_stripe_billing': tier_data.get('requires_stripe_billing', True)
                    }

                    logger.info(f"Successfully loaded pricing for {tier_key}: ${price.unit_amount / 100:.0f}")
                    successful_tiers += 1
                else:
                    logger.warning(f"No Stripe price found for lookup_key: {lookup_key}")

            except Exception as e:
                logger.error(f"Error loading pricing for tier {tier_key}: {str(e)}")

        logger.info(f"Pricing retrieval complete: {successful_tiers} tiers from Stripe, {len(pricing_data)} total available")
        return pricing_data

    @staticmethod
    def get_all_tiers_data():
        """Get all tiers data including internal/unavailable ones (for admin use)"""
        all_tiers = BillingService._load_tiers_config()

        # Convert to expected format but include all tiers
        pricing_data = {}
        for tier_key, tier_data in all_tiers.items():
            if not isinstance(tier_data, dict):
                continue

            pricing_data[tier_key] = BillingService._get_tier_fallback_data(tier_key, tier_data)
            # Add admin-specific fields
            pricing_data[tier_key].update({
                'is_customer_facing': tier_data.get('is_customer_facing', True),
                'is_available': tier_data.get('is_available', True)
            })

        return pricing_data

    @staticmethod
    def _get_tier_fallback_data(tier_key, tier_data):
        """Get fallback data for a single tier"""
        price_monthly = tier_data.get('stripe_price_monthly', 0)
        price_yearly = tier_data.get('stripe_price_yearly', 0)

        return {
            'name': tier_data.get('name', tier_key.title()),
            'price': f"${price_monthly:.0f}" if price_monthly > 0 else '$0',
            'price_display': f"${price_monthly:.0f}" if price_monthly > 0 else 'Free',
            'price_monthly': price_monthly,
            'price_yearly': price_yearly,
            'features': tier_data.get('fallback_features', []),
            'description': tier_data.get('description', f"Perfect for {tier_key} operations"),
            'user_limit': tier_data.get('user_limit', 1),
            'stripe_lookup_key': tier_data.get('stripe_lookup_key', ''),
            'is_stripe_ready': tier_data.get('is_stripe_ready', False),
            'is_fallback': True
        }

    @staticmethod
    def get_subscription_details(organization):
        """Get detailed subscription information from Stripe"""
        subscription_details = {
            'tier': organization.effective_subscription_tier,
            'status': 'inactive',
            'next_billing_date': None,
            'amount': None,
            'interval': None,
            'trial_end': None,
            'cancel_at_period_end': False
        }

        # For now, we don't have a separate Subscription model with stripe_subscription_id
        # This would need to be implemented when you add the Subscription model
        return subscription_details

    @staticmethod
    def get_tier_features(tier):
        """Get features for a specific tier from config"""
        tiers_config = BillingService._load_tiers_config()
        tier_data = tiers_config.get(tier, {})
        return tier_data.get('fallback_features', [])

    @staticmethod
    def get_user_limits(tier):
        """Get user limits for each tier from config"""
        tiers_config = BillingService._load_tiers_config()
        tier_data = tiers_config.get(tier, {})
        return tier_data.get('user_limit', 1)

    @staticmethod
    def _get_snapshot_pricing_data():
        """Get pricing data from cached PricingSnapshot records when Stripe is unavailable"""
        try:
            tiers_config = BillingService._load_tiers_config()
            pricing_data = {}

            for tier_key, tier_data in tiers_config.items():
                # Only include customer-facing and available tiers
                if not (tier_data.get('is_customer_facing', True) and tier_data.get('is_available', True)):
                    continue

                # Try to get cached pricing from snapshots
                snapshot = PricingSnapshot.get_latest_for_tier(tier_key)

                if snapshot:
                    pricing_data[tier_key] = {
                        'name': tier_data.get('name', tier_key.title()),
                        'price': f"${snapshot.monthly_price:.0f}" if snapshot.monthly_price else '$0',
                        'price_yearly': f"${snapshot.yearly_price:.0f}" if snapshot.yearly_price else '$0',
                        'features': tier_data.get('fallback_features', []),
                        'description': tier_data.get('description', f"Perfect for {tier_key} operations"),
                        'user_limit': tier_data.get('user_limit', 1),
                        'stripe_lookup_key': tier_data.get('stripe_lookup_key', ''),
                        'is_stripe_ready': True,  # Snapshots are from Stripe data
                        'is_cached': True
                    }
                else:
                    # No snapshot available - tier unavailable for purchase
                    logger.warning(f"No pricing snapshot available for tier {tier_key}")

            logger.info(f"Retrieved cached pricing for {len(pricing_data)} tiers from snapshots")
            return pricing_data

        except Exception as e:
            logger.error(f"Failed to get cached pricing data: {str(e)}")
            return {}
