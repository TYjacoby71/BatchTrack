from flask import render_template, request, jsonify, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from . import billing_bp
from ...extensions import csrf
import logging
import stripe

print(f"DEBUG: billing_bp in routes.py: {billing_bp}")
print(f"DEBUG: billing_bp name: {billing_bp.name}")
print(f"DEBUG: billing_bp url_prefix: {billing_bp.url_prefix}")

from ...services.stripe_service import StripeService
from ...services.subscription_service import SubscriptionService
from ...utils.permissions import require_permission, has_permission
from ...models import db, Organization, Permission
from ...blueprints.developer.subscription_tiers import load_tiers_config

def get_tier_permissions(tier_key):
    """Get all permissions for a subscription tier"""
    tiers_config = load_tiers_config()
    tier_data = tiers_config.get(tier_key, {})
    permission_names = tier_data.get('permissions', [])

    # Get actual permission objects
    permissions = Permission.query.filter(Permission.name.in_(permission_names)).all()
    return permissions

def user_has_tier_permission(user, permission_name):
    """Check if user has permission based on their subscription tier"""
    if user.user_type == 'developer':
        return True  # Developers have all permissions

    if not user.organization:
        return False

    # Get organization's subscription tier
    current_tier = user.organization.effective_subscription_tier

    # Get tier permissions
    tiers_config = load_tiers_config()
    tier_data = tiers_config.get(current_tier, {})
    tier_permissions = tier_data.get('permissions', [])

    return permission_name in tier_permissions

@billing_bp.route('/upgrade')
@login_required 
def upgrade():
    print("DEBUG: billing.upgrade route called")
    """Show subscription upgrade options"""
    organization = current_user.organization
    if not organization:
        flash('No organization found', 'error')
        return redirect(url_for('app_routes.dashboard'))

    # Load tier configuration
    tiers_config = load_tiers_config()

    # Filter for customer-facing and active tiers only
    customer_facing = request.args.get('customer_facing', 'true').lower() == 'true'
    active = request.args.get('active', 'true').lower() == 'true'

    available_tiers = {}
    for tier_key, tier_data in tiers_config.items():
        # Apply filters
        if customer_facing and not tier_data.get('is_customer_facing', True):
            continue
        if active and not tier_data.get('is_available', True):
            continue

        available_tiers[tier_key] = tier_data

    current_tier = organization.effective_subscription_tier

    return render_template('billing/upgrade.html',
                         organization=organization,
                         tiers=available_tiers,
                         current_tier=current_tier,
                         pricing_data=available_tiers,
                         subscription_details={
                             'status': organization.subscription.status if organization.subscription else 'inactive',
                             'next_billing_date': organization.subscription.next_billing_date if organization.subscription else None,
                             'amount': None,
                             'interval': 'monthly',
                             'trial_end': organization.subscription.trial_end if organization.subscription else None,
                             'cancel_at_period_end': False
                         })

logger = logging.getLogger(__name__)

@billing_bp.route('/checkout/<tier>')
@billing_bp.route('/checkout/<tier>/<billing_cycle>')
@login_required
def checkout(tier, billing_cycle='monthly'):
    """Create Stripe checkout session and redirect"""
    if not has_permission(current_user, 'organization.manage_billing'):
        flash('You do not have permission to manage billing.', 'error')
        return redirect(url_for('organization.dashboard'))

    # Validate tier is customer-facing and available
    from ...services.pricing_service import PricingService
    available_tiers = PricingService.get_pricing_data()

    if tier not in available_tiers:
        flash('Invalid or unavailable subscription tier.', 'error')
        return redirect(url_for('billing.upgrade'))

    if billing_cycle not in ['monthly', 'yearly']:
        billing_cycle = 'monthly'

    # Construct price key
    price_key = f"{tier}_{billing_cycle}" if billing_cycle != 'monthly' else tier

    # Check if tier is stripe-ready
    tiers_config = load_tiers_config()
    tier_data = tiers_config.get(tier, {})
    is_stripe_ready = tier_data.get('is_stripe_ready', False)
    
    # Create checkout session
    try:
        session = StripeService.create_checkout_session(current_user.organization, price_key)

        if not session:
            # Check if tier is not stripe-ready or we're in development mode
            if not is_stripe_ready or not current_app.config.get('STRIPE_WEBHOOK_SECRET'):
                # Development mode - simulate subscription
                success = StripeService.simulate_subscription_success(current_user.organization, tier)
                if success:
                    mode_reason = "Development Mode" if not is_stripe_ready else "Webhook not configured"
                    flash(f'{mode_reason}: Simulated {tier.title()} subscription activated!', 'success')
                    # Redirect to settings billing tab instead of organization dashboard
                    return redirect(url_for('settings.index') + '#billing')
                else:
                    flash('Failed to activate subscription in development mode.', 'error')
                    return redirect(url_for('billing.upgrade'))
            
            flash('Failed to create checkout session. Please try again.', 'error')
            return redirect(url_for('billing.upgrade'))
    except Exception as e:
        logger.error(f"Checkout error for org {current_user.organization.id}: {str(e)}")
        
        # Fallback for development
        if not is_stripe_ready:
            success = StripeService.simulate_subscription_success(current_user.organization, tier)
            if success:
                flash(f'Development Mode: {tier.title()} subscription activated!', 'success')
                return redirect(url_for('settings.index') + '#billing')
            else:
                flash('Failed to activate subscription in development mode.', 'error')
        else:
            flash('Payment system temporarily unavailable. Please try again later.', 'error')
        return redirect(url_for('billing.upgrade'))

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
    
    logger.info(f"Webhook received - Signature: {sig_header[:20] if sig_header else 'None'}...")
    logger.info(f"Payload size: {len(payload)} bytes")
    
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

    # Handle the event
    if event['type'] == 'customer.subscription.created':
        success = StripeService.handle_subscription_created(event['data']['object'])
        logger.info(f"Subscription created event handled: {success}")
    elif event['type'] == 'customer.subscription.updated':
        success = StripeService.handle_subscription_updated(event['data']['object'])
        logger.info(f"Subscription updated event handled: {success}")
    elif event['type'] == 'customer.subscription.deleted':
        # Handle subscription cancellation
        logger.info("Subscription deleted event received")
    else:
        logger.info(f"Unhandled Stripe webhook event: {event['type']}")

    return jsonify({'status': 'success'})


@billing_bp.route('/dev/activate/<tier>')
@login_required
def dev_activate_subscription(tier):
    """Development-only route to activate subscriptions"""
    from flask import current_app
    
    # Only allow in development mode
    if current_app.config.get('STRIPE_WEBHOOK_SECRET'):
        flash('This route is only available in development mode.', 'error')
        return redirect(url_for('billing.upgrade'))
    
    if not has_permission(current_user, 'organization.manage_billing'):
        flash('You do not have permission to manage billing.', 'error')
        return redirect(url_for('organization.dashboard'))
    
    # Validate tier
    from ...services.pricing_service import PricingService
    available_tiers = PricingService.get_pricing_data()
    
    if tier not in available_tiers:
        flash('Invalid subscription tier.', 'error')
        return redirect(url_for('billing.upgrade'))
    
    success = StripeService.simulate_subscription_success(current_user.organization, tier)
    
    if success:
        flash(f'Development Mode: {tier.title()} subscription activated!', 'success')
    else:
        flash('Failed to activate subscription.', 'error')
    
    return redirect(url_for('organization.dashboard'))


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