
import stripe
from flask import render_template, request, jsonify, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from . import billing_bp
from ...services.stripe_service import StripeService
from ...services.subscription_service import SubscriptionService
from ...utils.permissions import has_permission
import logging

logger = logging.getLogger(__name__)

@billing_bp.route('/upgrade')
@login_required
def upgrade():
    """Show upgrade options"""
    if not has_permission(current_user, 'manage_billing'):
        flash('You do not have permission to manage billing.', 'error')
        return redirect(url_for('organization.dashboard'))
    
    current_tier = SubscriptionService.get_effective_tier(current_user.organization)
    return render_template('billing/upgrade.html', current_tier=current_tier)

@billing_bp.route('/checkout/<tier>')
@billing_bp.route('/checkout/<tier>/<billing_cycle>')
@login_required
def checkout(tier, billing_cycle='monthly'):
    """Create Stripe checkout session and redirect"""
    if not has_permission(current_user, 'manage_billing'):
        flash('You do not have permission to manage billing.', 'error')
        return redirect(url_for('organization.dashboard'))
    
    if tier not in ['solo', 'team', 'enterprise']:
        flash('Invalid subscription tier.', 'error')
        return redirect(url_for('billing.upgrade'))
    
    if billing_cycle not in ['monthly', 'yearly']:
        billing_cycle = 'monthly'
    
    # Construct price key
    price_key = f"{tier}_{billing_cycle}" if billing_cycle != 'monthly' else tier
    
    # Create checkout session
    try:
        session = StripeService.create_checkout_session(current_user.organization, price_key)
        
        if not session:
            flash('Failed to create checkout session. Please try again.', 'error')
            return redirect(url_for('billing.upgrade'))
    except Exception as e:
        logger.error(f"Checkout error for org {current_user.organization.id}: {str(e)}")
        flash('Payment system temporarily unavailable. Please try again later.', 'error')
        return redirect(url_for('billing.upgrade'))
    
    return redirect(session.url)

@billing_bp.route('/cancel-subscription', methods=['POST'])
@login_required
def cancel_subscription():
    """Cancel current subscription"""
    if not has_permission(current_user, 'manage_billing'):
        return jsonify({'error': 'Permission denied'}), 403
    
    success = StripeService.cancel_subscription(current_user.organization)
    
    if success:
        flash('Subscription canceled successfully.', 'success')
        return jsonify({'success': True})
    else:
        flash('Failed to cancel subscription. Please contact support.', 'error')
        return jsonify({'error': 'Failed to cancel subscription'}), 500

@billing_bp.route('/webhooks/stripe', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhooks"""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
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
