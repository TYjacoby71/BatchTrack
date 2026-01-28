import logging
import os
from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from threading import Lock

import stripe
from flask import current_app

from ..extensions import db
from ..models.models import Organization
from ..models.pending_signup import PendingSignup
from ..models.stripe_event import StripeEvent
from ..models.subscription_tier import SubscriptionTier
from ..utils.timezone_utils import TimezoneUtils
from .signup_service import SignupService
from ..utils.cache_manager import app_cache

try:
    from stripe import exceptions as stripe_exceptions  # Stripe >= 11
except (ImportError, AttributeError):
    stripe_exceptions = None

if stripe_exceptions and hasattr(stripe_exceptions, 'StripeError'):
    StripeError = stripe_exceptions.StripeError
else:
    StripeError = getattr(getattr(stripe, 'error', None), 'StripeError', None)
    if StripeError is None:
        class StripeError(Exception):
            """Fallback Stripe error base when SDK structure changes."""
            pass


logger = logging.getLogger(__name__)

class BillingService:
    """Consolidated billing + Stripe orchestration service."""

    _pricing_cache_ttl_seconds = 600  # 10 minutes
    _pricing_error_cache_ttl_seconds = 60
    _pricing_lock_registry: dict[str, Lock] = defaultdict(Lock)
    _pricing_registry_lock = Lock()

    @classmethod
    def _pricing_cache_key(cls, lookup_key: str) -> str:
        return f"billing:price:{lookup_key}"

    @classmethod
    def _get_pricing_lock(cls, lookup_key: str) -> Lock:
        with cls._pricing_registry_lock:
            lock = cls._pricing_lock_registry.get(lookup_key)
            if not lock:
                lock = Lock()
                cls._pricing_lock_registry[lookup_key] = lock
            return lock

    # ------------------------------------------------------------------ #
    # Tier + organization helpers (source of truth for billing access)   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def get_tier_for_organization(organization):
        """Get the effective subscription tier for an organization."""
        if not organization or not organization.subscription_tier_id:
            return 'exempt'

        tier = db.session.get(SubscriptionTier, organization.subscription_tier_id)
        return str(tier.id) if tier else 'exempt'

    @staticmethod
    def assign_tier_to_organization(organization, tier_key):
        """Assign a subscription tier to an organization. tier_key is a tier ID string."""
        try:
            tier_id = int(tier_key)
        except (TypeError, ValueError):
            tier_id = None
        tier = db.session.get(SubscriptionTier, tier_id) if tier_id is not None else None
        if not tier:
            tier = SubscriptionTier.query.filter_by(billing_provider='exempt').first()

        if tier:
            organization.subscription_tier_id = tier.id
            db.session.commit()
            logger.info("Assigned tier %s to organization %s", tier_key, organization.id)

        return tier

    @staticmethod
    def can_add_users(organization, count=1):
        """Check if organization can add more users based on subscription tier."""
        if not organization or not organization.subscription_tier_obj:
            return False

        current_user_count = organization.users.count()
        limit = organization.subscription_tier_obj.user_limit

        if limit == -1:
            return True

        return (current_user_count + count) <= limit

    @staticmethod
    def has_tier_permission(organization, permission_name):
        """Check if organization's tier has a specific permission."""
        if not organization or not organization.subscription_tier_obj:
            return False
        return organization.subscription_tier_obj.has_permission(permission_name)

    @staticmethod
    def get_available_tiers():
        """Get all available customer-facing tiers."""
        return SubscriptionTier.query.filter_by(is_customer_facing=True).all()

    @staticmethod
    def get_permission_denied_upgrade_options(permission_name, organization):
        """Return upgrade tiers that include the given permission."""
        if not organization or not permission_name:
            return []
        try:
            current_tier_id = getattr(organization, "subscription_tier_id", None)
            tiers = SubscriptionTier.query.filter_by(is_customer_facing=True).all()
            upgrade_tiers = []
            for tier in tiers:
                if current_tier_id and tier.id == current_tier_id:
                    continue
                if not (tier.has_valid_integration or tier.is_billing_exempt):
                    continue
                if any(p.name == permission_name and p.is_active for p in tier.permissions):
                    upgrade_tiers.append(tier)
            upgrade_tiers.sort(key=lambda t: t.id)
            return upgrade_tiers
        except Exception as exc:
            logger.warning("Upgrade lookup failed for %s: %s", permission_name, exc)
            return []

    @staticmethod
    def get_live_pricing_data():
        """Get live pricing data from active billing providers only."""
        try:
            return BillingService.get_all_available_pricing()
        except Exception as exc:
            logger.warning("Could not fetch live pricing: %s", exc)
            return {
                'tiers': [],
                'currency': 'USD',
                'billing_cycles': ['monthly', 'yearly'],
                'available': False,
                'error': 'Pricing unavailable - check billing provider configuration'
            }

    @staticmethod
    def get_comprehensive_pricing_data():
        """Get comprehensive pricing data with tier information."""
        try:
            tiers = SubscriptionTier.query.filter_by(is_customer_facing=True).all()
            pricing_data = {'tiers': {}, 'available': True}

            for tier in tiers:
                key = str(tier.id)
                if tier.is_billing_exempt:
                    pricing_data['tiers'][key] = {
                        'name': tier.name,
                        'description': getattr(tier, 'description', ''),
                        'price': 'Free',
                        'billing_cycle': 'exempt',
                        'available': True,
                        'provider': 'exempt',
                        'features': [p.name for p in getattr(tier, 'permissions', [])]
                    }
                elif tier.billing_provider == 'stripe':
                    live_pricing = BillingService.get_live_pricing_for_tier(tier)
                    pricing_data['tiers'][key] = {
                        'name': tier.name,
                        'description': getattr(tier, 'description', ''),
                        'price': live_pricing['formatted_price'] if live_pricing else 'N/A',
                        'billing_cycle': live_pricing['billing_cycle'] if live_pricing else 'monthly',
                        'available': live_pricing is not None,
                        'provider': 'stripe',
                        'features': [p.name for p in getattr(tier, 'permissions', [])]
                    }
                elif tier.billing_provider == 'whop':
                    pricing_data['tiers'][key] = {
                        'name': tier.name,
                        'description': getattr(tier, 'description', ''),
                        'price': 'Contact Sales',
                        'billing_cycle': 'monthly',
                        'available': False,
                        'provider': 'whop',
                        'features': [p.name for p in getattr(tier, 'permissions', [])]
                    }

            return pricing_data

        except Exception as exc:
            logger.error("Error getting comprehensive pricing: %s", exc)
            return {'tiers': {}, 'available': False, 'error': str(exc)}

    @staticmethod
    def create_checkout_session(
        tier_key,
        user_email,
        user_name,
        success_url,
        cancel_url,
        metadata=None,
        existing_customer_id=None,
    ):
        """Create checkout session with appropriate provider. tier_key is a tier ID string."""
        try:
            tier_id = int(tier_key)
        except (TypeError, ValueError):
            tier_id = None
        tier = db.session.get(SubscriptionTier, tier_id) if tier_id is not None else None
        if not tier:
            logger.error("Tier %s not found", tier_key)
            return None

        if tier.is_billing_exempt:
            logger.warning("Cannot create checkout for exempt tier %s", tier_key)
            return None

        if tier.billing_provider == 'stripe':
            return BillingService.create_checkout_session_for_tier(
                tier,
                customer_email=user_email,
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata,
                client_reference_id=None,
                phone_required=True,
                allow_promo=True,
                existing_customer_id=existing_customer_id,
            )

        logger.warning("Billing provider %s not implemented", tier.billing_provider)
        return None

    @staticmethod
    def handle_webhook_event(provider, event_data):
        """Route webhook payloads to the correct billing provider."""
        if provider == 'stripe':
            return BillingService._handle_stripe_webhook(event_data or {})
        if provider == 'whop':
            logger.warning("Whop webhook handling not yet implemented")
            return 200
        logger.error("Unknown webhook provider: %s", provider)
        return 400

    @staticmethod
    def validate_tier_access(organization):
        """Validate that organization has valid tier access."""
        if not organization:
            return False, "no_organization"

        if isinstance(organization, Mapping):
            billing_status = organization.get('billing_status') or 'active'
            is_active = organization.get('is_active', True)
            is_exempt = organization.get('is_billing_exempt', False)
            subscription_tier_id = organization.get('subscription_tier_id')
        else:
            billing_status = getattr(organization, 'billing_status', 'active') or 'active'
            is_active = getattr(organization, 'is_active', True)
            tier_obj = getattr(organization, 'subscription_tier_obj', None)
            is_exempt = tier_obj.is_billing_exempt if tier_obj else False
            subscription_tier_id = getattr(organization, 'subscription_tier_id', None)

        if not is_active:
            return False, "organization_suspended"

        if not subscription_tier_id:
            return False, "no_tier_assigned"

        if is_exempt:
            return True, "exempt_tier"

        billing_status = billing_status.lower()
        if billing_status == 'active':
            return True, "billing_active"
        if billing_status in ['payment_failed', 'past_due']:
            return False, "payment_required"
        if billing_status in ['canceled', 'cancelled']:
            return False, "subscription_canceled"
        if billing_status == 'suspended':
            return False, "organization_suspended"

        return True, "tier_valid"

    # ------------------------------------------------------------------ #
    # Stripe primitives (single-source of truth)                         #
    # ------------------------------------------------------------------ #

    @staticmethod
    def construct_event(payload: bytes, sig_header: str, webhook_secret: str):
        """Construct Stripe event from webhook payload."""
        return stripe.Webhook.construct_event(payload, sig_header, webhook_secret)

    @staticmethod
    def ensure_stripe():
        """Ensure Stripe API keys are configured and loaded."""
        stripe_secret = BillingService._fetch_stripe_secret()
        if not stripe_secret:
            logger.warning("Stripe secret key not configured")
            return False
        stripe.api_key = stripe_secret
        return True

    @staticmethod
    def _fetch_stripe_secret():
        secret = None
        try:
            secret = current_app.config.get('STRIPE_SECRET_KEY')
        except Exception:
            secret = None
        return secret or os.environ.get('STRIPE_SECRET_KEY')

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
    def _handle_stripe_webhook(event: dict) -> int:
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
                BillingService._handle_checkout_completed(event)
            elif event_type == "customer.subscription.created":
                BillingService._handle_subscription_created(event)
            elif event_type == "customer.subscription.updated":
                BillingService._handle_subscription_updated(event)
            elif event_type == "customer.subscription.deleted":
                BillingService._handle_subscription_deleted(event)
            elif event_type == "invoice.payment_succeeded":
                BillingService._handle_payment_succeeded(event)
            elif event_type == "invoice.payment_failed":
                BillingService._handle_payment_failed(event)
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
            if not BillingService.ensure_stripe():
                return
            import stripe
            checkout = stripe.checkout.Session.retrieve(
                session_id,
                expand=['customer', 'customer_details', 'line_items.data.price']
            )
            provisioned = BillingService._provision_checkout_session(checkout)
            if not provisioned:
                BillingService._apply_batchbot_refill_checkout(checkout)
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
                if BillingService.ensure_stripe():
                    try:
                        cust = stripe.Customer.retrieve(customer_id)
                        org_id_meta = (cust.metadata or {}).get('organization_id')
                        if org_id_meta:
                            org = db.session.get(Organization, int(org_id_meta))
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
                if BillingService.ensure_stripe():
                    try:
                        cust = stripe.Customer.retrieve(customer_id)
                        org_id_meta = (cust.metadata or {}).get('organization_id')
                        if org_id_meta:
                            org = db.session.get(Organization, int(org_id_meta))
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
                if BillingService.ensure_stripe():
                    try:
                        cust = stripe.Customer.retrieve(customer_id)
                        org_id_meta = (cust.metadata or {}).get('organization_id')
                        if org_id_meta:
                            org = db.session.get(Organization, int(org_id_meta))
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
    def get_live_pricing_for_tier(tier_obj):
        """Get live pricing from Stripe for a subscription tier"""
        lookup_key = getattr(tier_obj, 'stripe_lookup_key', None)
        if not lookup_key:
            return None

        cache_key = BillingService._pricing_cache_key(lookup_key)
        cached = app_cache.get(cache_key)
        if cached:
            return cached

        lock = BillingService._get_pricing_lock(lookup_key)
        with lock:
            # Another thread may have populated while we were waiting
            cached = app_cache.get(cache_key)
            if cached:
                return cached

            if not BillingService.ensure_stripe():
                return None

            price_obj = None
            try:
                price_obj, resolution_strategy = BillingService._resolve_price_for_lookup_key(lookup_key)

                if not price_obj:
                    logger.warning(
                        "No active Stripe price found for lookup key %s; ensure the price exists and is active",
                        lookup_key,
                    )
                    app_cache.set(cache_key, None, ttl=BillingService._pricing_error_cache_ttl_seconds)
                    return None

                amount = price_obj.unit_amount / 100
                currency = price_obj.currency.upper()

                billing_cycle = 'one-time'
                if price_obj.recurring:
                    billing_cycle = 'yearly' if price_obj.recurring.interval == 'year' else 'monthly'

                if resolution_strategy != 'lookup_key':
                    logger.info(
                        "Resolved Stripe price %s for lookup key %s using %s fallback",
                        price_obj.id,
                        lookup_key,
                        resolution_strategy,
                    )

                data = {
                    'price_id': price_obj.id,
                    'amount': amount,
                    'formatted_price': f'${amount:.0f}',
                    'currency': currency,
                    'billing_cycle': billing_cycle,
                    'lookup_key': lookup_key,
                    'last_synced': datetime.now(timezone.utc).isoformat()
                }
                app_cache.set(cache_key, data, ttl=BillingService._pricing_cache_ttl_seconds)
                return data

            except StripeError as e:
                logger.error(f"Stripe error fetching price for {lookup_key}: {e}")
                app_cache.set(cache_key, None, ttl=BillingService._pricing_error_cache_ttl_seconds)
                return None

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

        except StripeError:
            # Propagate to caller for centralized logging/handling
            raise

    @staticmethod
    def create_checkout_session_for_tier(
        tier_obj,
        *,
        customer_email: str | None,
        success_url: str,
        cancel_url: str,
        metadata: dict | None = None,
        client_reference_id: str | None = None,
        phone_required: bool = True,
        allow_promo: bool = True,
        existing_customer_id: str | None = None,
    ):
        """Create checkout session using tier's lookup key with minimal required inputs."""
        if not BillingService.ensure_stripe():
            return None

        # Get live pricing first
        pricing = BillingService.get_live_pricing_for_tier(tier_obj)
        if not pricing:
            logger.error(f"No pricing found for tier {tier_obj.name} (ID: {tier_obj.id})")
            return None

        try:
            session_params = {
                'mode': 'subscription',
                'payment_method_types': ['card'],
                'line_items': [{
                    'price': pricing['price_id'],
                    'quantity': 1,
                }],
                'success_url': success_url,
                'cancel_url': cancel_url,
                'client_reference_id': client_reference_id,
                'billing_address_collection': 'auto',
                'phone_number_collection': {'enabled': phone_required},
                'allow_promotion_codes': allow_promo,
                'metadata': {
                    'tier_id': str(tier_obj.id),
                    'tier_name': tier_obj.name,
                    'lookup_key': tier_obj.stripe_lookup_key,
                    **(metadata or {})
                },
                'custom_fields': [
                    {
                        'key': 'workspace_name',
                        'label': {'type': 'custom', 'custom': 'Workspace / brand name'},
                        'type': 'text',
                        'text': {'minimum_length': 2, 'maximum_length': 60},
                    },
                    {
                        'key': 'first_name',
                        'label': {'type': 'custom', 'custom': 'First name'},
                        'type': 'text',
                        'text': {'minimum_length': 1, 'maximum_length': 40},
                    },
                    {
                        'key': 'last_name',
                        'label': {'type': 'custom', 'custom': 'Last name'},
                        'type': 'text',
                        'text': {'minimum_length': 1, 'maximum_length': 60},
                    },
                ],
            }

            if session_params.get('mode') == 'payment':
                session_params['customer_creation'] = 'always'

            if existing_customer_id:
                session_params['customer'] = existing_customer_id
                session_params['customer_update'] = {'name': 'auto', 'address': 'auto'}
            elif customer_email:
                session_params['customer_email'] = customer_email

            session = stripe.checkout.Session.create(**session_params)

            logger.info(
                "Created checkout session %s for tier %s (%s) with price %s",
                session.id,
                tier_obj.name,
                tier_obj.id,
                pricing['price_id'],
            )
            return session

        except StripeError as e:
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
        if not BillingService.ensure_stripe():
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

        except StripeError as e:
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

            organization = db.session.get(Organization, organization_id)
            if not organization:
                logger.error(f"Organization {organization_id} not found")
                return False

            # Get tier from subscription metadata
            tier_id = subscription.get('metadata', {}).get('tier_id')
            if tier_id:
                try:
                    tier = db.session.get(SubscriptionTier, int(tier_id))
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
        if not BillingService.ensure_stripe():
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

        except StripeError as e:
            logger.error(f"Failed to create portal session: {e}")
            return None

    @staticmethod
    def cancel_subscription(stripe_customer_id: str) -> bool:
        """Cancel all active subscriptions for a given Stripe customer."""
        if not stripe_customer_id:
            return False
        if not BillingService.ensure_stripe():
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
            pricing = BillingService.get_live_pricing_for_tier(tier)

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
        if not BillingService.ensure_stripe():
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
        if not BillingService.ensure_stripe():
            return None
        import stripe
        checkout = stripe.checkout.Session.retrieve(
            session_id,
            expand=['customer', 'customer_details', 'line_items.data.price']
        )
        return BillingService._provision_checkout_session(checkout)

    @staticmethod
    def _provision_checkout_session(checkout_session):
        """Internal helper shared by webhook + success URL to build accounts."""
        pending_id = BillingService._get_pending_signup_id_from_session(checkout_session)
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
                BillingService.update_customer_metadata(customer_obj.id, {
                    'organization_id': str(org.id),
                    'tier_id': str(org.subscription_tier_id or ''),
                })
            return org, user
        except Exception as exc:
            logger.error("Failed provisioning checkout session %s: %s", getattr(checkout_session, 'id', 'unknown'), exc)
            raise

    @staticmethod
    def _apply_batchbot_refill_checkout(checkout_session) -> bool:
        """Grant BatchBot credits when a standalone refill checkout completes."""
        try:
            metadata = getattr(checkout_session, 'metadata', {}) or {}
            lookup_key = metadata.get('batchbot_refill_lookup_key')
            if not lookup_key:
                line_items = getattr(checkout_session, 'line_items', {}) or {}
                data = line_items.get('data') or []
                if data:
                    price = data[0].get('price') or {}
                    lookup_key = price.get('id')
            if not lookup_key:
                return False

            from ..models import Organization
            from ..models.addon import Addon
            from ..models.batchbot_credit import BatchBotCreditBundle
            from .batchbot_credit_service import BatchBotCreditService

            org = None
            org_id = metadata.get('organization_id')
            if org_id:
                try:
                    org = db.session.get(Organization, int(org_id))
                except (TypeError, ValueError):
                    org = None

            customer_id = getattr(checkout_session, 'customer', None)
            if not org and customer_id:
                org = Organization.query.filter_by(stripe_customer_id=customer_id).first()
                if not org and BillingService.ensure_stripe():
                    import stripe
                    try:
                        cust = stripe.Customer.retrieve(customer_id)
                        org_meta = (cust.metadata or {}).get('organization_id')
                        if org_meta:
                            org = db.session.get(Organization, int(org_meta))
                    except Exception as exc:
                        logger.warning("Unable to resolve organization from Stripe customer %s: %s", customer_id, exc)
            if not org:
                logger.warning("BatchBot refill checkout %s missing organization context", getattr(checkout_session, 'id', 'unknown'))
                return False

            addon = Addon.query.filter_by(stripe_lookup_key=lookup_key).first()
            if not addon or not getattr(addon, 'batchbot_credit_amount', 0):
                logger.warning("BatchBot refill checkout %s referenced unknown addon %s", getattr(checkout_session, 'id', 'unknown'), lookup_key)
                return False

            reference = f"checkout:{getattr(checkout_session, 'id', 'unknown')}"
            existing = BatchBotCreditBundle.query.filter_by(reference=reference).first()
            if existing:
                return True

            bundle = BatchBotCreditService.grant_from_addon(org, addon, reference=reference)
            if bundle:
                logger.info(
                    "Granted %s BatchBot requests to org %s via checkout %s",
                    bundle.purchased_requests,
                    org.id,
                    reference,
                )
                return True
            return False
        except Exception as exc:
            logger.error("Failed to apply BatchBot refill for checkout %s: %s", getattr(checkout_session, 'id', 'unknown'), exc)
            return False

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
        if not BillingService.ensure_stripe():
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
        return BillingService._create_checkout_session_by_lookup_key(
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
        return BillingService._create_checkout_session_by_lookup_key(
            lookup_key,
            customer_email,
            success_url,
            cancel_url,
            metadata=metadata,
            mode='subscription'
        )