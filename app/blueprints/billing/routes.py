from flask import render_template, request, jsonify, redirect, url_for, flash, current_app, session
from flask_login import login_required, current_user
from . import billing_bp
from ...extensions import csrf
import logging
import stripe

logger = logging.getLogger(__name__)

# Consolidated Billing Service and its related methods will be used throughout.
# The ResilientBillingService is now deprecated and replaced by BillingService.

# Billing access control middleware
@billing_bp.before_request
def check_billing_access():
    """Ensure organization has valid billing status for system access"""
    # Skip billing checks for billing routes themselves and webhooks
    if request.endpoint and (
        request.endpoint.startswith('billing.') or
        request.endpoint == 'billing.stripe_webhook' or
        request.endpoint == 'billing.upgrade'
    ):
        return

    if current_user.is_authenticated and current_user.organization:
        org = current_user.organization

        # Use consolidated billing service for comprehensive check
        has_access, reason = BillingService.check_organization_access(org)

        if not has_access:
            if reason == 'organization_suspended':
                flash('Your organization has been suspended. Please contact support.', 'error')
                return redirect(url_for('billing.upgrade'))
            elif reason not in ['exempt', 'developer']:
                flash('Subscription required to access the system.', 'error')
                return redirect(url_for('billing.upgrade'))

# Debug statements removed for production readiness

from ...services.stripe_service import StripeService
from ...services.subscription_service import SubscriptionService
from ...services.billing_service import BillingService
from ...services.signup_service import SignupService
from ...utils.permissions import require_permission, has_permission
from ...models import db, Organization, Permission
from ...models.billing_snapshot import BillingSnapshot

# Reconciliation routes removed - no more fallback logic needed

@billing_bp.route('/upgrade')
@login_required
def upgrade():
    """Show subscription upgrade options"""
    organization = current_user.organization
    if not organization:
        flash('No organization found', 'error')
        return redirect(url_for('app_routes.dashboard'))

    # Get pricing data from PricingService (handles Stripe integration and fallbacks)
    # This now uses the consolidated BillingService which includes snapshot logic
    pricing_data = BillingService.get_pricing_with_snapshots()

    logger.info(f"Pricing data retrieved for upgrade page: {len(pricing_data)} tiers")
    for tier_key, tier_info in pricing_data.items():
        logger.info(f"Tier {tier_key}: {tier_info.get('name', 'Unknown')} - Stripe Ready: {tier_info.get('is_stripe_ready', False)}")

    current_tier = organization.effective_subscription_tier

    return render_template('billing/upgrade.html',
                         organization=organization,
                         tiers=pricing_data,
                         current_tier=current_tier,
                         pricing_data=pricing_data,
                         subscription_details={
                             'status': 'active' if organization.tier else 'inactive',
                             'next_billing_date': None,
                             'amount': None,
                             'interval': 'monthly',
                             'trial_end': None,
                             'cancel_at_period_end': False
                         })

@billing_bp.route('/checkout/<tier>')
@billing_bp.route('/checkout/<tier>/<billing_cycle>')
def checkout(tier, billing_cycle='monthly'):
    """Create Stripe checkout session for subscription payment"""
    
    # Validate tier availability and Stripe configuration
    if not BillingService.validate_tier_availability(tier):
        flash('Invalid subscription tier selected.', 'error')
        return redirect(url_for('billing.upgrade'))

    if billing_cycle not in ['monthly', 'yearly']:
        billing_cycle = 'monthly'

    # Check if tier is configured in Stripe using the consolidated service's tier data
    tiers_config = BillingService.get_tiers_config() # Use consolidated method
    tier_data = tiers_config.get(tier, {})

    if billing_cycle == 'yearly' and not tier_data.get('stripe_price_id_yearly'):
        flash('Yearly billing not available for this tier.', 'error')
        return redirect(url_for('billing.upgrade'))
    elif billing_cycle == 'monthly' and not tier_data.get('stripe_price_id_monthly'):
        flash('This tier is not configured for billing.', 'error')
        return redirect(url_for('billing.upgrade'))

    # Handle new signups vs existing user upgrades
    if not current_user.is_authenticated and session.get('pending_signup'):
        # New customer signup flow
        try:
            price_key = BillingService.build_price_key(tier, billing_cycle)
            signup_data = session['pending_signup']
            checkout_session = StripeService.create_checkout_session_for_signup(
                signup_data, price_key
            )

            if not checkout_session:
                flash('Payment system temporarily unavailable. Please try again later.', 'error')
                return redirect(url_for('auth.signup'))

            return redirect(checkout_session.url)

        except Exception as e:
            logger.error(f"Signup checkout error: {str(e)}")
            flash('Unable to process payment. Please try again.', 'error')
            return redirect(url_for('auth.signup'))

    elif current_user.is_authenticated:
        # Existing user upgrade flow
        if not has_permission(current_user, 'organization.manage_billing'):
            flash('You do not have permission to manage billing.', 'error')
            return redirect(url_for('organization.dashboard'))

        try:
            price_key = BillingService.build_price_key(tier, billing_cycle)
            checkout_session = StripeService.create_checkout_session(current_user.organization, price_key)

            if not checkout_session:
                flash('Payment system temporarily unavailable. Please contact support.', 'error')
                return redirect(url_for('billing.upgrade'))

            return redirect(checkout_session.url)

        except Exception as e:
            logger.error(f"Upgrade checkout error: {str(e)}")
            flash('Payment system temporarily unavailable. Please contact support.', 'error')
            return redirect(url_for('billing.upgrade'))

    else:
        # No valid flow
        flash('Please complete signup first.', 'error')
        return redirect(url_for('auth.signup'))

