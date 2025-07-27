from flask import render_template, request, jsonify, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from . import billing_bp
from ...extensions import csrf
import logging
import stripe

# Debug statements removed for production readiness

from ...services.stripe_service import StripeService
from ...services.subscription_service import SubscriptionService
from ...services.billing_service import BillingService
from ...services.signup_service import SignupService
from ...utils.permissions import require_permission, has_permission
from ...models import db, Organization, Permission

@billing_bp.route('/reconciliation-needed')
@login_required
def reconciliation_needed():
    """Show reconciliation flow for users who signed up during Stripe outages"""
    from ...services.resilient_billing_service import ResilientBillingService
    
    needs_reconciliation, reason = ResilientBillingService.check_reconciliation_needed(current_user.organization)
    
    if not needs_reconciliation:
        return redirect(url_for('app_routes.dashboard'))
    
    # Get grace period info
    from ...models.billing_snapshot import BillingSnapshot
    latest_snapshot = BillingSnapshot.get_latest_valid_snapshot(current_user.organization.id)
    
    return render_template('billing/reconciliation_needed.html',
                         requested_tier=current_user.organization.effective_subscription_tier,
                         grace_expires=latest_snapshot.period_end if latest_snapshot else None,
                         reason=reason)

@billing_bp.route('/reconcile-to-free', methods=['POST'])
@login_required
def reconcile_to_free():
    """Handle user choosing free plan during reconciliation"""
    from app.models.subscription_tier import SubscriptionTier
    free_tier = SubscriptionTier.query.filter_by(key='free').first()
    if free_tier and current_user.organization:
        current_user.organization.subscription_tier_id = free_tier.id
        db.session.commit()
        flash('Your account has been updated to the free plan.', 'success')
    
    return redirect(url_for('app_routes.dashboard'))

@billing_bp.route('/upgrade')
@login_required 
def upgrade():
    print("DEBUG: billing.upgrade route called")
    """Show subscription upgrade options"""
    organization = current_user.organization
    if not organization:
        flash('No organization found', 'error')
        return redirect(url_for('app_routes.dashboard'))

    # Get available tiers using BillingService
    customer_facing = request.args.get('customer_facing', 'true').lower() == 'true'
    active = request.args.get('active', 'true').lower() == 'true'
    
    available_tiers = BillingService.get_available_tiers(
        customer_facing=customer_facing,
        active=active
    )

    current_tier = organization.effective_subscription_tier

    return render_template('billing/upgrade.html',
                         organization=organization,
                         tiers=available_tiers,
                         current_tier=current_tier,
                         pricing_data=available_tiers,
                         subscription_details={
                             'status': 'active' if organization.tier else 'inactive',
                             'next_billing_date': None,
                             'amount': None,
                             'interval': 'monthly',
                             'trial_end': None,
                             'cancel_at_period_end': False
                         })

logger = logging.getLogger(__name__)

@billing_bp.route('/checkout/<tier>')
@billing_bp.route('/checkout/<tier>/<billing_cycle>')
def checkout(tier, billing_cycle='monthly'):
    """Create Stripe checkout session for subscription payment"""
    from flask import session

    # Validate tier availability and Stripe configuration
    if not BillingService.validate_tier_availability(tier):
        flash('Invalid subscription tier selected.', 'error')
        return redirect(url_for('billing.upgrade'))

    if billing_cycle not in ['monthly', 'yearly']:
        billing_cycle = 'monthly'

    # Check if tier is configured in Stripe
    from ..blueprints.developer.subscription_tiers import load_tiers_config
    tiers_config = load_tiers_config()
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

    # Handle the event using centralized handler
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
    return SignupService.complete_signup(pending_signup['selected_tier'], is_stripe_mode=True)



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

        max_users = current_user.organization.get_max_users()

        debug_data = {
            'user_id': current_user.id,
            'user_type': current_user.user_type,
            'organization_id': current_user.organization_id,
            'subscription_tier': current_user.organization.effective_subscription_tier,
            'stripe_configured': bool(current_app.config.get('STRIPE_SECRET_KEY')),
            'webhook_configured': bool(current_app.config.get('STRIPE_WEBHOOK_SECRET')),
            'organization_info': {
                'id': current_user.organization.id,
                'name': current_user.organization.name,
                'max_users': max_users,
                'active_users': current_user.organization.active_users_count,
                'features': current_user.organization.get_subscription_features()
            },
            'subscription_info': {
                'has_subscription': bool(current_user.organization.tier),
                'subscription_status': 'active' if current_user.organization.tier else 'inactive',
                'subscription_tier': current_user.organization.effective_subscription_tier
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

    # Load tier information for debug buttons
    from ..developer.subscription_tiers import load_tiers_config
    tiers_config = load_tiers_config()

    return render_template('billing/debug.html', 
                         debug_info=debug_info,
                         organization=org,
                         subscription=subscription,
                         tiers_config=tiers_config)

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, current_app.config['STRIPE_WEBHOOK_SECRET']
        )
    except ValueError:
        logger.error("Invalid payload in Stripe webhook")
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid signature in Stripe webhook")
        return jsonify({'error': 'Invalid signature'}), 400

    # Handle the event
    if event['type'] == 'customer.subscription.created':
        StripeService.handle_subscription_created(event['data']['object'])
    elif event['type'] == 'customer.subscription.updated':
        StripeService.handle_subscription_updated(event['data']['object'])
    elif event['type'] == 'customer.subscription.deleted':
        # Handle subscription cancellation
        pass
    else:
        logger.info(f"Unhandled Stripe webhook event: {event['type']}")

    return jsonify({'status': 'success'})