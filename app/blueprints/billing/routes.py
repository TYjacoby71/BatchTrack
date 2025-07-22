from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from app.models import db, Organization, Permission
from app.utils.permissions import require_permission, has_permission
from app.blueprints.developer.subscription_tiers import load_tiers_config
import logging

billing_bp = Blueprint('billing', __name__, url_prefix='/billing')

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
                         current_tier=current_tier)

logger = logging.getLogger(__name__)

@billing_bp.route('/checkout/<tier>')
@billing_bp.route('/checkout/<tier>/<billing_cycle>')
@login_required
def checkout(tier, billing_cycle='monthly'):
    """Create Stripe checkout session and redirect"""
    if not has_permission(current_user, 'organization.manage_billing'):
        flash('You do not have permission to manage billing.', 'error')
        return redirect(url_for('organization.dashboard'))

    try:
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

        # Create checkout session
        try:
            from ...services.stripe_service import StripeService
            session = StripeService.create_checkout_session(current_user.organization, price_key)

            if not session:
                flash('Failed to create checkout session. Please try again.', 'error')
                return redirect(url_for('billing.upgrade'))
                
            return redirect(session.url)
        except ImportError:
            flash('Payment system not configured. Please contact support.', 'error')
            return redirect(url_for('billing.upgrade'))
    except Exception as e:
        logger.error(f"Checkout error for org {current_user.organization.id}: {str(e)}")
        flash('Payment system temporarily unavailable. Please try again later.', 'error')
        return redirect(url_for('billing.upgrade'))

@billing_bp.route('/cancel-subscription', methods=['POST'])
@login_required
def cancel_subscription():
    """Cancel current subscription"""
    if not has_permission(current_user, 'organization.manage_billing'):
        return jsonify({'error': 'Permission denied'}), 403

    try:
        from ...services.stripe_service import StripeService
        success = StripeService.cancel_subscription(current_user.organization)

        if success:
            flash('Subscription canceled successfully.', 'success')
            return jsonify({'success': True})
        else:
            flash('Failed to cancel subscription. Please contact support.', 'error')
            return jsonify({'error': 'Failed to cancel subscription'}), 500
    except ImportError:
        flash('Payment system not configured. Please contact support.', 'error')
        return jsonify({'error': 'Payment system not available'}), 500

@billing_bp.route('/webhooks/stripe', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhooks"""
    try:
        import stripe
        from ...services.stripe_service import StripeService
        
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
    except ImportError:
        logger.warning("Stripe not configured, webhook ignored")
        return jsonify({'status': 'stripe_not_configured'}), 200