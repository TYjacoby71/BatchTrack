import stripe
import logging
import os
from flask import current_app
from datetime import datetime, timedelta
from decimal import Decimal
from app.extensions import db
from app.models.stripe_event import StripeEvent
from ..models import db, SubscriptionTier, Organization
from ..utils.timezone_utils import TimezoneUtils


logger = logging.getLogger(__name__)

class StripeService:
    """Service for handling Stripe integration and billing operations"""

    @staticmethod
    def initialize():
        """Initialize Stripe with API key"""
        api_key = current_app.config.get('STRIPE_SECRET_KEY')
        if not api_key:
            raise ValueError("STRIPE_SECRET_KEY not configured")

        stripe.api_key = api_key
        logger.info("Stripe service initialized")

    @staticmethod
    def construct_event(payload: bytes, sig_header: str, webhook_secret: str):
        """Construct Stripe event from webhook payload"""
        return stripe.Webhook.construct_event(payload, sig_header, webhook_secret)

    

    @staticmethod
    def get_customer(customer_id: str):
        """Get Stripe customer by ID"""
        try:
            return stripe.Customer.retrieve(customer_id)
        except Exception as e:
            logger.error(f"Failed to retrieve customer {customer_id}: {str(e)}")
            return None

    @staticmethod
    def get_checkout_session(session_id: str):
        """Get Stripe checkout session by ID"""
        try:
            return stripe.checkout.Session.retrieve(session_id)
        except Exception as e:
            logger.error(f"Failed to retrieve checkout session {session_id}: {str(e)}")
            return None

    @staticmethod
    def handle_webhook_event(event: dict) -> int:
        """Handle Stripe webhook event with idempotency"""
        from sqlalchemy.exc import IntegrityError
        
        # Insert-first pattern to handle concurrent replays
        stripe_event = StripeEvent(
            event_id=event["id"],
            event_type=event["type"],
            status='received'
        )
        
        try:
            db.session.add(stripe_event)
            db.session.commit()
        except IntegrityError:
            # Event already exists (concurrent replay)
            db.session.rollback()
            logger.info(f"Replay detected for event {event['id']}, skipping")
            return 200

        try:
            # Route by event type
            event_type = event["type"]

            if event_type == "checkout.session.completed":
                StripeService._handle_checkout_completed(event)
            elif event_type == "customer.subscription.created":
                StripeService._handle_subscription_created(event)
            elif event_type == "customer.subscription.updated":
                StripeService._handle_subscription_updated(event)
            elif event_type == "customer.subscription.deleted":
                StripeService._handle_subscription_deleted(event)
            elif event_type == "invoice.payment_succeeded":
                StripeService._handle_payment_succeeded(event)
            elif event_type == "invoice.payment_failed":
                StripeService._handle_payment_failed(event)
            else:
                logger.info(f"Unhandled webhook event type: {event_type}")

            # Mark as processed
            stripe_event.status = 'processed'
            stripe_event.processed_at = datetime.utcnow()
            db.session.commit()

            return 200

        except Exception as e:
            logger.error(f"Error processing webhook event {event['id']}: {str(e)}")
            stripe_event.status = 'failed'
            stripe_event.error_message = str(e)
            db.session.commit()
            return 500

    @staticmethod
    def _handle_checkout_completed(event):
        """Handle checkout.session.completed event"""
        # Implementation moved from routes - this would contain the signup completion logic
        pass

    @staticmethod
    def _handle_subscription_created(event):
        """Handle customer.subscription.created event"""
        pass

    @staticmethod
    def _handle_subscription_updated(event):
        """Handle customer.subscription.updated event"""
        pass

    @staticmethod
    def _handle_subscription_deleted(event):
        """Handle customer.subscription.deleted event"""
        pass

    @staticmethod
    def _handle_payment_succeeded(event):
        """Handle invoice.payment_succeeded event"""
        pass

    @staticmethod
    def _handle_payment_failed(event):
        """Handle invoice.payment_failed event"""
        pass

    @staticmethod
    def initialize_stripe():
        """Initialize Stripe with API key"""
        stripe_secret = os.environ.get('STRIPE_SECRET_KEY')
        if not stripe_secret:
            logger.warning("Stripe secret key not configured")
            return False
        stripe.api_key = stripe_secret
        logger.info("Stripe initialized successfully")
        return True

    @staticmethod
    def get_live_pricing_for_tier(tier_obj):
        """Get live pricing from Stripe for a subscription tier"""
        if not StripeService.initialize_stripe():
            return None

        if not tier_obj.stripe_lookup_key:
            return None

        try:
            # Use lookup_key to find the price - this is the industry standard
            prices = stripe.Price.list(
                lookup_keys=[tier_obj.stripe_lookup_key],
                active=True,
                limit=1
            )

            if not prices.data:
                logger.warning(f"No active Stripe price found for lookup key: {tier_obj.stripe_lookup_key}")
                return None

            price = prices.data[0]

            # Format pricing data
            amount = price.unit_amount / 100
            currency = price.currency.upper()

            billing_cycle = 'one-time'
            if price.recurring:
                billing_cycle = 'yearly' if price.recurring.interval == 'year' else 'monthly'

            return {
                'price_id': price.id,
                'amount': amount,
                'formatted_price': f'${amount:.0f}',
                'currency': currency,
                'billing_cycle': billing_cycle,
                'lookup_key': tier_obj.stripe_lookup_key
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error fetching price for {tier_obj.stripe_lookup_key}: {e}")
            return None

    @staticmethod
    def create_checkout_session_for_tier(tier_obj, customer_email, customer_name, success_url, cancel_url, metadata=None):
        """Create checkout session using tier's lookup key - industry standard"""
        if not StripeService.initialize_stripe():
            return None

        # Get live pricing first
        pricing = StripeService.get_live_pricing_for_tier(tier_obj)
        if not pricing:
            logger.error(f"No pricing found for tier {tier_obj.key}")
            return None

        try:
            # Create customer first (industry standard)
            customer = stripe.Customer.create(
                email=customer_email,
                name=customer_name,
                metadata=metadata or {}
            )

            # Create checkout session with live price ID
            session = stripe.checkout.Session.create(
                customer=customer.id,
                payment_method_types=['card'],
                line_items=[{
                    'price': pricing['price_id'],
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'tier_key': tier_obj.key,
                    'lookup_key': tier_obj.stripe_lookup_key,
                    **(metadata or {})
                }
            )

            logger.info(f"Created checkout session for tier {tier_obj.key} with price {pricing['price_id']}")
            return session

        except stripe.error.StripeError as e:
            logger.error(f"Failed to create checkout session for tier {tier_obj.key}: {e}")
            return None

    @staticmethod
    def sync_product_from_stripe(lookup_key):
        """Sync a single product from Stripe to local database"""
        if not StripeService.initialize_stripe():
            return False

        try:
            # Get product by lookup key
            prices = stripe.Price.list(
                lookup_keys=[lookup_key],
                active=True,
                limit=1
            )

            if not prices.data:
                logger.warning(f"No Stripe product found for lookup key: {lookup_key}")
                return False

            price = prices.data[0]
            product = stripe.Product.retrieve(price.product)

            # Update local tier with Stripe data
            tier_obj = SubscriptionTier.query.filter_by(stripe_lookup_key=lookup_key).first()
            if tier_obj:
                # Update pricing info
                tier_obj.fallback_price = f"${price.unit_amount / 100:.0f}"
                tier_obj.last_billing_sync = TimezoneUtils.utc_now()

                # Store Stripe metadata
                if hasattr(tier_obj, 'stripe_metadata'):
                    tier_obj.stripe_metadata = {
                        'product_id': product.id,
                        'price_id': price.id,
                        'last_synced': TimezoneUtils.utc_now().isoformat()
                    }

                db.session.commit()
                logger.info(f"Synced tier {tier_obj.key} with Stripe product {product.name}")
                return True

        except stripe.error.StripeError as e:
            logger.error(f"Error syncing product from Stripe: {e}")
            return False

    @staticmethod
    def handle_subscription_webhook(event):
        """Handle subscription webhooks - industry standard"""
        event_type = event['type']
        subscription = event['data']['object']

        try:
            # Find organization by customer
            customer_id = subscription['customer']
            customer = stripe.Customer.retrieve(customer_id)

            organization_id = customer.metadata.get('organization_id')
            if not organization_id:
                logger.error(f"No organization_id in customer metadata for {customer_id}")
                return False

            organization = Organization.query.get(organization_id)
            if not organization:
                logger.error(f"Organization {organization_id} not found")
                return False

            # Get tier from subscription metadata
            tier_key = subscription.get('metadata', {}).get('tier_key')
            if tier_key:
                tier = SubscriptionTier.query.filter_by(key=tier_key).first()
                if tier:
                    organization.subscription_tier_id = tier.id

            # Handle subscription status
            status = subscription['status']
            if status == 'active':
                organization.is_active = True
                organization.billing_status = 'active'
            elif status in ['past_due', 'unpaid']:
                organization.billing_status = 'payment_failed'
                organization.is_active = False
            elif status == 'canceled':
                organization.billing_status = 'canceled'
                organization.is_active = False

            # Store Stripe customer ID if not present
            if not organization.stripe_customer_id:
                organization.stripe_customer_id = customer_id

            db.session.commit()
            logger.info(f"Updated organization {organization.id} from {event_type}")
            return True

        except Exception as e:
            logger.error(f"Webhook handling failed: {e}")
            db.session.rollback()
            return False

    @staticmethod
    def create_customer_portal_session(organization, return_url):
        """Create customer portal session for billing management"""
        if not StripeService.initialize_stripe():
            return None

        if not organization.stripe_customer_id:
            logger.error(f"No Stripe customer ID for organization {organization.id}")
            return None

        try:
            session = stripe.billing_portal.Session.create(
                customer=organization.stripe_customer_id,
                return_url=return_url
            )
            return session

        except stripe.error.StripeError as e:
            logger.error(f"Failed to create portal session: {e}")
            return None

    @staticmethod
    def get_all_available_pricing():
        """Get live pricing for all available tiers - for signup page"""
        available_tiers = SubscriptionTier.query.filter_by(
            is_customer_facing=True,
            is_available=True,
            requires_stripe_billing=True
        ).all()

        pricing_data = {}

        for tier in available_tiers:
            pricing = StripeService.get_live_pricing_for_tier(tier)

            pricing_data[tier.key] = {
                'name': tier.name,
                'description': tier.description,
                'user_limit': tier.user_limit,
                'permissions': tier.get_permissions(),
                'price': pricing['formatted_price'] if pricing else tier.fallback_price,
                'billing_cycle': pricing['billing_cycle'] if pricing else 'monthly',
                'available': pricing is not None,
                'stripe_available': pricing is not None
            }

        return pricing_data