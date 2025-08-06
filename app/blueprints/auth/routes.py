from flask import render_template, request, redirect, url_for, flash, session, current_app, jsonify, abort
from flask_login import login_user, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired
from werkzeug.security import generate_password_hash
from . import auth_bp
from ...extensions import db
from ...models import User, Organization, Role, Permission
from ...utils.timezone_utils import TimezoneUtils
from ...utils.permissions import require_permission
from flask_login import login_required
import logging
from .whop_auth import WhopAuth # Import WhopAuth
from ...services.oauth_service import OAuthService
from ...services.email_service import EmailService
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('app_routes.dashboard'))

    form = LoginForm()
    if request.method == 'POST' and form.validate_on_submit():
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Please provide both username and password')
            return render_template('auth/login.html', form=form)

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            # Ensure user is active
            if not user.is_active:
                flash('Account is inactive. Please contact administrator.')
                return render_template('auth/login.html', form=form)

            # Log the user in
            login_user(user)

            # Update last login
            user.last_login = TimezoneUtils.utc_now()
            db.session.commit()

            # Redirect based on user type - developers go to their own dashboard
            if user.user_type == 'developer':
                return redirect(url_for('developer.dashboard'))
            else:
                return redirect(url_for('app_routes.dashboard'))
        else:
            flash('Invalid username or password')
            return render_template('auth/login.html', form=form)

    return render_template('auth/login.html', form=form, oauth_available=OAuthService.is_oauth_configured())

@auth_bp.route('/oauth/google')
def oauth_google():
    """Initiate Google OAuth flow"""
    logger.info("OAuth Google route accessed")
    
    # Check configuration with detailed logging
    config_status = OAuthService.get_configuration_status()
    logger.info(f"OAuth configuration status: {config_status}")
    
    if not config_status['is_configured']:
        logger.warning("OAuth not configured - redirecting to login with error")
        flash('OAuth is not configured. Please contact administrator.', 'error')
        return redirect(url_for('auth.login'))
    
    logger.info("Getting OAuth authorization URL")
    authorization_url, state = OAuthService.get_authorization_url()
    
    if not authorization_url:
        logger.error("Failed to get authorization URL")
        flash('Unable to initiate OAuth. Please try again.', 'error')
        return redirect(url_for('auth.login'))
    
    logger.info(f"OAuth authorization URL generated successfully, state: {state[:10]}...")
    session['oauth_state'] = state
    return redirect(authorization_url)

@auth_bp.route('/oauth/callback')
def oauth_callback():
    """Handle OAuth callback"""
    try:
        # Get state and code from callback
        state = request.args.get('state')
        code = request.args.get('code')
        error = request.args.get('error')
        
        logger.info(f"OAuth callback received - state: {state[:10] if state else None}, code: {code[:10] if code else None}, error: {error}")
        
        if error:
            logger.error(f"OAuth callback error: {error}")
            flash(f'OAuth authentication failed: {error}', 'error')
            return redirect(url_for('auth.login'))
        
        if not state or not code:
            logger.error("OAuth callback missing required parameters")
            flash('OAuth callback missing required parameters.', 'error')
            return redirect(url_for('auth.login'))
        
        # Exchange code for credentials
        credentials = OAuthService.exchange_code_for_token(code, state)
        if not credentials:
            logger.error("Failed to exchange OAuth code for credentials")
            flash('OAuth authentication failed. Please try again.', 'error')
            return redirect(url_for('auth.login'))
        
        # Get user info from Google
        user_info = OAuthService.get_user_info(credentials)
        if not user_info:
            flash('Unable to retrieve user information. Please try again.', 'error')
            return redirect(url_for('auth.login'))
        
        email = user_info.get('email')
        first_name = user_info.get('given_name', '')
        last_name = user_info.get('family_name', '')
        oauth_id = user_info.get('sub')
        
        if not email:
            flash('Email address is required for account creation.', 'error')
            return redirect(url_for('auth.login'))
        
        # Check if user exists
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Existing user - update OAuth info if needed
            if not user.oauth_provider:
                user.oauth_provider = 'google'
                user.oauth_provider_id = oauth_id
                user.email_verified = True  # OAuth emails are pre-verified
                db.session.commit()
            
            # Log them in
            login_user(user)
            user.last_login = TimezoneUtils.utc_now()
            db.session.commit()
            
            flash(f'Welcome back, {user.first_name}!', 'success')
            
            if user.user_type == 'developer':
                return redirect(url_for('developer.dashboard'))
            else:
                return redirect(url_for('app_routes.dashboard'))
        
        else:
            # New user - store info for signup flow
            session['oauth_user_info'] = {
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'oauth_provider': 'google',
                'oauth_provider_id': oauth_id,
                'email_verified': True
            }
            
            flash('Please complete your account setup by selecting a subscription plan.', 'info')
            return redirect(url_for('auth.signup'))
    
    except Exception as e:
        logger.error(f"OAuth callback error: {str(e)}")
        flash('OAuth authentication failed. Please try again.', 'error')
        return redirect(url_for('auth.login'))

