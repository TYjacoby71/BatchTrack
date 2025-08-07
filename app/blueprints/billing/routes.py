import logging
import stripe
import os
import json
from datetime import datetime, timedelta
from flask import Blueprint, request, render_template, flash, redirect, url_for, session, jsonify, current_app
from flask_login import login_required, current_user
from ...services.billing_service import BillingService
from ...services.stripe_service import StripeService
from ...services.whop_service import WhopService
from ...services.signup_service import SignupService
from ...models.models import Organization, User
from ...models.subscription_tier import SubscriptionTier
from ...models.role import Role
from ...extensions import db
from ...utils.timezone_utils import TimezoneUtils

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
        pricing_data = BillingService.get_live_pricing_data()
        logger.info(f"Live pricing data retrieved for upgrade page: {len(pricing_data)} tiers")
    except Exception as e:
        logger.error(f"Error fetching live pricing: {e}")
        flash('Pricing information temporarily unavailable. Please try again later.', 'warning')
        pricing_data = {}

    return render_template('billing/upgrade.html',
                         organization=organization,
                         pricing_data=pricing_data)

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
        # For Stripe checkout
        if billing_cycle in ['month', 'year']:
            checkout_url = StripeService.create_checkout_session(
                organization, 
                tier, 
                billing_cycle,
                success_url=url_for('billing.complete_signup_from_stripe', _external=True),
                cancel_url=url_for('billing.upgrade', _external=True)
            )
            if checkout_url:
                return redirect(checkout_url)

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
        if not StripeService.initialize_stripe():
            logger.error("Failed to initialize Stripe")
            flash('Payment system error', 'error')
            return redirect(url_for('auth.signup'))

        # Retrieve checkout session
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        logger.info(f"Retrieved checkout session: {checkout_session.id}")

        # Get customer details
        customer = stripe.Customer.retrieve(checkout_session.customer)
        logger.info(f"Retrieved customer: {customer.id}")

        # Extract user info from checkout session
        customer_details = checkout_session.customer_details
        if not customer_details:
            logger.error("No customer details in checkout session")
            flash('Customer information not found', 'error')
            return redirect(url_for('auth.signup'))

        # Get tier from checkout metadata or session metadata
        tier = checkout_session.metadata.get('tier') or customer.metadata.get('tier')
        if not tier:
            logger.error("No tier found in checkout session or customer metadata")
            flash('Subscription tier not found', 'error')
            return redirect(url_for('auth.signup'))

        logger.info(f"Processing signup for tier: {tier}")

        # Get pending signup data from session (if available)
        pending_signup = session.get('pending_signup', {})
        oauth_user_info = pending_signup.get('oauth_user_info', {})

        # Build signup data from Stripe customer details and session data
        signup_data = {
            'email': customer_details.email or customer.email,
            'first_name': customer_details.name.split(' ')[0] if customer_details.name else oauth_user_info.get('first_name', ''),
            'last_name': ' '.join(customer_details.name.split(' ')[1:]) if customer_details.name and len(customer_details.name.split(' ')) > 1 else oauth_user_info.get('last_name', ''),
            'org_name': customer.metadata.get('org_name') or f"{customer_details.name}'s Company" if customer_details.name else "My Company",
            'username': customer.metadata.get('username') or customer_details.email.split('@')[0] if customer_details.email else oauth_user_info.get('email', '').split('@')[0],
            'signup_source': checkout_session.metadata.get('signup_source', 'stripe'),
            'promo_code': checkout_session.metadata.get('promo_code'),
            'referral_code': checkout_session.metadata.get('referral_code'),
            'oauth_provider': oauth_user_info.get('oauth_provider'),
            'oauth_provider_id': oauth_user_info.get('oauth_provider_id'),
            'email_verified': bool(oauth_user_info.get('email_verified', False))
        }

        logger.info(f"Built signup data: {signup_data}")

        # Create the organization and user
        from ...models.subscription_tier import SubscriptionTier
        from ...models.models import Organization, User
        from ...models.role import Role
        from flask_login import login_user

        # Get the subscription tier
        subscription_tier = SubscriptionTier.query.filter_by(key=tier).first()
        if not subscription_tier:
            logger.error(f"Subscription tier '{tier}' not found in database")
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

        # Send welcome email
        try:
            from ...services.email_service import EmailService
            EmailService.send_welcome_email(
                owner_user.email,
                owner_user.first_name,
                org.name,
                tier.title()
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
        logger.info(f"User {owner_user.username} logged in successfully")

        # Clear pending signup data
        session.pop('pending_signup', None)
        logger.info("Cleared pending signup data from session")

        flash(f'Welcome to BatchTrack! Your {tier.title()} account is ready to use.', 'success')
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
        portal_url = StripeService.create_customer_portal_session(organization.stripe_customer_id)
        if portal_url:
            return redirect(portal_url)
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
def stripe_webhook():
    """Handle Stripe webhooks"""
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    try:
        # Verify webhook signature
        endpoint_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')
        if not endpoint_secret:
            logger.error("Stripe webhook secret not configured")
            return jsonify({'error': 'Webhook secret not configured'}), 400

        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )

        logger.info(f"Received Stripe webhook: {event['type']}")

        # Handle different event types
        if event['type'] == 'checkout.session.completed':
            return handle_checkout_completed(event)
        elif event['type'] == 'customer.created':
            # Customer created - check if this is from a signup checkout
            return handle_customer_created(event)
        elif event['type'] in ['customer.subscription.created', 'customer.subscription.updated']:
            return handle_subscription_change(event)
        elif event['type'] == 'customer.subscription.deleted':
            return handle_subscription_deleted(event)
        else:
            logger.info(f"Unhandled webhook event type: {event['type']}")
            return jsonify({'status': 'unhandled'}), 200

    except ValueError as e:
        logger.error(f"Invalid payload: {e}")
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature: {e}")
        return jsonify({'error': 'Invalid signature'}), 400
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'error': 'Webhook processing failed'}), 500

