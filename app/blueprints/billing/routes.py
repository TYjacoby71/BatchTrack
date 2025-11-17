import logging
import os
import json
from datetime import datetime, timedelta
from flask import Blueprint, request, render_template, flash, redirect, url_for, session, jsonify, current_app
from flask_login import login_required, current_user
from ...services.billing_service import BillingService
from ...services.stripe_service import StripeService
from ...services.whop_service import WhopService
from ...services.signup_service import SignupService
from ...services.session_service import SessionService
from ...models.models import Organization, User
from ...models.subscription_tier import SubscriptionTier
from ...models.role import Role
from ...extensions import db
from ...utils.timezone_utils import TimezoneUtils
from ...extensions import csrf
from ...extensions import limiter

logger = logging.getLogger(__name__)

billing_bp = Blueprint('billing', __name__, url_prefix='/billing')

@billing_bp.route('/upgrade')
@login_required
def upgrade():
    """Display upgrade options with live pricing"""
    organization = current_user.organization
    if not organization:
        flash('No organization found', 'error')
        return redirect(url_for('app_routes.dashboard'))

    # Get live pricing data
    try:
        pricing_data = BillingService.get_comprehensive_pricing_data()
        logger.info(f"Live pricing data retrieved for upgrade page: {len(pricing_data.get('tiers', {}))} tiers")
    except Exception as e:
        logger.error(f"Error fetching live pricing: {e}")
        flash('Pricing information temporarily unavailable. Please try again later.', 'warning')
        pricing_data = {'tiers': {}, 'available': False}

    # Get current tier information
    current_tier = BillingService.get_tier_for_organization(organization)

    # Get subscription details (mock for now since we don't have Stripe integration active)
    subscription_details = {
        'status': 'active' if current_tier != 'exempt' else 'inactive',
        'next_billing_date': None,
        'amount': None,
        'interval': None,
        'trial_end': None,
        'cancel_at_period_end': False
    }

    # Build a minimal tiers map from DB for debug display (no JSON reads)
    from ...models.subscription_tier import SubscriptionTier
    try:
        db_tiers = SubscriptionTier.query.filter_by(is_customer_facing=True).all()
        tiers_config = {str(t.id): {
            'name': t.name,
            'is_available': t.has_valid_integration or t.is_billing_exempt,
            'billing_provider': t.billing_provider,
        } for t in db_tiers}
    except Exception as e:
        logger.error(f"Error loading tiers from DB: {e}")
        tiers_config = {}

    return render_template('billing/upgrade.html',
                         organization=organization,
                         pricing_data=pricing_data.get('tiers', {}),
                         tiers=tiers_config,
                         current_tier=current_tier,
                         subscription_details=subscription_details)

@billing_bp.route('/storage')
@login_required
def storage_addon():
    """Redirect to Stripe subscription checkout for storage add-on if configured on the tier."""
    organization = current_user.organization
    if not organization or not organization.subscription_tier:
        flash('No organization or tier found', 'error')
        return redirect(url_for('app_routes.dashboard'))

    tier = organization.subscription_tier
    # Enforce tier-allowed add-ons: storage key must be allowed on this tier
    try:
        from ...models.addon import Addon
        storage_addon = Addon.query.filter_by(key='storage', is_active=True).first()
    except Exception:
        storage_addon = None
    if not storage_addon or storage_addon not in getattr(tier, 'allowed_addons', []):
        flash('Storage add-on is not available for your tier. Please upgrade instead.', 'warning')
        return redirect(url_for('billing.upgrade'))

    lookup_key = storage_addon.stripe_lookup_key

    try:
        if not StripeService.initialize_stripe():
            flash('Billing temporarily unavailable', 'error')
            return redirect(url_for('billing.upgrade'))

        # Create a subscription checkout session for the storage add-on price lookup key
        session = StripeService.create_subscription_checkout_by_lookup_key(
            lookup_key,
            current_user.email,
            success_url=url_for('billing.upgrade', _external=True),
            cancel_url=url_for('billing.upgrade', _external=True),
            metadata={'addon': 'storage'}
        )
        if session and getattr(session, 'url', None):
            return redirect(session.url)
        flash('Unable to start storage checkout', 'error')
        return redirect(url_for('billing.upgrade'))
    except Exception as e:
        logger.error(f"Storage add-on checkout error: {e}")
        flash('Checkout failed. Please try again later.', 'error')
        return redirect(url_for('billing.upgrade'))