@auth_bp.route('/verify-email/<token>')
def verify_email(token):
    """Verify email address"""
    try:
        # Find user with this verification token
        user = User.query.filter_by(email_verification_token=token).first()
        
        if not user:
            flash('Invalid verification link.', 'error')
            return redirect(url_for('auth.login'))
        
        # Check if token is expired (24 hours)
        if user.email_verification_sent_at:
            expires_at = user.email_verification_sent_at + timedelta(hours=24)
            if TimezoneUtils.utc_now() > expires_at:
                flash('Verification link has expired. Please request a new one.', 'error')
                return redirect(url_for('auth.resend_verification'))
        
        # Verify the email
        user.email_verified = True
        user.email_verification_token = None
        user.email_verification_sent_at = None
        db.session.commit()
        
        flash('Email verified successfully! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
        
    except Exception as e:
        logger.error(f"Email verification error: {str(e)}")
        flash('Email verification failed. Please try again.', 'error')
        return redirect(url_for('auth.login'))

@auth_bp.route('/resend-verification', methods=['GET', 'POST'])
def resend_verification():
    """Resend email verification"""
    if request.method == 'POST':
        email = request.form.get('email')
        
        user = User.query.filter_by(email=email).first()
        if user and not user.email_verified:
            # Generate new verification token
            user.email_verification_token = EmailService.generate_verification_token(email)
            user.email_verification_sent_at = TimezoneUtils.utc_now()
            db.session.commit()
            
            # Send verification email
            EmailService.send_verification_email(
                email, 
                user.email_verification_token, 
                user.first_name
            )
            
            flash('Verification email sent! Please check your inbox.', 'success')
        else:
            flash('If an account with that email exists and is unverified, a verification email has been sent.', 'info')
        
        return redirect(url_for('auth.login'))
    
    return render_template('auth/resend_verification.html')

@auth_bp.route('/logout')
def logout():
    from flask import session

    # Clear developer customer view session if present
    session.pop('dev_selected_org_id', None)

    logout_user()
    return redirect(url_for('homepage'))

@auth_bp.route('/dev-login')
def dev_login():
    """Quick developer login for system access"""
    dev_user = User.query.filter_by(username='dev').first()
    if dev_user:
        login_user(dev_user)
        flash('Developer access granted', 'success')
        return redirect(url_for('developer.dashboard'))
    else:
        flash('Developer account not found. Please contact system administrator.', 'error')
        return redirect(url_for('auth.login'))

@auth_bp.route('/signup-data')
def signup_data():
    """API endpoint to get available tiers for signup modal"""
    from ...services.billing_service import BillingService
    from ...blueprints.developer.subscription_tiers import load_tiers_config

    # Get available tiers from billing service
    available_tiers_db = BillingService.get_available_tiers()
    tiers_config = load_tiers_config()

    # Show all customer-facing tiers
    available_tiers = {}
    for tier_obj in available_tiers_db:
        tier_config = tiers_config.get(tier_obj.key, {})
        if tier_config and tier_config.get('is_customer_facing', True):
            # Get features from the correct JSON structure
            features = tier_config.get('fallback_features', [])

            available_tiers[tier_obj.key] = {
                'name': tier_obj.name,
                'price_monthly': 0,  # Will be populated from Stripe/Whop
                'price_display': tier_obj.fallback_price,
                'price_yearly': '$0',  # Will be populated from Stripe/Whop
                'features': features,
                'user_limit': tier_obj.user_limit,
                'whop_product_id': tier_config.get('whop_product_id', '')
            }

    return jsonify({
        'available_tiers': available_tiers,
        'oauth_available': OAuthService.is_oauth_configured()
    })

@auth_bp.route('/debug/oauth-config')
def debug_oauth_config():
    """Debug OAuth configuration - only in debug mode"""
    if not current_app.config.get('DEBUG'):
        abort(404)
        
    config_status = OAuthService.get_configuration_status()
    
    return jsonify({
        'oauth_configuration': config_status,
        'environment_vars': {
            'GOOGLE_OAUTH_CLIENT_ID_present': bool(current_app.config.get('GOOGLE_OAUTH_CLIENT_ID')),
            'GOOGLE_OAUTH_CLIENT_SECRET_present': bool(current_app.config.get('GOOGLE_OAUTH_CLIENT_SECRET'))
        },
        'template_oauth_available': OAuthService.is_oauth_configured()
    })

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """Simplified signup flow - tier selection only, then redirect to payment"""
    if current_user.is_authenticated:
        return redirect(url_for('app_routes.dashboard'))

    # Get pricing data for customer-facing tiers only
    from ...services.billing_service import BillingService
    from ...blueprints.developer.subscription_tiers import load_tiers_config

    # Get available tiers from billing service
    available_tiers_db = BillingService.get_available_tiers()
    tiers_config = load_tiers_config()

    # Show all customer-facing tiers
    available_tiers = {}
    for tier_obj in available_tiers_db:
        tier_config = tiers_config.get(tier_obj.key, {})
        if tier_config:
            # Get features from the correct JSON structure
            features = tier_config.get('fallback_features', [])

            available_tiers[tier_obj.key] = {
                'name': tier_obj.name,
                'price_monthly': 0,  # Will be populated from Stripe/Whop
                'price_display': tier_obj.fallback_price,
                'price_yearly': '$0',  # Will be populated from Stripe/Whop
                'features': features,
                'user_limit': tier_obj.user_limit,
                'whop_product_id': tier_config.get('whop_product_id', '')
            }

    # Get signup tracking parameters
    signup_source = request.args.get('source', request.form.get('source', 'direct'))
    referral_code = request.args.get('ref', request.form.get('ref'))
    promo_code = request.args.get('promo', request.form.get('promo'))
    preselected_tier = request.args.get('tier')
    
    # Check for OAuth user info from session
    oauth_user_info = session.get('oauth_user_info')
    
    if request.method == 'POST':
        selected_tier = request.form.get('selected_tier')
        oauth_signup = request.form.get('oauth_signup') == 'true'

        if not selected_tier:
            flash('Please select a subscription plan', 'error')
            return render_template('auth/signup.html',
                         signup_source=signup_source,
                         referral_code=referral_code,
                         promo_code=promo_code,
                         available_tiers=available_tiers,
                         oauth_user_info=oauth_user_info)

        if selected_tier not in available_tiers:
            flash('Invalid subscription plan selected', 'error')
            return render_template('auth/signup.html',
                         signup_source=signup_source,
                         referral_code=referral_code,
                         promo_code=promo_code,
                         available_tiers=available_tiers,
                         oauth_user_info=oauth_user_info)

        # Create Stripe checkout session
        from ...services.stripe_service import StripeService
        from ...models import SubscriptionTier
        
        tier_obj = SubscriptionTier.query.filter_by(key=selected_tier).first()
        if not tier_obj:
            flash('Invalid subscription plan', 'error')
            return render_template('auth/signup.html',
                         signup_source=signup_source,
                         referral_code=referral_code,
                         promo_code=promo_code,
                         available_tiers=available_tiers,
                         oauth_user_info=oauth_user_info)

        # Metadata for Stripe (minimal for now)
        metadata = {
            'tier': selected_tier,
            'signup_source': signup_source,
            'oauth_signup': str(oauth_signup)
        }
        
        if oauth_user_info:
            metadata['oauth_email'] = oauth_user_info.get('email', '')
            metadata['oauth_provider'] = oauth_user_info.get('oauth_provider', '')
            metadata['oauth_provider_id'] = oauth_user_info.get('oauth_provider_id', '')
        
        if referral_code:
            metadata['referral_code'] = referral_code
        if promo_code:
            metadata['promo_code'] = promo_code
        
        success_url = url_for('billing.complete_signup_from_stripe', _external=True) + '?session_id={CHECKOUT_SESSION_ID}'
        cancel_url = url_for('auth.signup', _external=True)
        
        # Let Stripe collect all user info
        stripe_session = StripeService.create_checkout_session_for_tier(
            tier_obj,
            customer_email=oauth_user_info.get('email') if oauth_user_info else None,
            customer_name=None,  # Let Stripe collect this
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata
        )

        if stripe_session:
            # Store minimal signup info for completion
            session['pending_signup'] = {
                'selected_tier': selected_tier,
                'signup_source': signup_source,
                'referral_code': referral_code,
                'promo_code': promo_code,
                'oauth_user_info': oauth_user_info
            }
            return redirect(stripe_session.url)
        else:
            flash('Payment system temporarily unavailable. Please try again later.', 'error')

    return render_template('auth/signup.html',
                         signup_source=signup_source,
                         referral_code=referral_code,
                         promo_code=promo_code,
                         available_tiers=available_tiers,
                         oauth_user_info=oauth_user_info,
                         oauth_available=OAuthService.is_oauth_configured(),
                         preselected_tier=preselected_tier)

# Whop License Login Route
@auth_bp.route('/whop-login', methods=['POST'])
def whop_login():
    """Authenticate user with Whop license key"""
    license_key = request.form.get('license_key')
    email = request.form.get('email', '')

    if not license_key:
        flash('License key is required.', 'error')
        return redirect(url_for('auth.login'))

    from .whop_auth import WhopAuth
    user_data = WhopAuth.handle_whop_login(license_key, email) # Corrected variable name

    if user_data:
        # Attempt to find or create user based on Whop data
        user = User.query.filter_by(email=user_data.get('email')).first()
        if not user:
            # Create a new user if they don't exist
            # You'll need to decide on a username strategy if not provided by Whop
            username = user_data.get('username', user_data.get('email').split('@')[0]) # Example username generation
            user = User(
                username=username,
                email=user_data.get('email'),
                first_name=user_data.get('first_name', ''),
                last_name=user_data.get('last_name', ''),
                is_active=True, # Assume active if they have a valid license
                user_type='customer' # Default user type
            )
            # Password is not managed by Whop, so it won't be set here. Consider passwordless login or initial setup.
            db.session.add(user)
            db.session.flush() # Flush to get user.id

        # Assign role/tier based on Whop data if available and map it to your internal roles
        # This part is highly dependent on how you map Whop products/tiers to your app's roles
        # Example:
        # whop_product_id = user_data.get('product_id')
        # role = Role.query.filter_by(whop_product_id=whop_product_id).first()
        # if role:
        #     user.roles.append(role) # Assuming a many-to-many relationship for roles

        login_user(user)
        user.last_login = TimezoneUtils.utc_now()
        db.session.commit()
        flash('Successfully logged in with Whop license.', 'success')
        return redirect(url_for('app_routes.dashboard'))
    else:
        flash('Invalid license key or access denied.', 'error')
        return redirect(url_for('auth.login'))

# Permission and Role Management Routes have been moved to organization blueprint

@auth_bp.route('/roles/<int:role_id>')
@login_required
@require_permission('organization.manage_roles')
def get_role(role_id):
    """Get role details for editing"""
    role = Role.query.get_or_404(role_id)

    # Check permissions
    if role.is_system_role and current_user.user_type != 'developer':
        abort(403)

    if role.organization_id != current_user.organization_id and current_user.user_type != 'developer':
        abort(403)

    return jsonify({
        'success': True,
        'role': {
            'id': role.id,
            'name': role.name,
            'description': role.description,
            'permission_ids': [p.id for p in role.permissions]
        }
    })

@auth_bp.route('/permissions/api')
@login_required
@require_permission('organization.manage_roles')
def permissions_api():
    """API endpoint for permissions data"""
    permissions = Permission.query.filter_by(is_active=True).all()

    categories = {}
    for perm in permissions:
        category = perm.category or 'general'
        if category not in categories:
            categories[category] = []
        categories[category].append({
            'id': perm.id,
            'name': perm.name,
            'description': perm.description,
            'required_subscription_tier': perm.required_subscription_tier
        })

    return jsonify({
        'success': True,
        'categories': categories
    })