def handle_checkout_completed(event):
    """Handle successful checkout completion"""
    try:
        checkout_session = event['data']['object']
        session_id = checkout_session['id']

        logger.info(f"Processing checkout completion for session: {session_id}")

        # Extract metadata from checkout session
        metadata = checkout_session.get('metadata', {})
        tier_key = metadata.get('tier_key')

        if not tier_key:
            logger.error(f"No tier_key in checkout session metadata: {session_id}")
            return jsonify({'error': 'Missing tier information'}), 400

        # Get customer information
        customer_id = checkout_session.get('customer')
        if not customer_id:
            logger.error(f"No customer ID in checkout session: {session_id}")
            return jsonify({'error': 'Missing customer information'}), 400

        # Complete signup using the checkout session
        success = complete_signup_from_checkout_session(checkout_session)

        if success:
            logger.info(f"Successfully completed signup from checkout session: {session_id}")
            return jsonify({'status': 'success'}), 200
        else:
            logger.error(f"Failed to complete signup from checkout session: {session_id}")
            return jsonify({'error': 'Signup completion failed'}), 500

    except Exception as e:
        logger.error(f"Error handling checkout completion: {e}")
        return jsonify({'error': 'Processing failed'}), 500

def handle_customer_created(event):
    """Handle customer.created webhook - may be part of signup flow"""
    try:
        customer = event['data']['object']
        customer_id = customer['id']

        logger.info(f"Processing customer.created for: {customer_id}")

        # Check if this customer has signup-related metadata
        metadata = customer.get('metadata', {})

        if 'tier' in metadata or 'signup_source' in metadata:
            # This appears to be a signup customer - process the signup
            tier_key = metadata.get('tier')
            if not tier_key:
                logger.warning(f"Customer {customer_id} has signup metadata but no tier")
                return jsonify({'status': 'no_tier'}), 200

            # Build signup data from customer information and metadata
            signup_data = {
                'org_name': customer['name'] or f"{customer['email']} Organization",
                'email': customer['email'],
                'first_name': metadata.get('first_name', customer['name'].split(' ')[0] if customer['name'] else ''),
                'last_name': metadata.get('last_name', ' '.join(customer['name'].split(' ')[1:]) if customer['name'] and ' ' in customer['name'] else ''),
                'username': metadata.get('username', customer['email'].split('@')[0]),
                'signup_source': metadata.get('signup_source', 'stripe'),
                'promo_code': metadata.get('promo_code'),
                'referral_code': metadata.get('referral_code'),
                'oauth_provider': metadata.get('oauth_provider'),
                'oauth_provider_id': metadata.get('oauth_provider_id'),
                'password_hash': metadata.get('password_hash', 'stripe_signup_pending')
            }

            # Complete the signup
            from ...services.signup_service import SignupService
            success = SignupService.complete_stripe_signup(signup_data, tier_key, customer_id)

            if success:
                logger.info(f"Successfully completed signup for customer: {customer_id}")
                return jsonify({'status': 'signup_completed'}), 200
            else:
                logger.error(f"Failed to complete signup for customer: {customer_id}")
                return jsonify({'error': 'Signup completion failed'}), 500
        else:
            # Regular customer creation, not a signup
            logger.info(f"Regular customer creation, not a signup: {customer_id}")
            return jsonify({'status': 'regular_customer'}), 200

    except Exception as e:
        logger.error(f"Error handling customer.created: {e}")
        return jsonify({'error': 'Processing failed'}), 500

def complete_signup_from_checkout_session(checkout_session):
    """Complete signup using checkout session data"""
    try:
        # Extract all necessary information from the checkout session
        metadata = checkout_session.get('metadata', {})
        customer_id = checkout_session.get('customer')

        # Get customer details
        customer = stripe.Customer.retrieve(customer_id)

        # Build comprehensive signup data
        signup_data = {
            'org_name': customer.name or f"{customer.email} Organization",
            'email': customer.email,
            'first_name': metadata.get('first_name', customer.name.split(' ')[0] if customer.name else ''),
            'last_name': metadata.get('last_name', ' '.join(customer.name.split(' ')[1:]) if customer.name and ' ' in customer.name else ''),
            'username': metadata.get('username', customer.email.split('@')[0]),
            'signup_source': metadata.get('signup_source', 'stripe'),
            'promo_code': metadata.get('promo_code'),
            'referral_code': metadata.get('referral_code'),
            'oauth_provider': metadata.get('oauth_provider'),
            'oauth_provider_id': metadata.get('oauth_provider_id'),
            'oauth_email': metadata.get('oauth_email'),
            'password_hash': metadata.get('password_hash', 'stripe_checkout_signup')
        }

        tier_key = metadata.get('tier_key') or metadata.get('tier')

        from ...services.signup_service import SignupService
        return SignupService.complete_stripe_signup(signup_data, tier_key, customer_id)

    except Exception as e:
        logger.error(f"Error completing signup from checkout session: {e}")
        return False


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
        'subscription_tier': organization.subscription_tier_obj.key if organization.subscription_tier_obj else None,
        'stripe_customer_id': organization.stripe_customer_id,
        'whop_license_key': organization.whop_license_key,
        'billing_status': getattr(organization, 'billing_status', 'unknown'),
        'last_online_sync': organization.last_online_sync.isoformat() if organization.last_online_sync else None,
        'offline_license_valid': BillingService.validate_offline_license(organization)[0] if organization.offline_tier_cache else False
    }

    return render_template('billing/debug.html', debug_info=debug_info)