@billing_bp.route('/addons/start/<addon_key>', methods=['POST'])
@login_required
def start_addon_checkout(addon_key):
    """Start Stripe checkout for a specific add-on by key (uses addon.stripe_lookup_key).
    Enforces that the add-on is allowed for the organization's current tier.
    """
    from ...models.addon import Addon
    from ...services.stripe_service import StripeService
    addon = Addon.query.filter_by(key=addon_key, is_active=True).first()
    if not addon or not addon.stripe_lookup_key:
        flash('Add-on not available.', 'warning')
        return redirect(url_for('settings.index') + '#billing')

    organization = current_user.organization
    tier = getattr(organization, 'subscription_tier_obj', None)
    # Enforce allowed vs included semantics
    if not tier:
        flash('No subscription tier found for your organization.', 'warning')
        return redirect(url_for('settings.index') + '#billing')
    included = set(getattr(tier, 'included_addons', []) or [])
    allowed = set(getattr(tier, 'allowed_addons', []) or [])
    if addon in included:
        flash('This add-on is already included in your tier.', 'info')
        return redirect(url_for('settings.index') + '#billing')
    if addon not in allowed:
        flash('This add-on is not available for your current tier.', 'warning')
        return redirect(url_for('billing.upgrade'))

    try:
        if not StripeService.initialize_stripe():
            flash('Billing temporarily unavailable', 'error')
            return redirect(url_for('settings.index') + '#billing')
        session = StripeService.create_subscription_checkout_by_lookup_key(
            addon.stripe_lookup_key,
            current_user.email,
            success_url=url_for('settings.index', _external=True) + '#billing',
            cancel_url=url_for('settings.index', _external=True) + '#billing',
            metadata={'addon': addon.function_key if hasattr(addon, 'function_key') else addon.name}
        )
        if session and getattr(session, 'url', None):
            return redirect(session.url)
        flash('Unable to start checkout', 'error')
    except Exception as e:
        logger.error(f"Addon checkout error ({addon_key}): {e}")
        flash('Checkout failed. Please try again later.', 'error')
    return redirect(url_for('settings.index') + '#billing')

@billing_bp.route('/checkout/<tier>')
@billing_bp.route('/checkout/<tier>/<billing_cycle>')
@login_required
def checkout(tier, billing_cycle='month'):
    """Initiate checkout process"""
    organization = current_user.organization
    if not organization:
        flash('No organization found', 'error')
        return redirect(url_for('billing.upgrade'))

    try:
        # Use unified billing service for checkout
        checkout_session = BillingService.create_checkout_session(
            tier,
            current_user.email,
            f"{current_user.first_name} {current_user.last_name}",
            url_for('billing.complete_signup_from_stripe', _external=True),
            url_for('billing.upgrade', _external=True),
            metadata={'tier': tier, 'billing_cycle': billing_cycle}
        )
        
        if checkout_session:
            return redirect(checkout_session.url)

        flash('Checkout not available for this tier', 'error')
        return redirect(url_for('billing.upgrade'))

    except Exception as e:
        logger.error(f"Checkout error: {e}")
        flash('Checkout failed. Please try again.', 'error')
        return redirect(url_for('billing.upgrade'))

@billing_bp.route('/whop-checkout/<product_id>')
@login_required
def whop_checkout(product_id):
    """Redirect to Whop checkout"""
    organization = current_user.organization
    if not organization:
        flash('No organization found', 'error')
        return redirect(url_for('billing.upgrade'))

    try:
        checkout_url = WhopService.create_checkout_session(
            product_id,
            current_user.email,
            success_url=url_for('billing.complete_signup_from_whop', _external=True)
        )
        if checkout_url:
            return redirect(checkout_url)

        flash('Whop checkout not available', 'error')
        return redirect(url_for('billing.upgrade'))

    except Exception as e:
        logger.error(f"Whop checkout error: {e}")
        flash('Checkout failed. Please try again.', 'error')
        return redirect(url_for('billing.upgrade'))

