
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
    """Complete signup process after Stripe payment - industry standard"""
    try:
        session_id = request.args.get('session_id')
        if not session_id:
            flash('Invalid checkout session', 'error')
            return redirect(url_for('auth.signup'))

        # Initialize Stripe
        if not StripeService.initialize_stripe():
            flash('Payment system error', 'error')
            return redirect(url_for('auth.signup'))
            
        # Retrieve checkout session
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        
        # Get customer with signup metadata
        customer = stripe.Customer.retrieve(checkout_session.customer)
        signup_data = customer.metadata
        
        if not signup_data.get('org_name'):
            flash('Signup data not found', 'error')
            return redirect(url_for('auth.signup'))
        
        # Get tier from checkout metadata
        tier = checkout_session.metadata.get('tier')
        if not tier:
            flash('Subscription tier not found', 'error')
            return redirect(url_for('auth.signup'))
        
        # Complete signup using retrieved data
        success = SignupService.complete_stripe_signup(signup_data, tier, customer.id)
        
        if success:
            flash('Welcome to BatchTrack! Your account is ready.', 'success')
            return redirect(url_for('app_routes.dashboard'))
        else:
            flash('Failed to complete account setup', 'error')
            return redirect(url_for('auth.signup'))
            
    except Exception as e:
        logger.error(f"Stripe signup completion error: {e}")
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
    try:
        payload = request.get_data(as_text=True)
        sig_header = request.headers.get('Stripe-Signature')
        
        event = StripeService.verify_webhook_signature(payload, sig_header)
        
        if event['type'] == 'checkout.session.completed':
            # Handle successful checkout
            session = event['data']['object']
            customer_id = session.get('customer')
            
            # Find organization by customer ID and update subscription
            organization = Organization.query.filter_by(stripe_customer_id=customer_id).first()
            if organization:
                # Update subscription status
                SignupService.activate_stripe_subscription(organization, session)
                
        elif event['type'] == 'invoice.payment_failed':
            # Handle failed payment
            invoice = event['data']['object']
            customer_id = invoice.get('customer')
            
            organization = Organization.query.filter_by(stripe_customer_id=customer_id).first()
            if organization:
                # Handle payment failure
                SignupService.handle_payment_failure(organization)

        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'error': 'Webhook failed'}), 400

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
