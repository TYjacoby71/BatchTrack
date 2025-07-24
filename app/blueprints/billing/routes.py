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
def checkout(tier, billing_cycle='monthly'):
    """Create Stripe checkout session and redirect"""
    from flask import session
    
    logger.info(f"Checkout route called for tier: {tier}, authenticated: {current_user.is_authenticated}")
    
    # Validate tier is customer-facing and available
    from ...services.pricing_service import PricingService
    available_tiers = PricingService.get_pricing_data()

    if tier not in available_tiers:
        flash('Invalid or unavailable subscription tier.', 'error')
        return redirect(url_for('billing.upgrade'))

    if billing_cycle not in ['monthly', 'yearly']:
        billing_cycle = 'monthly'

    # Check tier configuration for Stripe readiness
    tiers_config = load_tiers_config()
    tier_data = tiers_config.get(tier, {})
    is_stripe_ready = tier_data.get('is_stripe_ready', False)
    
    logger.info(f"Tier {tier} stripe_ready status: {is_stripe_ready}")

    # FLOW 1: DEVELOPMENT MODE (Stripe Ready = FALSE)
    # Bypass payment processing, create account immediately
    if not is_stripe_ready:
        logger.info(f"Development mode: Bypassing payment processing for tier {tier}")
        
        # NEW SIGNUP: User not authenticated but has pending signup data
        if not current_user.is_authenticated and session.get('pending_signup'):
            logger.info("Creating account immediately - no payment processing")
            return complete_signup_dev_mode(tier, is_stripe_mode=False)
        
        # EXISTING USER UPGRADE: User is authenticated, upgrade existing org
        elif current_user.is_authenticated:
            if not has_permission(current_user, 'organization.manage_billing'):
                flash('You do not have permission to manage billing.', 'error')
                return redirect(url_for('organization.dashboard'))
                
            logger.info(f"Upgrading existing user immediately - no payment processing")
            success = StripeService.simulate_subscription_success(current_user.organization, tier)
            if success:
                flash(f'Development Mode: {tier.title()} subscription activated!', 'success')
                return redirect(url_for('settings.index') + '#billing')
            else:
                flash('Failed to activate subscription in development mode.', 'error')
                return redirect(url_for('billing.upgrade'))
        
        # ERROR: No pending signup and not authenticated
        else:
            flash('Please complete signup information first.', 'error')
            return redirect(url_for('auth.signup'))
    
    # FLOW 2: PRODUCTION MODE (Stripe Ready = TRUE)  
    # Proceed to payment processing, hold account creation until payment success
    else:
        logger.info(f"Production mode: Processing payment first for tier {tier}")
        
        # NEW SIGNUP: Create temporary account first, then redirect to Stripe
        if not current_user.is_authenticated and session.get('pending_signup'):
            logger.info("Creating temporary account before Stripe checkout")
            return complete_signup_dev_mode(tier, is_stripe_mode=True)
        
        # EXISTING USER UPGRADE: Must be authenticated for billing changes
        elif current_user.is_authenticated:
            if not has_permission(current_user, 'organization.manage_billing'):
                flash('You do not have permission to manage billing.', 'error')
                return redirect(url_for('organization.dashboard'))
                
            try:
                price_key = f"{tier}_{billing_cycle}" if billing_cycle != 'monthly' else tier
                checkout_session = StripeService.create_checkout_session(current_user.organization, price_key)

                if not checkout_session:
                    flash('Stripe configuration incomplete. Please check your Stripe settings or contact support.', 'error')
                    return redirect(url_for('billing.upgrade'))

                return redirect(checkout_session.url)

            except Exception as e:
                logger.error(f"Checkout error for org {current_user.organization.id}: {str(e)}")
                flash('Payment system temporarily unavailable. Please contact support.', 'error')
                return redirect(url_for('billing.upgrade'))
        
        # ERROR: No authentication for production mode
        else:
            flash('Please complete account creation first, then upgrade your subscription.', 'error')
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


