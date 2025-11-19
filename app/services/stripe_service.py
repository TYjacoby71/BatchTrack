import stripe
import logging
import os
from flask import current_app
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import stripe.error as stripe_error
from app.extensions import db
from app.models.stripe_event import StripeEvent
from app.models.subscription_tier import SubscriptionTier
from app.models.models import Organization
from app.models.pending_signup import PendingSignup
from .signup_service import SignupService
from ..utils.timezone_utils import TimezoneUtils


logger = logging.getLogger(__name__)

class StripeService:
    """Service for handling Stripe integration and billing operations"""

    # Simple in-process cache for pricing lookups to reduce Stripe calls
    _pricing_cache = {}
    _pricing_cache_ttl_seconds = 600  # 10 minutes

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
            stripe_event.processed_at = datetime.now(timezone.utc)
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
            obj = event.get('data', {}).get('object', {})
            session_id = obj.get('id')
            if not StripeService.initialize_stripe():
                return
            import stripe
            checkout = stripe.checkout.Session.retrieve(
                session_id,
                expand=['customer', 'customer_details', 'line_items.data.price']
            )
            StripeService._provision_checkout_session(checkout)
        except Exception as e:
            logger.error(f"Error handling checkout.session.completed: {e}")
            return

    @staticmethod
    def _handle_subscription_created(event):
        try:
            obj = event.get('data', {}).get('object', {})
            customer_id = obj.get('customer')
            status = obj.get('status')
            items = obj.get('items', {}).get('data', [])
            price = items[0]['price'] if items else None
            lookup_key = price.get('id') if price else None

            from ..extensions import db
            from ..models.models import Organization
            from ..models.subscription_tier import SubscriptionTier
            from ..models.addon import Addon, OrganizationAddon

            # Resolve organization
            org = Organization.query.filter_by(stripe_customer_id=customer_id).first()
            if not org:
                # Fallback to customer metadata lookup
                if StripeService.initialize_stripe():
                    try:
                        cust = stripe.Customer.retrieve(customer_id)
                        org_id_meta = (cust.metadata or {}).get('organization_id')
                        if org_id_meta:
                            org = Organization.query.get(int(org_id_meta))
                    except Exception as _e:
                        logger.warning(f"Could not resolve org from customer metadata: {_e}")
            if not org:
                logger.warning(f"Subscription.created for unknown customer {customer_id}")
                return

            # Update organization billing/subscription status
            org.subscription_status = status or org.subscription_status
            if status in ['active', 'trialing']:
                org.billing_status = 'active'
                org.is_active = True
            elif status in ['past_due', 'unpaid']:
                org.billing_status = 'past_due'
                org.is_active = False
            elif status in ['canceled', 'cancelled']:
                org.billing_status = 'canceled'
                org.is_active = False

            if not org.stripe_customer_id:
                org.stripe_customer_id = customer_id

            # Activate add-on on subscription creation if lookup matches
            matching_addon = Addon.query.filter_by(stripe_lookup_key=lookup_key).first()
            if matching_addon:
                # Upsert OrganizationAddon
                existing = OrganizationAddon.query.filter_by(
                    organization_id=org.id,
                    addon_id=matching_addon.id
                ).first()
                if existing:
                    existing.active = status in ['active', 'trialing']
                    existing.stripe_item_id = obj.get('id')
                    existing.current_period_end = datetime.utcfromtimestamp(obj.get('current_period_end')) if obj.get('current_period_end') else None
                else:
                    assoc = OrganizationAddon(
                        organization_id=org.id,
                        addon_id=matching_addon.id,
                        active=status in ['active', 'trialing'],
                        source='subscription_item',
                        stripe_item_id=obj.get('id'),
                        current_period_end=datetime.utcfromtimestamp(obj.get('current_period_end')) if obj.get('current_period_end') else None
                    )
                    db.session.add(assoc)

            db.session.commit()
        except Exception as e:
            logger.error(f"Error handling subscription.created: {e}")

    @staticmethod
    def _handle_subscription_updated(event):
        try:
            obj = event.get('data', {}).get('object', {})
            sub_id = obj.get('id')
            status = obj.get('status')
            customer_id = obj.get('customer')
            from ..extensions import db
            from ..models.models import Organization
            from ..models.addon import Addon, OrganizationAddon

            # Update OrganizationAddon for matching Stripe subscription id
            rec = OrganizationAddon.query.filter_by(stripe_item_id=sub_id).first()
            if rec:
                rec.active = status in ['active', 'trialing']
                rec.current_period_end = datetime.utcfromtimestamp(obj.get('current_period_end')) if obj.get('current_period_end') else rec.current_period_end

            # Update organization billing/subscription status
            org = Organization.query.filter_by(stripe_customer_id=customer_id).first()
            if not org:
                if StripeService.initialize_stripe():
                    try:
                        cust = stripe.Customer.retrieve(customer_id)
                        org_id_meta = (cust.metadata or {}).get('organization_id')
                        if org_id_meta:
                            org = Organization.query.get(int(org_id_meta))
                    except Exception as _e:
                        logger.warning(f"Could not resolve org from customer metadata: {_e}")

            if org:
                org.subscription_status = status or org.subscription_status
                if status in ['active', 'trialing']:
                    org.billing_status = 'active'
                    org.is_active = True
                elif status in ['past_due', 'unpaid']:
                    org.billing_status = 'past_due'
                    org.is_active = False
                elif status in ['canceled', 'cancelled']:
                    org.billing_status = 'canceled'
                    org.is_active = False

            db.session.commit()
        except Exception as e:
            logger.error(f"Error handling subscription.updated: {e}")

    @staticmethod
    def _handle_subscription_deleted(event):
        try:
            obj = event.get('data', {}).get('object', {})
            sub_id = obj.get('id')
            customer_id = obj.get('customer')
            from ..extensions import db
            from ..models.models import Organization
            from ..models.addon import OrganizationAddon

            rec = OrganizationAddon.query.filter_by(stripe_item_id=sub_id).first()
            if rec:
                rec.active = False

            org = Organization.query.filter_by(stripe_customer_id=customer_id).first()
            if not org:
                if StripeService.initialize_stripe():
                    try:
                        cust = stripe.Customer.retrieve(customer_id)
                        org_id_meta = (cust.metadata or {}).get('organization_id')
                        if org_id_meta:
                            org = Organization.query.get(int(org_id_meta))
                    except Exception as _e:
                        logger.warning(f"Could not resolve org from customer metadata: {_e}")

            if org:
                org.subscription_status = 'canceled'
                org.billing_status = 'canceled'
                org.is_active = False

            db.session.commit()
        except Exception as e:
            logger.error(f"Error handling subscription.deleted: {e}")

    # Removed duplicate stub handlers that previously overwrote real implementations

    @staticmethod
    def _handle_payment_succeeded(event):
        """Handle invoice.payment_succeeded event"""
        try:
            invoice = event.get('data', {}).get('object', {})
            customer_id = invoice.get('customer')
            if not customer_id:
                return

            org = Organization.query.filter_by(stripe_customer_id=customer_id).first()
            if not org:
                logger.warning("Payment succeeded for unknown customer %s", customer_id)
                return

            org.billing_status = 'active'
            org.subscription_status = 'active'
            next_payment_time = invoice.get('next_payment_attempt') or invoice.get('period_end')
            if next_payment_time:
                try:
                    org.next_billing_date = datetime.utcfromtimestamp(next_payment_time).date()
                except Exception:
                    pass

            db.session.commit()
        except Exception as exc:
            logger.error(f"Error handling payment succeeded: {exc}")
            db.session.rollback()

    @staticmethod
    def _handle_payment_failed(event):
        """Handle invoice.payment_failed event"""
        try:
            invoice = event.get('data', {}).get('object', {})
            customer_id = invoice.get('customer')
            if not customer_id:
                return

            org = Organization.query.filter_by(stripe_customer_id=customer_id).first()
            if not org:
                logger.warning("Payment failed for unknown customer %s", customer_id)
                return

            org.billing_status = 'payment_failed'
            org.subscription_status = 'past_due'
            db.session.commit()
        except Exception as exc:
            logger.error(f"Error handling payment failed: {exc}")
            db.session.rollback()

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
        # Serve from cache if fresh
        try:
            cache_key = f"price::{tier_obj.stripe_lookup_key}"
            now = datetime.now(timezone.utc)
            cached = StripeService._pricing_cache.get(cache_key)
            if cached and (now - cached['ts']).total_seconds() < StripeService._pricing_cache_ttl_seconds:
                return cached['data']
        except Exception:
            pass

        if not StripeService.initialize_stripe():
            return None

        if not tier_obj.stripe_lookup_key:
            return None

        price_obj = None
        try:
            price_obj, resolution_strategy = StripeService._resolve_price_for_lookup_key(
                tier_obj.stripe_lookup_key
            )

            if not price_obj:
                logger.warning(
                    "No active Stripe price found for lookup key %s; ensure the price exists and is active",
                    tier_obj.stripe_lookup_key,
                )
                return None

            # Format pricing data
            amount = price_obj.unit_amount / 100
            currency = price_obj.currency.upper()

            billing_cycle = 'one-time'
            if price_obj.recurring:
                billing_cycle = 'yearly' if price_obj.recurring.interval == 'year' else 'monthly'

            if resolution_strategy != 'lookup_key':
                logger.info(
                    "Resolved Stripe price %s for lookup key %s using %s fallback",
                    price_obj.id,
                    tier_obj.stripe_lookup_key,
                    resolution_strategy,
                )

            return {
                'price_id': price_obj.id,
                'amount': amount,
                'formatted_price': f'${amount:.0f}',
                'currency': currency,
                'billing_cycle': billing_cycle,
                'lookup_key': tier_obj.stripe_lookup_key,
                'last_synced': datetime.now(timezone.utc).isoformat()
            }

        except stripe_error.StripeError as e:
            logger.error(f"Stripe error fetching price for {tier_obj.stripe_lookup_key}: {e}")
            return None
        finally:
            # Cache successful lookups
            try:
                if price_obj:
                    data = {
                        'price_id': price_obj.id,
                        'amount': price_obj.unit_amount / 100,
                        'formatted_price': f"${price_obj.unit_amount / 100:.0f}",
                        'currency': price_obj.currency.upper(),
                        'billing_cycle': 'yearly' if getattr(price_obj, 'recurring', None) and price_obj.recurring.interval == 'year' else ('monthly' if getattr(price_obj, 'recurring', None) and price_obj.recurring.interval == 'month' else 'one-time'),
                        'lookup_key': tier_obj.stripe_lookup_key,
                        'last_synced': datetime.now(timezone.utc).isoformat()
                    }
                    StripeService._pricing_cache[cache_key] = {'ts': datetime.now(timezone.utc), 'data': data}
            except Exception:
                pass
    
    @staticmethod
    def _resolve_price_for_lookup_key(lookup_key: str):
        """
        Attempt to resolve a Stripe price for the given lookup key.
        Returns a tuple of (price_object, resolution_strategy).
        """
        price_obj = None
        strategy = 'lookup_key'

        try:
            price_list = stripe.Price.list(
                lookup_keys=[lookup_key],
                active=True,
                limit=1
            )

            if price_list.data:
                return price_list.data[0], strategy

            logger.warning(
                "Stripe lookup by lookup_key failed for %s; attempting to treat it as a price ID",
                lookup_key,
            )

            if lookup_key.startswith('price_'):
                strategy = 'price_id_fallback'
                price_obj = stripe.Price.retrieve(lookup_key)
                if getattr(price_obj, 'active', False):
                    return price_obj, strategy
                logger.warning(
                    "Stripe price %s retrieved via fallback is not active",
                    lookup_key,
                )
                return None, strategy

            return None, 'lookup_key'

        except stripe_error.StripeError:
            # Propagate to caller for centralized logging/handling
            raise

    @staticmethod
    def create_checkout_session_for_tier(
        tier_obj,
        *,
        customer_email: str,
        success_url: str,
        cancel_url: str,
        metadata: dict | None = None,
        client_reference_id: str | None = None,
        phone_required: bool = True,
        allow_promo: bool = True,
    ):
        """Create checkout session using tier's lookup key with minimal required inputs."""
        if not StripeService.initialize_stripe():
            return None

        # Get live pricing first
        pricing = StripeService.get_live_pricing_for_tier(tier_obj)
        if not pricing:
            logger.error(f"No pricing found for tier {tier_obj.name} (ID: {tier_obj.id})")
            return None

        if not customer_email:
            logger.error("Customer email is required to create Stripe checkout session")
            return None

        try:
            session = stripe.checkout.Session.create(
                mode='subscription',
                payment_method_types=['card'],
                line_items=[{
                    'price': pricing['price_id'],
                    'quantity': 1,
                }],
                success_url=success_url,
                cancel_url=cancel_url,
                customer_email=customer_email,
                client_reference_id=client_reference_id,
                billing_address_collection='auto',
                phone_number_collection={'enabled': phone_required},
                allow_promotion_codes=allow_promo,
                metadata={
                    'tier_id': str(tier_obj.id),
                    'tier_name': tier_obj.name,
                    'lookup_key': tier_obj.stripe_lookup_key,
                    **(metadata or {})
                },
            )

            logger.info(
                "Created checkout session %s for tier %s (%s) with price %s",
                session.id,
                tier_obj.name,
                tier_obj.id,
                pricing['price_id'],
            )
            return session

        except stripe_error.StripeError as e:
            logger.error(
                "Failed to create checkout session for tier %s (ID: %s): %s",
                tier_obj.name,
                tier_obj.id,
                e,
            )
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
                logger.info(f"Synced tier {tier_obj.name} (ID: {tier_obj.id}) with Stripe product {product.name}")
                return True

        except stripe_error.StripeError as e:
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
            tier_id = subscription.get('metadata', {}).get('tier_id')
            if tier_id:
                try:
                    tier = SubscriptionTier.query.get(int(tier_id))
                    if tier:
                        organization.subscription_tier_id = tier.id
                except (ValueError, TypeError):
                    # Fallback: try by name if tier_id fails
                    tier_name = subscription.get('metadata', {}).get('tier_name')
                    if tier_name:
                        tier = SubscriptionTier.query.filter_by(name=tier_name).first()
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

        except stripe_error.StripeError as e:
            logger.error(f"Failed to create portal session: {e}")
            return None

    @staticmethod
    def cancel_subscription(stripe_customer_id: str) -> bool:
        """Cancel all active subscriptions for a given Stripe customer."""
        if not stripe_customer_id:
            return False
        if not StripeService.initialize_stripe():
            return False
        import stripe
        try:
            subs = stripe.Subscription.list(customer=stripe_customer_id, status='active', limit=20)
            cancelled = False
            for sub in subs.auto_paging_iter():
                stripe.Subscription.delete(sub.id)
                cancelled = True
            if not cancelled:
                logger.info("No active subscriptions to cancel for customer %s", stripe_customer_id)
            return cancelled
        except Exception as exc:
            logger.error(f"Failed to cancel subscription for customer {stripe_customer_id}: {exc}")
            return False

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

            pricing_data['tiers'][str(tier.id)] = {
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

    @staticmethod
    def update_customer_metadata(customer_id: str, metadata: dict) -> bool:
        """Merge and update metadata on a Stripe customer."""
        if not StripeService.initialize_stripe():
            return False
        try:
            # Retrieve existing metadata to merge
            cust = stripe.Customer.retrieve(customer_id)
            existing = dict(getattr(cust, 'metadata', {}) or {})
            existing.update(metadata or {})
            stripe.Customer.modify(customer_id, metadata=existing)
            return True
        except Exception as e:
            logger.error(f"Failed to update customer metadata for {customer_id}: {e}")
            return False

    @staticmethod
    def finalize_checkout_session(session_id: str):
        """Finalize (or refinalize) a Stripe checkout session by ID."""
        if not session_id:
            return None
        if not StripeService.initialize_stripe():
            return None
        import stripe
        checkout = stripe.checkout.Session.retrieve(
            session_id,
            expand=['customer', 'customer_details', 'line_items.data.price']
        )
        return StripeService._provision_checkout_session(checkout)

    @staticmethod
    def _provision_checkout_session(checkout_session):
        """Internal helper shared by webhook + success URL to build accounts."""
        pending_id = StripeService._get_pending_signup_id_from_session(checkout_session)
        if not pending_id:
            logger.info("Checkout session %s missing pending signup reference", getattr(checkout_session, 'id', 'unknown'))
            return None

        pending = db.session.get(PendingSignup, pending_id)
        if not pending:
            logger.warning("Pending signup %s not found for checkout session %s", pending_id, getattr(checkout_session, 'id', 'unknown'))
            return None

        import stripe
        customer_obj = getattr(checkout_session, 'customer', None)
        if isinstance(customer_obj, str):
            customer_obj = stripe.Customer.retrieve(customer_obj)

        try:
            org, user = SignupService.complete_pending_signup_from_checkout(pending, checkout_session, customer_obj)

            # Store metadata back on customer for future subscription events
            if getattr(customer_obj, 'id', None) and org:
                StripeService.update_customer_metadata(customer_obj.id, {
                    'organization_id': str(org.id),
                    'tier_id': str(org.subscription_tier_id or ''),
                })
            return org, user
        except Exception as exc:
            logger.error("Failed provisioning checkout session %s: %s", getattr(checkout_session, 'id', 'unknown'), exc)
            raise

    @staticmethod
    def _get_pending_signup_id_from_session(checkout_session):
        metadata = getattr(checkout_session, 'metadata', {}) or {}
        client_reference_id = getattr(checkout_session, 'client_reference_id', None)
        candidate = metadata.get('pending_signup_id') or client_reference_id
        if not candidate:
            return None
        try:
            return int(candidate)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _create_checkout_session_by_lookup_key(
        lookup_key,
        customer_email,
        success_url,
        cancel_url,
        metadata=None,
        mode='subscription'
    ):
        if not StripeService.initialize_stripe():
            return None
        import stripe
        try:
            session = stripe.checkout.Session.create(
                mode=mode,
                line_items=[{
                    'price': lookup_key,
                    'quantity': 1
                }],
                customer_email=customer_email,
                success_url=success_url,
                cancel_url=cancel_url,
                allow_promotion_codes=True,
                billing_address_collection='auto',
                phone_number_collection={'enabled': True},
                metadata=metadata or {}
            )
            return session
        except Exception as e:
            logger.error(f"Stripe {mode} checkout error: {e}")
            return None

    @staticmethod
    def create_one_time_checkout_by_lookup_key(lookup_key, customer_email, success_url, cancel_url, metadata=None):
        """Create a one-time checkout session for an add-on using a price lookup key."""
        return StripeService._create_checkout_session_by_lookup_key(
            lookup_key,
            customer_email,
            success_url,
            cancel_url,
            metadata=metadata,
            mode='payment'
        )

    @staticmethod
    def create_subscription_checkout_by_lookup_key(lookup_key, customer_email, success_url, cancel_url, metadata=None):
        """Create a subscription checkout session for a recurring add-on using price lookup key."""
        return StripeService._create_checkout_session_by_lookup_key(
            lookup_key,
            customer_email,
            success_url,
            cancel_url,
            metadata=metadata,
            mode='subscription'
        )