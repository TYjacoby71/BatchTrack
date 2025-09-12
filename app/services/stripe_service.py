import stripe
import logging
import os
from flask import current_app
from datetime import datetime, timedelta
from decimal import Decimal
from app.extensions import db
from app.models.stripe_event import StripeEvent
from app.models.subscription_tier import SubscriptionTier
from app.models.models import Organization
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
        return True

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
        try:
            session = event['data']['object']
            customer_id = session.get('customer')
            metadata = session.get('metadata', {})

            # If an organization_id is present in metadata, link customer to org
            organization_id = metadata.get('organization_id')
            if organization_id and customer_id:
                org = Organization.query.get(int(organization_id))
                if org:
                    org.stripe_customer_id = customer_id
                    # Set provisional status
                    org.billing_status = 'active'
                    db.session.commit()
                    logger.info(f"Linked Stripe customer {customer_id} to organization {org.id}")
        except Exception as e:
            logger.error(f"checkout.session.completed handling error: {e}")

    @staticmethod
    def _handle_subscription_created(event):
        """Handle customer.subscription.created event"""
        StripeService._upsert_subscription_from_event(event)

    @staticmethod
    def _handle_subscription_updated(event):
        """Handle customer.subscription.updated event"""
        StripeService._upsert_subscription_from_event(event)

    @staticmethod
    def _handle_subscription_deleted(event):
        """Handle customer.subscription.deleted event"""
        try:
            subscription = event['data']['object']
            customer_id = subscription.get('customer')
            if not customer_id:
                return
            org = Organization.query.filter_by(stripe_customer_id=customer_id).first()
            if not org:
                logger.warning(f"Org not found for customer {customer_id} on subscription.deleted")
                return
            org.subscription_status = 'canceled'
            org.billing_status = 'canceled'
            db.session.commit()
        except Exception as e:
            logger.error(f"subscription.deleted handling error: {e}")

    @staticmethod
    def _handle_payment_succeeded(event):
        """Handle invoice.payment_succeeded event"""
        try:
            invoice = event['data']['object']
            customer_id = invoice.get('customer')
            if not customer_id:
                return
            org = Organization.query.filter_by(stripe_customer_id=customer_id).first()
            if not org:
                return
            org.billing_status = 'active'
            db.session.commit()
        except Exception as e:
            logger.error(f"invoice.payment_succeeded handling error: {e}")

    @staticmethod
    def _handle_payment_failed(event):
        """Handle invoice.payment_failed event"""
        try:
            invoice = event['data']['object']
            customer_id = invoice.get('customer')
            if not customer_id:
                return
            org = Organization.query.filter_by(stripe_customer_id=customer_id).first()
            if not org:
                return
            org.billing_status = 'payment_failed'
            db.session.commit()
        except Exception as e:
            logger.error(f"invoice.payment_failed handling error: {e}")

    @staticmethod
    def _upsert_subscription_from_event(event):
        """Create or update org subscription status and tier from a subscription event."""
        try:
            subscription = event['data']['object']
            customer_id = subscription.get('customer')
            if not customer_id:
                return

            org = Organization.query.filter_by(stripe_customer_id=customer_id).first()
            # If org not linked yet but customer has metadata with organization_id, link it
            if not org:
                customer = stripe.Customer.retrieve(customer_id)
                org_id_meta = None
                try:
                    org_id_meta = customer.metadata.get('organization_id') if hasattr(customer, 'metadata') else None
                except Exception:
                    org_id_meta = None
                if org_id_meta:
                    candidate = Organization.query.get(int(org_id_meta))
                    if candidate:
                        candidate.stripe_customer_id = customer_id
                        org = candidate

            if not org:
                logger.warning(f"Organization not found for customer {customer_id}")
                return

            # Map tier by price lookup_key
            items = subscription.get('items', {}).get('data', [])
            price_lookup_key = None
            if items:
                price = items[0].get('price', {})
                price_lookup_key = price.get('lookup_key')
            tier_to_set = None
            if price_lookup_key:
                # Normalize to monthly key for mapping
                base_lookup = StripeService.derive_interval_lookup_key(price_lookup_key, target_interval='monthly')
                tier_to_set = SubscriptionTier.query.filter_by(stripe_lookup_key=base_lookup).first()

            if tier_to_set:
                org.subscription_tier_id = tier_to_set.id

            # Update status fields
            status = subscription.get('status')
            if status:
                org.subscription_status = status
                if status in ['active', 'trialing']:
                    org.billing_status = 'active'
                    org.is_active = True
                elif status in ['past_due', 'unpaid']:
                    org.billing_status = 'payment_failed'
                elif status in ['canceled', 'incomplete_expired']:
                    org.billing_status = 'canceled'

            # Persist subscription id
            if subscription.get('id'):
                org.stripe_subscription_id = subscription['id']

            db.session.commit()
        except Exception as e:
            logger.error(f"subscription upsert handling error: {e}")

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
            # Use lookup_key to find the price - prefer monthly; include yearly if present
            monthly_key = tier_obj.stripe_lookup_key
            yearly_key = StripeService.derive_interval_lookup_key(monthly_key, target_interval='yearly')

            monthly_price = StripeService._get_price_by_lookup_key(monthly_key)
            yearly_price = StripeService._get_price_by_lookup_key(yearly_key) if yearly_key != monthly_key else None

            if not monthly_price and not yearly_price:
                logger.warning(f"No active Stripe price found for lookup keys: {monthly_key} / {yearly_key}")
                return None

            def _fmt(price_obj):
                amt = price_obj.unit_amount / 100
                return f'${amt:.0f}'

            result = {
                'lookup_key_monthly': monthly_key,
                'lookup_key_yearly': yearly_key if yearly_price else None,
                'currency': (monthly_price.currency if monthly_price else yearly_price.currency).upper(),
                'billing_cycle': 'monthly' if monthly_price else 'yearly'
            }
            if monthly_price:
                result['price_id_monthly'] = monthly_price.id
                result['price_monthly'] = _fmt(monthly_price)
            if yearly_price:
                result['price_id_yearly'] = yearly_price.id
                result['price_yearly'] = _fmt(yearly_price)

            return result

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
            # Choose price by requested billing_cycle metadata if present
            requested_cycle = (metadata or {}).get('billing_cycle')
            if requested_cycle == 'yearly' and pricing.get('price_id_yearly'):
                selected_price_id = pricing['price_id_yearly']
            else:
                selected_price_id = pricing.get('price_id_monthly') or pricing.get('price_id_yearly')

            session = stripe.checkout.Session.create(
                customer=customer.id,
                payment_method_types=['card'],
                line_items=[{
                    'price': selected_price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'tier_key': tier_obj.key,
                    'lookup_key_monthly': pricing.get('lookup_key_monthly'),
                    'lookup_key_yearly': pricing.get('lookup_key_yearly'),
                    'selected_billing_cycle': 'yearly' if selected_price_id == pricing.get('price_id_yearly') else 'monthly',
                    **(metadata or {})
                }
            )

            logger.info(f"Created checkout session for tier {tier_obj.key} with price {pricing['price_id']}")
            return session

        except stripe.error.StripeError as e:
            logger.error(f"Failed to create checkout session for tier {tier_obj.key}: {e}")
            return None

    @staticmethod
    def _get_price_by_lookup_key(lookup_key: str):
        """Return the first active Price for a lookup key, or None."""
        if not lookup_key:
            return None
        prices = stripe.Price.list(lookup_keys=[lookup_key], active=True, limit=1)
        return prices.data[0] if prices.data else None

    @staticmethod
    def derive_interval_lookup_key(base_lookup_key: str, target_interval: str = 'yearly') -> str:
        """Derive a yearly or monthly lookup key from a monthly base name.
        Convention: replace suffix '_monthly' with '_yearly' and vice versa.
        """
        if not base_lookup_key:
            return base_lookup_key
        if target_interval == 'yearly':
            return base_lookup_key.replace('_monthly', '_yearly')
        if target_interval == 'monthly':
            return base_lookup_key.replace('_yearly', '_monthly')
        return base_lookup_key

    @staticmethod
    def sync_product_from_stripe(lookup_key):
        """Sync a single product from Stripe to local PricingSnapshot entries."""
        if not StripeService.initialize_stripe():
            return False

        try:
            # Import here to avoid circular imports
            from app.models.pricing_snapshot import PricingSnapshot

            # Get all active prices for the lookup key (both intervals)
            prices = stripe.Price.list(lookup_keys=[lookup_key, StripeService.derive_interval_lookup_key(lookup_key, 'yearly')], active=True, limit=10)
            if not prices.data:
                logger.warning(f"No Stripe prices found for lookup key(s): {lookup_key}")
                return False

            updated_any = False
            for price in prices.auto_paging_iter():
                try:
                    product = stripe.Product.retrieve(price.product)
                    snapshot = PricingSnapshot.update_from_stripe_data(price, product)
                    updated_any = True or updated_any
                except Exception as inner:
                    logger.error(f"Failed to create snapshot for price {price.id}: {inner}")

            if updated_any:
                db.session.commit()
                logger.info(f"Pricing snapshots updated for lookup key(s) starting with {lookup_key}")
                return True
            return False

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
        """Get live pricing for Stripe tiers only"""
        stripe_tiers = SubscriptionTier.query.filter_by(
            is_customer_facing=True,
            billing_provider='stripe'
        ).all()

        pricing_data = {'tiers': {}, 'available': True, 'provider': 'stripe'}

        for tier in stripe_tiers:
            pricing = StripeService.get_live_pricing_for_tier(tier)

            pricing_data['tiers'][tier.key] = {
                'name': tier.name,
                'description': getattr(tier, 'description', ''),
                'user_limit': tier.user_limit,
                'permissions': [p.name for p in tier.permissions] if hasattr(tier, 'permissions') else [],
                'price': pricing['formatted_price'] if pricing else 'N/A',
                'billing_cycle': pricing['billing_cycle'] if pricing else 'monthly',
                'available': pricing is not None,
                'stripe_available': pricing is not None,
                'provider': 'stripe'
            }

        return pricing_data