@billing_bp.route('/complete-signup-from-stripe')
def complete_signup_from_stripe():
    """Complete signup process after Stripe payment"""
    try:
        session_id = request.args.get('session_id')
        if not session_id:
            logger.error("No session_id provided")
            flash('Invalid checkout session', 'error')
            return redirect(url_for('auth.signup'))

        logger.info(f"Processing Stripe signup completion for session: {session_id}")

        # Initialize Stripe
        if not StripeService.initialize():
            logger.error("Failed to initialize Stripe")
            flash('Payment system error', 'error')
            return redirect(url_for('auth.signup'))

        # Retrieve checkout session
        checkout_session = StripeService.get_checkout_session(session_id)
        if not checkout_session:
            logger.error("Failed to retrieve checkout session")
            flash('Checkout session not found', 'error')
            return redirect(url_for('auth.signup'))

        logger.info(f"Retrieved checkout session: {checkout_session.id}")

        # Get customer details
        customer = StripeService.get_customer(checkout_session.customer)
        if not customer:
            logger.error("Failed to retrieve customer")
            flash('Customer information not found', 'error')
            return redirect(url_for('auth.signup'))

        logger.info(f"Retrieved customer: {customer.id}")

        # Extract user info from checkout session
        customer_details = checkout_session.customer_details
        if not customer_details:
            logger.error("No customer details in checkout session")
            flash('Customer information not found', 'error')
            return redirect(url_for('auth.signup'))

        # Get tier from checkout metadata or session metadata
        tier_identifier = (
            checkout_session.metadata.get('tier_id')
            or checkout_session.metadata.get('tier')
            or customer.metadata.get('tier_id')
            or customer.metadata.get('tier')
            or checkout_session.metadata.get('lookup_key')
            or customer.metadata.get('lookup_key')
        )
        if not tier_identifier:
            logger.error("No tier found in checkout session or customer metadata")
            flash('Subscription tier not found', 'error')
            return redirect(url_for('auth.signup'))

        logger.info(f"Processing signup for tier identifier: {tier_identifier}")

        # Get pending signup data from session (if available)
        pending_signup = session.get('pending_signup', {})
        oauth_user_info = pending_signup.get('oauth_user_info', {})

        # Build signup data from Stripe customer details and session data
        signup_data = {
            'email': customer_details.email or customer.email,
            'first_name': customer_details.name.split(' ')[0] if customer_details.name else oauth_user_info.get('first_name', ''),
            'last_name': ' '.join(customer_details.name.split(' ')[1:]) if customer_details.name and len(customer_details.name.split(' ')) > 1 else oauth_user_info.get('last_name', ''),
            'org_name': customer.metadata.get('org_name') or f"{customer_details.name}'s Company" if customer_details.name else "My Company",
            'username': customer.metadata.get('username') or customer_details.email.split('@')[0] if customer.email else oauth_user_info.get('email', '').split('@')[0],
            'signup_source': checkout_session.metadata.get('signup_source', 'stripe'),
            'promo_code': checkout_session.metadata.get('promo_code'),
            'referral_code': checkout_session.metadata.get('referral_code'),
            'oauth_provider': oauth_user_info.get('oauth_provider'),
            'oauth_provider_id': oauth_user_info.get('oauth_provider_id'),
            'email_verified': bool(oauth_user_info.get('email_verified', False)),
            'detected_timezone': checkout_session.metadata.get('detected_timezone', 'UTC')  # Auto-detected timezone
        }

        logger.info(f"Built signup data: {signup_data}")

        # Create the organization and user
        from ...models.subscription_tier import SubscriptionTier
        from ...models.models import Organization, User
        from ...models.role import Role
        from flask_login import login_user

        # Get the subscription tier
        subscription_tier = SubscriptionTier.find_by_identifier(tier_identifier)
        if not subscription_tier:
            logger.error(f"Subscription tier '{tier_identifier}' not found in database")
            flash('Invalid subscription plan', 'error')
            return redirect(url_for('auth.signup'))

        # Create organization
        org = Organization(
            name=signup_data['org_name'],
            contact_email=signup_data['email'],
            is_active=True,
            signup_source=signup_data['signup_source'],
            promo_code=signup_data.get('promo_code'),
            referral_code=signup_data.get('referral_code'),
            subscription_tier_id=subscription_tier.id,
            stripe_customer_id=customer.id
        )
        db.session.add(org)
        db.session.flush()  # Get the ID
        logger.info(f"Created organization with ID: {org.id}")

        # Create organization owner user
        owner_user = User(
            username=signup_data['username'],
            email=signup_data['email'],
            first_name=signup_data['first_name'],
            last_name=signup_data['last_name'],
            organization_id=org.id,
            user_type='customer',
            is_organization_owner=True,
            is_active=True,
            email_verified=signup_data.get('email_verified', True),  # Stripe emails are verified
            oauth_provider=signup_data.get('oauth_provider'),
            oauth_provider_id=signup_data.get('oauth_provider_id')
        )

        # Set a temporary password for non-OAuth users (they can reset it later)
        if not signup_data.get('oauth_provider'):
            import secrets
            temp_password = secrets.token_urlsafe(16)
            owner_user.set_password(temp_password)

            # Send password setup email
            from ...services.email_service import EmailService
            owner_user.password_reset_token = EmailService.generate_verification_token(owner_user.email)
            owner_user.password_reset_sent_at = TimezoneUtils.utc_now()

        db.session.add(owner_user)
        db.session.flush()
        logger.info(f"Created user with ID: {owner_user.id}")

        # Assign organization owner role
        org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
        if org_owner_role:
            owner_user.assign_role(org_owner_role)
            logger.info("Assigned organization_owner role")

        # Commit all changes
        db.session.commit()
        logger.info("Database changes committed successfully")

        # Update Stripe customer metadata with organization_id and tier_key
        try:
            from ...services.stripe_service import StripeService
            StripeService.update_customer_metadata(customer.id, {
                'organization_id': str(org.id),
                'tier_id': str(subscription_tier.id)
            })
        except Exception as meta_error:
            logger.warning(f"Failed to update Stripe customer metadata: {meta_error}")

        # Send welcome email
        try:
            from ...services.email_service import EmailService
            EmailService.send_welcome_email(
                owner_user.email,
                owner_user.first_name,
                org.name,
                subscription_tier.name
            )

            if not signup_data.get('oauth_provider'):
                # Send password setup email for non-OAuth users
                EmailService.send_password_setup_email(
                    owner_user.email,
                    owner_user.password_reset_token,
                    owner_user.first_name
                )
        except Exception as email_error:
            logger.warning(f"Failed to send welcome email: {email_error}")

        # Log in the user
        login_user(owner_user)
        SessionService.rotate_user_session(owner_user)
        owner_user.last_login = TimezoneUtils.utc_now()
        db.session.commit()
        logger.info(f"User {owner_user.username} logged in successfully")

        # Clear pending signup data
        session.pop('pending_signup', None)
        logger.info("Cleared pending signup data from session")

        flash(f'Welcome to BatchTrack! Your {subscription_tier.name} account is ready to use.', 'success')
        return redirect(url_for('app_routes.dashboard'))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Stripe signup completion error: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        flash('Account setup failed. Please contact support.', 'error')
        return redirect(url_for('auth.signup'))

