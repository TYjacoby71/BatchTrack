
import stripe
import logging
from flask import current_app, url_for
from ..models import db, SubscriptionTier, Organization
from ..utils.timezone_utils import TimezoneUtils

logger = logging.getLogger(__name__)

class StripeService:
    """Service for handling Stripe payment operations"""
    
    @staticmethod
    def initialize_stripe():
        """Initialize Stripe with API key"""
        logger.info("=== STRIPE INITIALIZATION ===")
        stripe_key = current_app.config.get('STRIPE_SECRET_KEY')
        logger.info(f"Stripe secret key configured: {bool(stripe_key)}")
        if stripe_key:
            logger.info(f"Stripe key prefix: {stripe_key[:7]}...")
        
        if not stripe_key:
            logger.warning("Stripe secret key not configured")
            return False
        stripe.api_key = stripe_key
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
            
            # Update subscription with Stripe customer ID
            if organization.subscription:
                organization.subscription.stripe_customer_id = customer.id
                db.session.commit()
            
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
        
        # Ensure customer exists
        if not organization.subscription.stripe_customer_id:
            customer = StripeService.create_customer(organization)
            if not customer:
                return None
        
        try:
            session = stripe.checkout.Session.create(
                customer=organization.subscription.stripe_customer_id,
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
            
            # Find organization by customer ID
            subscription = Subscription.query.filter_by(
                stripe_customer_id=customer_id
            ).first()
            
            if not subscription:
                logger.error(f"No subscription found for customer {customer_id}")
                return False
            
            # Update subscription with Stripe data
            subscription.stripe_subscription_id = subscription_id
            subscription.status = stripe_subscription['status']  # 'trialing' or 'active'
            subscription.current_period_start = TimezoneUtils.from_timestamp(
                stripe_subscription['current_period_start']
            )
            subscription.current_period_end = TimezoneUtils.from_timestamp(
                stripe_subscription['current_period_end']
            )
            subscription.next_billing_date = subscription.current_period_end
            
            # Handle trial information from Stripe
            if stripe_subscription.get('trial_end'):
                subscription.trial_start = TimezoneUtils.from_timestamp(
                    stripe_subscription.get('trial_start', stripe_subscription['current_period_start'])
                )
                subscription.trial_end = TimezoneUtils.from_timestamp(
                    stripe_subscription['trial_end']
                )
            
            # Set tier based on metadata
            metadata = stripe_subscription.get('metadata', {})
            if 'tier' in metadata:
                subscription.tier = metadata['tier']
            
            # Create billing snapshot for resilience
            from ..models.billing_snapshot import BillingSnapshot
            snapshot = BillingSnapshot.create_from_subscription(subscription)
            if snapshot:
                logger.info(f"Created billing snapshot for org {subscription.organization_id}")
            
            db.session.commit()
            logger.info(f"Updated subscription {subscription.id} with Stripe data (status: {subscription.status})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to handle subscription creation: {str(e)}")
            return False
    
    @staticmethod
    def handle_subscription_updated(stripe_subscription):
        """Handle subscription updates from webhook"""
        try:
            subscription_id = stripe_subscription['id']
            
            subscription = Subscription.query.filter_by(
                stripe_subscription_id=subscription_id
            ).first()
            
            if not subscription:
                logger.error(f"No subscription found for Stripe ID {subscription_id}")
                return False
            
            # Update status and periods
            subscription.status = stripe_subscription['status']
            subscription.current_period_start = TimezoneUtils.from_timestamp(
                stripe_subscription['current_period_start']
            )
            subscription.current_period_end = TimezoneUtils.from_timestamp(
                stripe_subscription['current_period_end']
            )
            subscription.next_billing_date = subscription.current_period_end
            
            # Create/update billing snapshot for resilience
            from ..models.billing_snapshot import BillingSnapshot
            snapshot = BillingSnapshot.create_from_subscription(subscription)
            if snapshot:
                logger.info(f"Updated billing snapshot for org {subscription.organization_id}")
            
            db.session.commit()
            logger.info(f"Updated subscription {subscription.id} from Stripe webhook")
            return True
            
        except Exception as e:
            logger.error(f"Failed to handle subscription update: {str(e)}")
            return False
    
    @staticmethod
    def cancel_subscription(organization):
        """Cancel a Stripe subscription"""
        StripeService.initialize_stripe()
        
        if not organization.subscription.stripe_subscription_id:
            logger.error(f"No Stripe subscription ID for org {organization.id}")
            return False
        
        try:
            stripe.Subscription.delete(
                organization.subscription.stripe_subscription_id
            )
            
            organization.subscription.status = 'canceled'
            db.session.commit()
            
            logger.info(f"Canceled subscription for org {organization.id}")
            return True
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to cancel subscription for org {organization.id}: {str(e)}")
            return False

    @staticmethod
    def create_customer_portal_session(organization, return_url):
        """Create a Stripe Customer Portal session for self-service billing management"""
        if not StripeService.initialize_stripe():
            logger.error("Stripe not configured")
            return None
            
        if not organization.subscription or not organization.subscription.stripe_customer_id:
            logger.error(f"No Stripe customer ID for org {organization.id}")
            return None
            
        try:
            session = stripe.billing_portal.Session.create(
                customer=organization.subscription.stripe_customer_id,
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
                # Handle subscription cancellation
                logger.info("Subscription deleted event received")
                # TODO: Implement subscription deletion handler
                return True
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
    def simulate_subscription_success(organization, tier='team'):
        """Simulate successful subscription for development/testing ONLY"""
        from flask import current_app
        from datetime import timedelta
        from ..models import Subscription
        
        logger.info(f"Simulating subscription for org {organization.id}, tier: {tier}")
        
        # PRIMARY CONTROL: Only allow simulation if tier is explicitly marked as NOT stripe-ready
        from ..blueprints.developer.subscription_tiers import load_tiers_config
        tiers_config = load_tiers_config()
        tier_data = tiers_config.get(tier, {})
        is_stripe_ready = tier_data.get('is_stripe_ready', False)
        
        # If stripe_ready is checked, force production mode - no simulation allowed
        if is_stripe_ready:
            logger.warning(f"Tier {tier} is stripe-ready - simulation blocked, must use real Stripe")
            return False
            
        # Development mode or non-stripe-ready tier - simulate webhook data
        subscription = organization.subscription
        if not subscription:
            logger.info(f"Creating new subscription record for organization {organization.id}")
            # Create a new subscription record
            subscription = Subscription(
                organization_id=organization.id,
                status='active',
                tier=tier,
                current_period_start=TimezoneUtils.utc_now(),
                current_period_end=TimezoneUtils.utc_now() + timedelta(days=30)
            )
            db.session.add(subscription)
        else:
            logger.info(f"Updating existing subscription for organization {organization.id}")
            # Update existing subscription
            subscription.status = 'active'
            subscription.tier = tier
            subscription.current_period_start = TimezoneUtils.utc_now()
            subscription.current_period_end = TimezoneUtils.utc_now() + timedelta(days=30)
        
        subscription.next_billing_date = subscription.current_period_end
        
        try:
            db.session.commit()
            logger.info(f"Successfully simulated subscription activation for org {organization.id}, tier: {tier}")
            return True
        except Exception as e:
            logger.error(f"Failed to simulate subscription for org {organization.id}: {str(e)}")
            db.session.rollback()
            return False
