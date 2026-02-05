"""Billing and subscription routes.

File purpose:
1) Present upgrade options, manage checkout, and handle billing webhooks.
2) Expose add-on checkout endpoints and downgrade selection flow.

Route index:
1. GET /billing/upgrade -> tier upgrade UI.
2. GET /billing/storage -> storage add-on checkout (legacy flow).
3. POST /billing/addons/start/<addon_key> -> start add-on checkout.
4. GET /billing/checkout/<tier> -> start tier checkout.
5. GET /billing/checkout/<tier>/<billing_cycle> -> start tier checkout (cycle).
6. GET/POST /billing/downgrade/<tier> -> downgrade recipe selection.
7. GET/POST /billing/downgrade/<tier>/<billing_cycle> -> downgrade selection (cycle).
8. GET /billing/whop-checkout/<product_id> -> Whop checkout.
9. GET /billing/complete-signup-from-stripe -> Stripe post-checkout callback.
10. GET /billing/complete-signup-from-whop -> Whop post-checkout callback.
11. GET /billing/customer-portal -> Stripe customer portal.
12. POST /billing/cancel-subscription -> cancel subscription.
13. POST /billing/webhooks/stripe -> Stripe webhooks.
14. GET /billing/debug -> billing debug payload.
"""

import logging
import os
import json
from datetime import datetime, timedelta
from flask import Blueprint, request, render_template, flash, redirect, url_for, session, jsonify, current_app
from flask_login import login_required, current_user, login_user
from ...services.billing_service import BillingService
from ...services.subscription_downgrade_service import (
    build_downgrade_context,
    apply_downgrade_selection,
)
from ...utils.permissions import require_permission
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

# Route 1: Show upgrade options and current tier context.
@billing_bp.route('/upgrade')
@login_required
@require_permission('organization.manage_billing')
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

# Route 2: Start storage add-on checkout (legacy storage add-on).
@billing_bp.route('/storage')
@login_required
@require_permission('organization.manage_billing')
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
        session = BillingService.create_subscription_checkout_by_lookup_key(
            lookup_key,
            current_user.email,
            success_url=url_for('billing.upgrade', _external=True),
            cancel_url=url_for('billing.upgrade', _external=True),
            metadata={'addon': 'storage'}
        )
        if session and getattr(session, 'url', None):
            return redirect(session.url)
        flash('Unable to start storage checkout', 'error')
    except Exception as e:
        logger.error(f"Storage add-on checkout error: {e}")
        flash('Checkout failed. Please try again later.', 'error')
    return redirect(url_for('billing.upgrade'))

