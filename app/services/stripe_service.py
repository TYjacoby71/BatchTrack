import stripe
import logging
from flask import current_app, url_for
from ..models import db, SubscriptionTier, Organization
from ..utils.timezone_utils import TimezoneUtils
from datetime import datetime

logger = logging.getLogger(__name__)

class StripeService:
    """Service for handling Stripe payment operations"""

    @staticmethod
    def initialize_stripe():
        """Initialize Stripe with API key"""
        logger.info("=== STRIPE INITIALIZATION ===")
        import os
        stripe_secret = os.environ.get('STRIPE_SECRET_KEY') or current_app.config.get('STRIPE_SECRET_KEY')
        logger.info(f"Stripe secret key configured: {bool(stripe_secret)}")
        if stripe_secret:
            logger.info(f"Stripe key prefix: {stripe_secret[:7]}...")

        if not stripe_secret:
            logger.warning("Stripe secret key not configured")
            return False
        stripe.api_key = stripe_secret
        logger.info("Stripe API key set successfully")
        return True

    @staticmethod
    def create_customer(organization):
        """Create a Stripe customer for an organization"""
        StripeService.initialize_stripe()

        try:
            customer = stripe.Customer.create(
                email=organization.contact_email,
                name=organization.name,
                metadata={
                    'organization_id': organization.id
                }
            )

            # For now, we don't have a separate Subscription model
            # This would need to be implemented when you add the Subscription model
            logger.info(f"Created Stripe customer {customer.id} for org {organization.id} (no subscription model to update)")

            logger.info(f"Created Stripe customer {customer.id} for org {organization.id}")
            return customer

        except stripe.error.StripeError as e:
            logger.error(f"Failed to create Stripe customer for org {organization.id}: {str(e)}")
            return None

    @staticmethod
    def create_checkout_session(organization, tier):
        """Create a Stripe checkout session for subscription"""
        # This method should only be called for stripe-ready tiers
        from ..blueprints.developer.subscription_tiers import load_tiers_config
        tiers_config = load_tiers_config()
        tier_data = tiers_config.get(tier, {})

        StripeService.initialize_stripe()

        # Try to get price ID from tier config first
        price_id = tier_data.get('stripe_price_id_monthly')

        # Fallback to hardcoded config if not found in tier
        if not price_id:
            price_id = current_app.config.get('STRIPE_PRICE_IDS', {}).get(tier)

        if not price_id:
            logger.error(f"No Stripe price ID configured for tier: {tier}")
            return None

        # For now, create a new customer for each checkout
        customer = StripeService.create_customer(organization)
        if not customer:
            return None

        try:
            session = stripe.checkout.Session.create(
                customer=customer.id,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=url_for('billing.complete_signup_from_stripe', _external=True),
                cancel_url=url_for('auth.signup', _external=True) + '?payment=cancelled',
                metadata={
                    'organization_id': organization.id,
                    'tier': tier
                }
            )

            logger.info(f"Created checkout session {session.id} for org {organization.id}")
            return session

        except stripe.error.StripeError as e:
            logger.error(f"Failed to create checkout session for org {organization.id}: {str(e)}")
            return None

    @staticmethod
    def handle_subscription_created(stripe_subscription):
        """Handle successful subscription creation from webhook"""
        try:
            customer_id = stripe_subscription['customer']
            subscription_id = stripe_subscription['id']

            # Find organization by customer metadata or signup metadata
            organization = None
            metadata = stripe_subscription.get('metadata', {})

            # Try to find organization from subscription metadata first
            if 'organization_id' in metadata:
                organization = Organization.query.get(metadata['organization_id'])

            # If not found, try to find by customer
            if not organization:
                # Get customer to check for organization_id in metadata
                customer = stripe.Customer.retrieve(customer_id)
                if customer.metadata.get('organization_id'):
                    organization = Organization.query.get(customer.metadata['organization_id'])

            if not organization:
                logger.error(f"No organization found for subscription {subscription_id}")
                return False

            # Set subscription tier based on metadata
            tier_key = metadata.get('tier')
            if tier_key:
                tier = SubscriptionTier.query.filter_by(key=tier_key).first()
                if tier:
                    organization.subscription_tier_id = tier.id
                    logger.info(f"Set organization {organization.id} to tier {tier_key}")

                    # Sync permissions based on new tier
                    from .billing_access_control import BillingAccessControl
                    BillingAccessControl.sync_permissions_from_tier(organization)
                else:
                    logger.error(f"Tier '{tier_key}' not found for organization {organization.id}")
                    return False

            # Create billing snapshot for resilience
            try:
                from ..models.billing_snapshot import BillingSnapshot
                snapshot = BillingSnapshot.create_from_stripe_subscription(
                    organization, stripe_subscription
                )
                if snapshot:
                    logger.info(f"Created billing snapshot for org {organization.id}")
            except Exception as e:
                logger.warning(f"Failed to create billing snapshot: {str(e)}")

            db.session.commit()
            logger.info(f"Activated subscription for org {organization.id} (tier: {tier_key})")
            return True

        except Exception as e:
            logger.error(f"Failed to handle subscription creation: {str(e)}")
            db.session.rollback()
            return False

    @staticmethod
    def handle_subscription_updated(stripe_subscription):
        """Handle subscription updates from webhook"""
        try:
            subscription_id = stripe_subscription['id']
            customer_id = stripe_subscription['customer']

            # Find organization by customer metadata
            organization = None
            customer = stripe.Customer.retrieve(customer_id)
            if customer.metadata.get('organization_id'):
                organization = Organization.query.get(customer.metadata['organization_id'])

            if not organization:
                logger.error(f"No organization found for subscription update {subscription_id}")
                return False

            # Handle subscription status changes
            status = stripe_subscription['status']
            logger.info(f"Subscription {subscription_id} status: {status} for org {organization.id}")

            # If subscription is canceled, deactivate the organization entirely
            if status == 'canceled':
                organization.is_active = False
                logger.info(f"Deactivated org {organization.id} due to subscription cancellation")
            elif status in ['unpaid', 'past_due']:
                # For unpaid/past_due, also deactivate to prevent access
                organization.is_active = False
                logger.info(f"Deactivated org {organization.id} due to payment issues: {status}")
            elif status == 'active':
                # Reactivate if subscription becomes active again
                organization.is_active = True
                logger.info(f"Reactivated org {organization.id} due to active subscription")

                # Sync permissions when reactivated
                from .billing_access_control import BillingAccessControl
                BillingAccessControl.sync_permissions_from_tier(organization)

            # Create/update billing snapshot for resilience
            try:
                from ..models.billing_snapshot import BillingSnapshot
                snapshot = BillingSnapshot.create_from_stripe_subscription(
                    organization, stripe_subscription
                )
                if snapshot:
                    logger.info(f"Updated billing snapshot for org {organization.id}")
            except Exception as e:
                logger.warning(f"Failed to update billing snapshot: {str(e)}")

            db.session.commit()
            logger.info(f"Updated subscription for org {organization.id} from webhook")
            return True

        except Exception as e:
            logger.error(f"Failed to handle subscription update: {str(e)}")
            db.session.rollback()
            return False

    @staticmethod
    def cancel_subscription(organization):
        """Cancel a Stripe subscription and deactivate organization"""
        if not StripeService.initialize_stripe():
            logger.error("Stripe not configured")
            return False

        # Find customer by organization
        try:
            customers = stripe.Customer.list(
                metadata={'organization_id': str(organization.id)},
                limit=1
            )

            if not customers.data:
                logger.error(f"No Stripe customer found for org {organization.id}")
                return False

            customer = customers.data[0]

            # Get active subscriptions for this customer
            subscriptions = stripe.Subscription.list(
                customer=customer.id,
                status='active',
                limit=1
            )

            if not subscriptions.data:
                logger.error(f"No active subscription found for org {organization.id}")
                return False

            subscription = subscriptions.data[0]

            # Cancel the subscription
            stripe.Subscription.delete(subscription.id)

            # Deactivate the organization - no access at all
            organization.is_active = False

            db.session.commit()

            logger.info(f"Canceled subscription and deactivated org {organization.id}")
            return True

        except stripe.error.StripeError as e:
            logger.error(f"Failed to cancel subscription for org {organization.id}: {str(e)}")
            return False

    @staticmethod
    def handle_subscription_deleted(stripe_subscription):
        """Handle subscription deletion from webhook - deactivate organization"""
        try:
            subscription_id = stripe_subscription['id']
            customer_id = stripe_subscription['customer']

            # Find organization by customer metadata
            organization = None
            customer = stripe.Customer.retrieve(customer_id)
            if customer.metadata.get('organization_id'):
                organization = Organization.query.get(customer.metadata['organization_id'])

            if not organization:
                logger.error(f"No organization found for subscription deletion {subscription_id}")
                return False

            # Deactivate the organization entirely - no access
            organization.is_active = False

            # Create billing snapshot for record keeping
            try:
                from ..models.billing_snapshot import BillingSnapshot
                snapshot = BillingSnapshot.create_from_stripe_subscription(
                    organization, stripe_subscription
                )
                if snapshot:
                    logger.info(f"Created final billing snapshot for org {organization.id}")
            except Exception as e:
                logger.warning(f"Failed to create final billing snapshot: {str(e)}")

            db.session.commit()
            logger.info(f"Deactivated org {organization.id} due to subscription deletion")
            return True

        except Exception as e:
            logger.error(f"Failed to handle subscription deletion: {str(e)}")
            db.session.rollback()
            return False

    @staticmethod
    def create_customer_portal_session(organization, return_url):
        """Create a Stripe Customer Portal session for self-service billing management"""
        if not StripeService.initialize_stripe():
            logger.error("Stripe not configured")
            return None

        try:
            # Find customer by organization metadata
            customers = stripe.Customer.list(
                metadata={'organization_id': str(organization.id)},
                limit=1
            )

            if not customers.data:
                logger.error(f"No Stripe customer found for org {organization.id}")
                return None

            customer = customers.data[0]

            session = stripe.billing_portal.Session.create(
                customer=customer.id,
                return_url=return_url,
            )

            logger.info(f"Created customer portal session for org {organization.id}")
            return session

        except stripe.error.StripeError as e:
            logger.error(f"Failed to create customer portal session for org {organization.id}: {str(e)}")
            return None


    @staticmethod
    def handle_webhook(event):
        """Centralized webhook event handling"""
        event_type = event['type']
        logger.info(f"Processing webhook event: {event_type}")

        try:
            if event_type == 'customer.subscription.created':
                success = StripeService.handle_subscription_created(event['data']['object'])
                logger.info(f"Subscription created event handled: {success}")
                return success
            elif event_type == 'customer.subscription.updated':
                success = StripeService.handle_subscription_updated(event['data']['object'])
                logger.info(f"Subscription updated event handled: {success}")
                return success
            elif event_type == 'customer.subscription.deleted':
                # Handle subscription cancellation - deactivate organization
                success = StripeService.handle_subscription_deleted(event['data']['object'])
                logger.info(f"Subscription deleted event handled: {success}")
                return success
            else:
                logger.info(f"Unhandled Stripe webhook event: {event_type}")
                return True
        except Exception as e:
            logger.error(f"Error handling webhook event {event_type}: {str(e)}")
            return False

    @staticmethod
    def create_checkout_session_for_signup(signup_data, price_key):
        """Create Stripe checkout session for new customer signup"""
        if not StripeService.initialize_stripe():
            logger.error("Stripe not configured for signup checkout")
            return None

        # Get tier from price key
        tier = price_key.replace('_yearly', '').replace('_monthly', '')

        # Validate tier configuration
        from ..blueprints.developer.subscription_tiers import load_tiers_config
        tiers_config = load_tiers_config()
        tier_data = tiers_config.get(tier, {})

        # Get Stripe price ID
        if 'yearly' in price_key:
            price_id = tier_data.get('stripe_price_id_yearly')
        else:
            price_id = tier_data.get('stripe_price_id_monthly')

        # Fallback to config
        if not price_id:
            price_id = current_app.config.get('STRIPE_PRICE_IDS', {}).get(price_key)

        if not price_id:
            logger.error(f"No Stripe price ID configured for: {price_key}")
            return None

        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=url_for('billing.complete_signup_from_stripe', _external=True),
                cancel_url=url_for('auth.signup', _external=True) + '?payment=cancelled',
                metadata={
                    'signup_data': str(signup_data),
                    'tier': tier,
                    'price_key': price_key
                }
            )

            logger.info(f"Created signup checkout session {session.id} for tier {tier}")
            return session

        except stripe.error.StripeError as e:
            logger.error(f"Failed to create signup checkout session: {str(e)}")
            return None

    @staticmethod
    def get_stripe_pricing_for_lookup_key(lookup_key):
        """Get pricing information from Stripe for a given lookup key"""
        if not stripe:
            return None

        try:
            # Search for price using lookup key
            prices = stripe.Price.list(lookup_keys=[lookup_key], limit=1)

            if not prices.data:
                return None

            price = prices.data[0]

            # Format the price
            amount = price.unit_amount / 100  # Convert from cents
            currency = price.currency.upper()

            # Determine billing cycle
            if price.recurring:
                interval = price.recurring.interval
                billing_cycle = 'yearly' if interval == 'year' else 'monthly'
            else:
                billing_cycle = 'one-time'

            return {
                'price_id': price.id,
                'formatted_price': f'${amount:.0f}',
                'amount': amount,
                'currency': currency,
                'billing_cycle': billing_cycle,
                'last_synced': datetime.utcnow().isoformat()
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error fetching pricing for {lookup_key}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching pricing for {lookup_key}: {str(e)}")
            return None