@billing_bp.route('/complete-signup-from-whop')
@login_required
def complete_signup_from_whop():
    """Complete signup process after Whop payment"""
    try:
        license_key = request.args.get('license_key')
        if not license_key:
            flash('No license key provided', 'error')
            return redirect(url_for('billing.upgrade'))

        # Complete signup using Whop license
        success = SignupService.complete_whop_signup(current_user.organization, license_key)

        if success:
            flash('Subscription activated successfully!', 'success')
            return redirect(url_for('app_routes.dashboard'))
        else:
            flash('Failed to activate subscription', 'error')
            return redirect(url_for('billing.upgrade'))

    except Exception as e:
        logger.error(f"Whop signup completion error: {e}")
        flash('Signup completion failed', 'error')
        return redirect(url_for('billing.upgrade'))

@billing_bp.route('/customer-portal')
@login_required
def customer_portal():
    """Redirect to Stripe customer portal"""
    organization = current_user.organization
    if not organization or not organization.stripe_customer_id:
        flash('No billing account found', 'error')
        return redirect(url_for('app_routes.dashboard'))

    try:
        portal_session = StripeService.create_customer_portal_session(
            organization, 
            url_for('app_routes.dashboard', _external=True)
        )
        if portal_session:
            return redirect(portal_session.url)
        else:
            flash('Unable to access billing portal', 'error')
            return redirect(url_for('app_routes.dashboard'))

    except Exception as e:
        logger.error(f"Customer portal error: {e}")
        flash('Billing portal unavailable', 'error')
        return redirect(url_for('app_routes.dashboard'))