def complete_signup_dev_mode(tier, is_stripe_mode=False):
    """Shared function to create organization and user account"""
    from flask import session
    from ...models import User, Organization, Role, Subscription
    from flask_login import login_user

    logger.info(f"Starting development signup completion for tier: {tier}")

    # Get pending signup data from session
    pending_signup = session.get('pending_signup')
    if not pending_signup:
        logger.error("No pending signup found in session")
        flash('No pending signup found. Please start the signup process again.', 'error')
        return redirect(url_for('auth.signup'))

    logger.info(f"Found pending signup for: {pending_signup.get('username')}")

    try:
        # Create organization
        org = Organization(
            name=pending_signup['org_name'],
            contact_email=pending_signup['email'],
            is_active=True,
            signup_source=pending_signup['signup_source'],
            promo_code=pending_signup.get('promo_code'),
            referral_code=pending_signup.get('referral_code')
        )
        db.session.add(org)
        db.session.flush()  # Get the ID
        logger.info(f"Created organization with ID: {org.id}")

        # Create subscription record
        subscription = Subscription(
            organization_id=org.id,
            tier=tier,
            status='active',
            notes=f"Created from signup for {tier} tier (development mode)"
        )
        db.session.add(subscription)
        db.session.flush()
        logger.info(f"Created subscription with tier: {tier}")

        # Create organization owner user
        owner_user = User(
            username=pending_signup['username'],
            email=pending_signup['email'],
            first_name=pending_signup['first_name'],
            last_name=pending_signup['last_name'],
            phone=pending_signup.get('phone'),
            organization_id=org.id,
            user_type='customer',
            is_organization_owner=True,
            is_active=True
        )
        owner_user.set_password(pending_signup['password'])
        db.session.add(owner_user)
        db.session.flush()
        logger.info(f"Created user with ID: {owner_user.id}")

        # Assign organization owner role
        org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
        if org_owner_role:
            owner_user.assign_role(org_owner_role)
            logger.info("Assigned organization_owner role")

        # For development mode, activate subscription
        if not is_stripe_mode:
            success = StripeService.simulate_subscription_success(org, tier)
            if not success:
                raise Exception("Failed to activate development subscription")
            logger.info("Activated development subscription")

        # Commit all changes
        db.session.commit()
        logger.info("Database changes committed successfully")

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
        logger.error(f"Error creating account: {str(e)}")
        flash(f'Error creating account: {str(e)}', 'error')
        return redirect(url_for('auth.signup'))

@billing_bp.route('/complete-signup-from-stripe')
def complete_signup_from_stripe():
    """Complete organization creation after successful Stripe payment"""
    from flask import session
    
    pending_signup = session.get('pending_signup')
    if not pending_signup:
        flash('No pending signup found. Please start the signup process again.', 'error')
        return redirect(url_for('auth.signup'))

    # Use shared function for Stripe mode
    return complete_signup_dev_mode(pending_signup['selected_tier'], is_stripe_mode=True)

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

@billing_bp.route('/debug')
@login_required
def debug_billing():
    """Debug endpoint for billing information"""
    try:
        if not current_user.organization:
            return jsonify({'error': 'No organization found for user'}), 400

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
                'has_subscription': bool(current_user.organization.subscription),
                'subscription_status': current_user.organization.subscription.status if current_user.organization.subscription else None,
                'subscription_tier': current_user.organization.subscription.tier if current_user.organization.subscription else None
            }
        }
        logger.info(f"Debug data generated successfully for user {current_user.id}")
        return jsonify(debug_data)
    except AttributeError as e:
        logger.error(f"AttributeError in debug_billing: {e}")
        return jsonify({'error': f'Attribute error - likely missing organization or subscription: {str(e)}'}), 500
    except Exception as e:
        logger.error(f"Debug billing error for user {current_user.id if current_user else 'Unknown'}: {e}")
        return jsonify({'error': f'Debug failed: {str(e)}'}), 500

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