# Route 3: Start add-on checkout for allowed add-ons.
@billing_bp.route('/addons/start/<addon_key>', methods=['POST'])
@login_required
@require_permission('organization.manage_billing')
def start_addon_checkout(addon_key):
    """Start Stripe checkout for a specific add-on by key (uses addon.stripe_lookup_key).
    Enforces that the add-on is allowed for the organization's current tier.
    """
    from ...models.addon import Addon
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
        session = BillingService.create_subscription_checkout_by_lookup_key(
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

# Route 4-5: Start tier checkout (optionally with billing cycle).
@billing_bp.route('/checkout/<tier>')
@billing_bp.route('/checkout/<tier>/<billing_cycle>')
@login_required
@require_permission('organization.manage_billing')
def checkout(tier, billing_cycle='month'):
    """Initiate checkout process"""
    organization = current_user.organization
    if not organization:
        flash('No organization found', 'error')
        return redirect(url_for('billing.upgrade'))

    try:
        target_tier = SubscriptionTier.find_by_identifier(tier)
        if not target_tier:
            flash('Checkout not available for this tier', 'error')
            return redirect(url_for('billing.upgrade'))

        downgrade_context = build_downgrade_context(organization, target_tier)
        limit = downgrade_context.get("limit")
        if limit is not None:
            active_count = len(downgrade_context.get("active_recipes") or [])
            if active_count > limit:
                return redirect(url_for('billing.downgrade', tier=tier, billing_cycle=billing_cycle))

        # Use unified billing service for checkout
        checkout_session = BillingService.create_checkout_session(
            tier,
            current_user.email,
            f"{current_user.first_name} {current_user.last_name}",
            url_for('billing.complete_signup_from_stripe', _external=True),
            url_for('billing.upgrade', _external=True),
            metadata={'tier': tier, 'billing_cycle': billing_cycle},
            existing_customer_id=getattr(organization, 'stripe_customer_id', None),
        )
        
        if checkout_session:
            return redirect(checkout_session.url)

        flash('Checkout not available for this tier', 'error')
        return redirect(url_for('billing.upgrade'))

    except Exception as e:
        logger.error(f"Checkout error: {e}")
        flash('Checkout failed. Please try again.', 'error')
        return redirect(url_for('billing.upgrade'))


# Route 6-7: Downgrade selection flow for recipe limits.
@billing_bp.route('/downgrade/<tier>', methods=['GET', 'POST'])
@billing_bp.route('/downgrade/<tier>/<billing_cycle>', methods=['GET', 'POST'])
@login_required
@require_permission('organization.manage_billing')
def downgrade(tier, billing_cycle='month'):
    organization = current_user.organization
    if not organization:
        flash('No organization found', 'error')
        return redirect(url_for('billing.upgrade'))

    target_tier = SubscriptionTier.find_by_identifier(tier)
    if not target_tier:
        flash('Invalid subscription tier selected', 'error')
        return redirect(url_for('billing.upgrade'))

    context = build_downgrade_context(organization, target_tier)
    limit = context.get("limit")
    if limit is None:
        return redirect(url_for('billing.checkout', tier=tier, billing_cycle=billing_cycle))

    if request.method == 'POST':
        selected_ids = request.form.getlist('keep_recipe_ids')
        success, message = apply_downgrade_selection(
            organization,
            target_tier,
            [int(val) for val in selected_ids if str(val).isdigit()],
            user_id=getattr(current_user, 'id', None),
        )
        if not success:
            flash(message, 'error')
        else:
            flash(message, 'success')
            return redirect(url_for('billing.checkout', tier=tier, billing_cycle=billing_cycle))

    return render_template(
        'billing/downgrade_recipes.html',
        organization=organization,
        target_tier=target_tier,
        required_count=context.get("required_count"),
        limit=limit,
        active_recipes=context.get("active_recipes"),
        locked_ids=set(context.get("locked_ids") or []),
        billing_cycle=billing_cycle,
    )

# Route 8: Redirect to Whop checkout.
@billing_bp.route('/whop-checkout/<product_id>')
@login_required
@require_permission('organization.manage_billing')
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

# Route 9: Finalize signup after Stripe checkout.
@billing_bp.route('/complete-signup-from-stripe')
def complete_signup_from_stripe():
    """Complete signup process after Stripe payment"""
    session_id = request.args.get('session_id')
    if not session_id:
        flash('Invalid checkout session', 'error')
        return redirect(url_for('auth.signup'))

    logger.info("Completing signup for checkout session %s", session_id)

    try:
        result = BillingService.finalize_checkout_session(session_id)
    except Exception as exc:
        logger.error("Stripe finalize failed for session %s: %s", session_id, exc)
        flash('Account setup failed. Please contact support.', 'error')
        return redirect(url_for('auth.signup'))

    organization = None
    owner_user = None
    if isinstance(result, tuple):
        organization, owner_user = result

    if not owner_user:
        flash('Payment confirmed! Please check your inbox for setup instructions.', 'info')
        return redirect(url_for('auth.login'))

    login_user(owner_user)
    SessionService.rotate_user_session(owner_user)
    owner_user.last_login = TimezoneUtils.utc_now()
    db.session.commit()

    session['onboarding_welcome'] = True
    tier_name = organization.subscription_tier.name if organization and organization.subscription_tier else 'BatchTrack'
    flash(f'Welcome to BatchTrack! Your {tier_name} account is ready to use.', 'success')
    return redirect(url_for('onboarding.welcome'))

# Route 10: Finalize signup after Whop checkout.
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

# Route 11: Redirect to the Stripe customer portal.
@billing_bp.route('/customer-portal')
@login_required
@require_permission('organization.manage_billing')
def customer_portal():
    """Redirect to Stripe customer portal"""
    organization = current_user.organization
    if not organization or not organization.stripe_customer_id:
        flash('No billing account found', 'error')
        return redirect(url_for('app_routes.dashboard'))

    try:
        portal_session = BillingService.create_customer_portal_session(
            organization,
            url_for('app_routes.dashboard', _external=True)
        )
        if portal_session:
            return redirect(portal_session.url)
        flash('Unable to access billing portal', 'error')
    except Exception as e:
        logger.error(f"Customer portal error: {e}")
        flash('Billing portal unavailable', 'error')
    return redirect(url_for('app_routes.dashboard'))

# Route 12: Cancel the current subscription.
@billing_bp.route('/cancel-subscription', methods=['POST'])
@login_required
@require_permission('organization.manage_billing')
def cancel_subscription():
    """Cancel current subscription"""
    organization = current_user.organization
    if not organization:
        flash('No organization found', 'error')
        return redirect(url_for('app_routes.dashboard'))

    try:
        if organization.stripe_customer_id:
            success = BillingService.cancel_subscription(organization.stripe_customer_id)
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

# Route 13: Stripe webhook ingestion for billing + add-ons.
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
        event = BillingService.construct_event(payload, sig_header, webhook_secret)
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

# Route 14: Billing debug payload (developer-only).
@billing_bp.route('/debug')
@login_required
@require_permission('organization.manage_billing')
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