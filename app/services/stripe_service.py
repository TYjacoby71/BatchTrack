
import stripe
import logging
from flask import current_app, url_for
from ..models import db, Subscription
from ..utils.timezone_utils import TimezoneUtils

logger = logging.getLogger(__name__)

class StripeService:
    """Service for handling Stripe payment operations"""
    
    @staticmethod
    def initialize_stripe():
        """Initialize Stripe with API key"""
        stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    
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
        StripeService.initialize_stripe()
        
        price_id = current_app.config['STRIPE_PRICE_IDS'].get(tier)
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
                success_url=url_for('organization.dashboard', _external=True) + '?payment=success',
                cancel_url=url_for('organization.dashboard', _external=True) + '?payment=cancelled',
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
            
            # Update subscription
            subscription.stripe_subscription_id = subscription_id
            subscription.status = 'active'
            subscription.current_period_start = TimezoneUtils.utc_now()
            subscription.current_period_end = TimezoneUtils.from_timestamp(
                stripe_subscription['current_period_end']
            )
            subscription.next_billing_date = subscription.current_period_end
            
            # Set tier based on metadata or price
            metadata = stripe_subscription.get('metadata', {})
            if 'tier' in metadata:
                subscription.tier = metadata['tier']
            
            db.session.commit()
            logger.info(f"Updated subscription {subscription.id} with Stripe data")
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