@billing_bp.route('/customer-portal')
@login_required
def customer_portal():
    """Redirect to Stripe Customer Portal for self-service billing management"""
    if not has_permission(current_user, 'organization.manage_billing'):
        flash('You do not have permission to manage billing.', 'error')
        return redirect(url_for('organization.dashboard'))

    # Create return URL to billing tab
    return_url = url_for('settings.index', _external=True) + '#billing'

    session = StripeService.create_customer_portal_session(current_user.organization, return_url)

    if not session:
        # Fallback for development mode or if customer portal fails
        if not current_app.config.get('STRIPE_WEBHOOK_SECRET'):
            flash('Customer portal not available in development mode.', 'info')
        else:
            flash('Unable to access billing management. Please contact support.', 'error')
        return redirect(url_for('settings.index') + '#billing')

    return redirect(session.url)

@billing_bp.route('/cancel-subscription', methods=['POST'])
@login_required
def cancel_subscription():
    """Cancel current subscription"""
    if not has_permission(current_user, 'organization.manage_billing'):
        return jsonify({'error': 'Permission denied'}), 403

    success = StripeService.cancel_subscription(current_user.organization)

    if success:
        flash('Subscription canceled successfully.', 'success')
        return jsonify({'success': True})
    else:
        flash('Failed to cancel subscription. Please contact support.', 'error')
        return jsonify({'error': 'Failed to cancel subscription'}), 500

@billing_bp.route('/webhooks/stripe', methods=['POST'])
@csrf.exempt
def stripe_webhook():
    """Handle Stripe webhooks"""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')

    logger.info("=== STRIPE WEBHOOK RECEIVED ===")
    logger.info(f"Request method: {request.method}")
    logger.info(f"Content-Type: {request.headers.get('Content-Type')}")
    logger.info(f"User-Agent: {request.headers.get('User-Agent')}")
    logger.info(f"Signature: {sig_header[:20] if sig_header else 'None'}...")
    logger.info(f"Payload size: {len(payload)} bytes")
    logger.info(f"Environment: {current_app.config.get('ENV', 'unknown')}")

    # Check if webhook secret is configured
    webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')
    if not webhook_secret:
        logger.error("STRIPE_WEBHOOK_SECRET not configured - webhook cannot be verified")
        return jsonify({'error': 'Webhook secret not configured'}), 500

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
        logger.info(f"Webhook event verified successfully: {event['type']}")
    except ValueError as e:
        logger.error(f"Invalid payload in Stripe webhook: {str(e)}")
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature in Stripe webhook: {str(e)}")
        return jsonify({'error': 'Invalid signature'}), 400

    # Handle the event using centralized handler from the consolidated BillingService
    success = StripeService.handle_webhook(event)

    if success:
        return jsonify({'status': 'success'})
    else:
        return jsonify({'error': 'Webhook processing failed'}), 500


# This function has been moved to SignupService.complete_signup()

@billing_bp.route('/complete-signup-from-stripe')
def complete_signup_from_stripe():
    """Complete organization creation after successful Stripe payment"""
    valid, message = SignupService.validate_pending_signup()
    if not valid:
        flash(f'Signup validation failed: {message}', 'error')
        return redirect(url_for('auth.signup'))

    pending_signup = session.get('pending_signup')
    if not pending_signup:
        flash('Signup session expired. Please sign up again.', 'error')
        return redirect(url_for('auth.signup'))

    return SignupService.complete_signup(pending_signup['selected_tier'])


@billing_bp.route('/debug')
@login_required
def debug_billing():
    """Debug endpoint for billing information"""
    try:
        if not current_user.organization:
            error_response = {'error': 'No organization found for user'}
            if request.headers.get('Accept') == 'application/json':
                return jsonify(error_response), 400
            return render_template('billing/debug.html', debug_info=error_response)

        organization = current_user.organization
        max_users = organization.get_max_users()

        debug_data = {
            'user_id': current_user.id,
            'user_type': current_user.user_type,
            'organization_id': organization.id,
            'subscription_tier': organization.effective_subscription_tier,
            'stripe_configured': bool(current_app.config.get('STRIPE_SECRET_KEY')),
            'webhook_configured': bool(current_app.config.get('STRIPE_WEBHOOK_SECRET')),
            'organization_info': {
                'id': organization.id,
                'name': organization.name,
                'max_users': max_users,
                'active_users': organization.active_users_count,
                'features': organization.get_subscription_features()
            },
            'subscription_info': {
                'has_subscription': bool(organization.tier),
                'subscription_status': 'active' if organization.tier else 'inactive',
                'subscription_tier': organization.effective_subscription_tier
            }
        }

        org = current_user.organization
        subscription = org.tier if org else None
        debug_info = debug_data
        logger.info(f"Debug data generated successfully for user {current_user.id}")

        # Return JSON if requested via API
        if request.headers.get('Accept') == 'application/json':
            return jsonify(debug_info)

    except AttributeError as e:
        logger.error(f"AttributeError in debug_billing: {e}")
        error_response = {'error': f'Attribute error - likely missing organization or subscription: {str(e)}'}
        if request.headers.get('Accept') == 'application/json':
            return jsonify(error_response), 500
        return render_template('billing/debug.html', debug_info=error_response)
    except Exception as e:
        logger.error(f"Debug billing error for user {current_user.id if current_user else 'Unknown'}: {e}")
        error_response = {'error': f'Debug failed: {str(e)}'}
        if request.headers.get('Accept') == 'application/json':
            return jsonify(error_response), 500
        return render_template('billing/debug.html', debug_info=error_response)

    # Load tier information for debug buttons using the consolidated service's config
    tiers_config = BillingService.get_tiers_config()

    return render_template('billing/debug.html',
                         debug_info=debug_info,
                         organization=org,
                         subscription=subscription,
                         tiers_config=tiers_config)