@billing_bp.route('/cancel-subscription', methods=['POST'])
@login_required
def cancel_subscription():
    """Cancel current subscription"""
    organization = current_user.organization
    if not organization:
        flash('No organization found', 'error')
        return redirect(url_for('app_routes.dashboard'))

    try:
        if organization.stripe_customer_id:
            success = StripeService.cancel_subscription(organization.stripe_customer_id)
        elif organization.whop_license_key:
            success = WhopService.cancel_subscription(organization.whop_license_key)
        else:
            flash('No active subscription found', 'error')
            return redirect(url_for('app_routes.dashboard'))

        if success:
            flash('Subscription cancelled successfully', 'success')
        else:
            flash('Failed to cancel subscription', 'error')

    except Exception as e:
        logger.error(f"Subscription cancellation error: {e}")
        flash('Cancellation failed', 'error')

    return redirect(url_for('app_routes.dashboard'))

@billing_bp.route('/webhooks/stripe', methods=['POST'])
@csrf.exempt
@limiter.limit("60/minute")
def stripe_webhook():
    """Handle Stripe webhooks"""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature', '')
    webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')

    if not webhook_secret:
        logger.error("Stripe webhook secret not configured")
        return '', 500

    try:
        event = StripeService.construct_event(payload, sig_header, webhook_secret)
        logger.info(f"Received Stripe webhook: {event['type']}")

        status = BillingService.handle_webhook_event('stripe', event)
        return '', status

    except ValueError as e:
        logger.error(f"Invalid payload: {str(e)}")
        return '', 400
    except Exception as e:
        logger.error(f"Webhook signature verification failed: {str(e)}")
        return '', 400




def handle_subscription_change(event):
    """Handle subscription creation or update"""
    try:
        subscription = event['data']['object']
        customer_id = subscription.get('customer')
        status = subscription.get('status')

        organization = Organization.query.filter_by(stripe_customer_id=customer_id).first()
        if not organization:
            logger.warning(f"Organization not found for customer ID: {customer_id}")
            return jsonify({'error': 'Organization not found'}), 404

        # Update subscription status
        if status in ['active', 'trialing']:
            organization.subscription_status = status
            organization.billing_status = 'active'
        elif status == 'past_due':
            organization.subscription_status = status
            organization.billing_status = 'past_due'
        elif status == 'canceled':
            organization.subscription_status = status
            organization.billing_status = 'cancelled'

        db.session.commit()
        logger.info(f"Updated organization {organization.id} subscription status to {status}")

        return jsonify({'status': 'success'}), 200

    except Exception as e:
        logger.error(f"Error handling subscription change: {e}")
        return jsonify({'error': 'Processing failed'}), 500

def handle_subscription_deleted(event):
    """Handle subscription deletion"""
    try:
        subscription = event['data']['object']
        customer_id = subscription.get('customer')

        organization = Organization.query.filter_by(stripe_customer_id=customer_id).first()
        if not organization:
            logger.warning(f"Organization not found for customer ID: {customer_id}")
            return jsonify({'error': 'Organization not found'}), 404

        organization.subscription_status = 'cancelled'
        organization.billing_status = 'cancelled'
        db.session.commit()
        logger.info(f"Updated organization {organization.id} subscription status to cancelled")

        return jsonify({'status': 'success'}), 200

    except Exception as e:
        logger.error(f"Error handling subscription deletion: {e}")
        return jsonify({'error': 'Processing failed'}), 500

@billing_bp.route('/debug')
@login_required
def debug_billing():
    """Debug billing information"""
    if not current_user.is_developer:
        flash('Access denied', 'error')
        return redirect(url_for('app_routes.dashboard'))

    organization = current_user.organization
    if not organization:
        flash('No organization found', 'error')
        return redirect(url_for('app_routes.dashboard'))

    debug_info = {
        'organization_id': organization.id,
        'subscription_tier': str(organization.subscription_tier_obj.id) if organization.subscription_tier_obj else None,
        'stripe_customer_id': organization.stripe_customer_id,
        'whop_license_key': organization.whop_license_key,
        'billing_status': getattr(organization, 'billing_status', 'unknown'),
        'last_online_sync': organization.last_online_sync.isoformat() if organization.last_online_sync else None
    }

    return render_template('billing/debug.html', debug_info=debug_info)