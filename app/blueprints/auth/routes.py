from flask import render_template, request, redirect, url_for, flash, session, current_app, jsonify, abort
from flask_login import login_user, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired
from werkzeug.security import generate_password_hash
from . import auth_bp
from ...extensions import db
from ...models import User, Organization, Role, Permission
from ...models.subscription_tier import SubscriptionTier # Import SubscriptionTier here
from ...utils.timezone_utils import TimezoneUtils
from ...utils.permissions import require_permission
from flask_login import login_required
import logging
from .whop_auth import WhopAuth # Import WhopAuth
from ...services.oauth_service import OAuthService
from ...services.email_service import EmailService
from ...extensions import limiter
from ...services.session_service import SessionService
from ...services.signup_service import SignupService
from ...services.billing_service import BillingService
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _log_loadtest_login_context(reason: str, extra: dict | None = None) -> None:
    """Emit structured diagnostics for load-test login failures."""
    if not current_app.config.get("LOADTEST_LOG_LOGIN_FAILURE_CONTEXT"):
        return

    try:
        details = {
            "reason": reason,
            "remote_addr": request.headers.get("X-Forwarded-For", request.remote_addr),
            "host": request.host,
            "scheme": request.scheme,
            "is_secure": request.is_secure,
            "x_forwarded_proto": request.headers.get("X-Forwarded-Proto"),
            "cookies_present": bool(request.cookies),
            "session_cookie_present": "session" in request.cookies,
            "csrf_token_in_form": bool(request.form.get("csrf_token")),
            "user_agent": (request.headers.get("User-Agent") or "")[:160],
        }
        if extra:
            details.update(extra)
        current_app.logger.warning("Load test login context: %s", details)
    except Exception as exc:  # pragma: no cover - diagnostics should never fail login
        current_app.logger.warning("Failed to log load test login context: %s", exc)

def load_tiers_config():
    raise RuntimeError('load_tiers_config has been removed. Use DB via SubscriptionTier queries.')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("6000/minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('app_routes.dashboard'))

    form = LoginForm()
    # Persist "next" param for OAuth/alternate login flows
    try:
        if request.method == 'GET':
            next_param = request.args.get('next')
            if next_param and isinstance(next_param, str) and next_param.startswith('/') and not next_param.startswith('//'):
                session['login_next'] = next_param
    except Exception:
        pass
    if request.method == 'POST' and form.validate_on_submit():
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Please provide both username and password')
            return render_template('pages/auth/login.html', form=form)

        user = User.query.filter_by(username=username).first()

        if username and username.startswith("loadtest_user"):
            logger.info(
                "Load test login attempt: %s, user_found=%s",
                username,
                bool(user),
            )
            if user:
                try:
                    password_valid = user.check_password(password or "")
                except Exception:
                    password_valid = False
                logger.info(
                    "Load test user state: is_active=%s, password_valid=%s",
                    user.is_active,
                    password_valid,
                )

        if user and user.check_password(password):
            # Ensure user is active
            if not user.is_active:
                if username and username.startswith("loadtest_user"):
                    logger.warning("Load test user %s is inactive", username)
                _log_loadtest_login_context("inactive_user", {"username": username})
                flash('Account is inactive. Please contact administrator.')
                return render_template('pages/auth/login.html', form=form)

            # Log the user in
            login_user(user)
            SessionService.rotate_user_session(user)

            # Clear dismissed alerts from session on login
            session.pop('dismissed_alerts', None)

            # Update last login
            user.last_login = TimezoneUtils.utc_now()
            db.session.commit()

            # Redirect based on user type and optional next parameter
            if user.user_type == 'developer':
                return redirect(url_for('developer.dashboard'))
            else:
                # Prefer an explicit next target if present and safe; otherwise go to dashboard
                try:
                    next_url = session.pop('login_next', None) or request.args.get('next')
                except Exception:
                    next_url = None
                if isinstance(next_url, str) and next_url.startswith('/') and not next_url.startswith('//'):
                    return redirect(next_url)
                return redirect(url_for('app_routes.dashboard'))
        else:
            _log_loadtest_login_context("invalid_credentials", {"username": username, "user_found": bool(user)})
            if username and username.startswith("loadtest_user"):
                logger.warning("Load test login failed: invalid credentials for %s", username)
            flash('Invalid username or password')
            return render_template('pages/auth/login.html', form=form)

    return render_template('pages/auth/login.html', form=form, oauth_available=OAuthService.is_oauth_configured())

@auth_bp.route('/oauth/google')
@limiter.limit("1200/minute")
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
@limiter.limit("1200/minute")
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

        # Validate state parameter against session
        session_state = session.pop('oauth_state', None)
        if not session_state or session_state != state:
            logger.error(f"OAuth state mismatch: session={session_state[:10] if session_state else None}, callback={state[:10]}")
            flash('OAuth state validation failed. Please try again.', 'error')
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
            SessionService.rotate_user_session(user)

            # Clear dismissed alerts from session on OAuth login
            session.pop('dismissed_alerts', None)

            user.last_login = TimezoneUtils.utc_now()
            db.session.commit()

            flash(f'Welcome back, {user.first_name}!', 'success')

            if user.user_type == 'developer':
                return redirect(url_for('developer.dashboard'))
            else:
                # Prefer explicit next if present; else dashboard
                try:
                    next_url = session.pop('login_next', None)
                except Exception:
                    next_url = None
                if isinstance(next_url, str) and next_url.startswith('/') and not next_url.startswith('//'):
                    return redirect(next_url)
                return redirect(url_for('organization.dashboard'))

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

            # Send new users to signup, but if a tool draft exists, keep it and deep-link to recipe after signup
            flash('Please complete your account setup by selecting a subscription plan.', 'info')
            return redirect(url_for('auth.signup', tier='free'))

    except Exception as e:
        logger.error(f"OAuth callback error: {str(e)}")
        flash('OAuth authentication failed. Please try again.', 'error')
        return redirect(url_for('auth.login'))

@auth_bp.route('/callback')
@limiter.limit("1200/minute")
def oauth_callback_compat():
    """Compatibility alias for tests expecting /auth/callback."""
    return oauth_callback()

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

    return render_template('pages/auth/resend_verification.html')

@auth_bp.route('/logout')
def logout():
    from flask import session

    # Clear developer customer view session if present
    session.pop('dev_selected_org_id', None)

    # Clear dismissed alerts from session on logout
    session.pop('dismissed_alerts', None)

    # Clear public tool drafts on logout so sensitive data doesn't persist between users
    try:
        session.pop('tool_draft', None)
        session.pop('tool_draft_meta', None)
    except Exception:
        pass
    if current_user.is_authenticated:
        current_user.active_session_token = None
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
    SessionService.clear_session_state()
    logout_user()
    return redirect(url_for('homepage'))

@auth_bp.route('/dev-login')
def dev_login():
    """Quick developer login for system access"""
    dev_user = User.query.filter_by(username='dev').first()
    if dev_user:
        login_user(dev_user)
        SessionService.rotate_user_session(dev_user)
        dev_user.last_login = TimezoneUtils.utc_now()
        db.session.commit()
        flash('Developer access granted', 'success')
        return redirect(url_for('developer.dashboard'))
    else:
        flash('Developer account not found. Please contact system administrator.', 'error')
        return redirect(url_for('auth.login'))

@auth_bp.route('/signup-data')
def signup_data():
    """API endpoint to get available tiers for signup modal"""
    # Get tiers filtered by database columns only - no hardcoded logic
    from ...models.subscription_tier import SubscriptionTier

    available_tiers_db = SubscriptionTier.query.filter_by(
            is_customer_facing=True).filter(
            SubscriptionTier.billing_provider != 'exempt').order_by(SubscriptionTier.user_limit).all()

    # Build purely from DB for display
    available_tiers = {}
    for tier_obj in available_tiers_db:
        # Features from permissions
        features = [p.name for p in getattr(tier_obj, 'permissions', [])]

        # Get live pricing from Stripe if available, otherwise use fallback
        live_pricing = None
        if tier_obj.stripe_lookup_key:
            try:
                live_pricing = BillingService.get_live_pricing_for_tier(tier_obj)
            except Exception:
                live_pricing = None

        # Use live pricing if available, otherwise show as contact sales
        if live_pricing:
            price_display = live_pricing['formatted_price']
        else:
            price_display = 'Contact Sales'

        available_tiers[str(tier_obj.id)] = {
            'name': tier_obj.name,
            'price_display': price_display,
            'features': features,
            'user_limit': tier_obj.user_limit,
            'whop_product_id': tier_obj.whop_product_key or ''
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
@limiter.limit("600/minute")
def signup():
    """Simplified signup flow - tier selection only, then redirect to payment"""
    if current_user.is_authenticated:
        return redirect(url_for('app_routes.dashboard'))

    # Get available tiers from database only
    from ...models.subscription_tier import SubscriptionTier
    db_tiers = SubscriptionTier.query.filter_by(
        is_customer_facing=True
    ).filter(
        SubscriptionTier.billing_provider != 'exempt'
    ).all()

    # Build available tiers using DB only
    available_tiers = {}
    for tier_obj in db_tiers:
        features = [p.name for p in getattr(tier_obj, 'permissions', [])]

        # Get live pricing from Stripe if available, otherwise use fallback
        live_pricing = None
        if tier_obj.stripe_lookup_key:
            try:
                live_pricing = BillingService.get_live_pricing_for_tier(tier_obj)
            except Exception:
                live_pricing = None

        # Use live pricing if available, otherwise show as contact sales
        price_display = live_pricing['formatted_price'] if live_pricing else 'Contact Sales'

        available_tiers[str(tier_obj.id)] = {
            'name': tier_obj.name,
            'price_display': price_display,
            'features': features,
            'user_limit': tier_obj.user_limit,
            'whop_product_id': tier_obj.whop_product_key or ''
        }

    # Get signup tracking parameters
    signup_source = request.args.get('source', request.form.get('source', 'direct'))
    referral_code = request.args.get('ref', request.form.get('ref'))
    promo_code = request.args.get('promo', request.form.get('promo'))
    preselected_tier = request.args.get('tier')

    # Check for OAuth user info from session
    oauth_user_info = session.get('oauth_user_info')
    prefill_email = request.form.get('contact_email') or (oauth_user_info.get('email') if oauth_user_info else '')
    prefill_phone = request.form.get('contact_phone') or ''

    if request.method == 'POST':
        selected_tier = request.form.get('selected_tier')
        oauth_signup = request.form.get('oauth_signup') == 'true'
        contact_email = (request.form.get('contact_email') or '').strip()
        contact_phone = (request.form.get('contact_phone') or '').strip()

        if not selected_tier:
            flash('Please select a subscription plan', 'error')
            return render_template('pages/auth/signup.html',
                         signup_source=signup_source,
                         referral_code=referral_code,
                         promo_code=promo_code,
                         available_tiers=available_tiers,
                         oauth_user_info=oauth_user_info,
                         contact_email=contact_email,
                         contact_phone=contact_phone)

        if selected_tier not in available_tiers:
            flash('Invalid subscription plan selected', 'error')
            return render_template('pages/auth/signup.html',
                         signup_source=signup_source,
                         referral_code=referral_code,
                         promo_code=promo_code,
                         available_tiers=available_tiers,
                         oauth_user_info=oauth_user_info,
                         contact_email=contact_email,
                         contact_phone=contact_phone)

        # Create Stripe checkout session
        from ...models import SubscriptionTier
        from ...services.signup_service import SignupService
        try:
            tier_id = int(selected_tier)
            tier_obj = db.session.get(SubscriptionTier, tier_id)
        except (ValueError, TypeError):
            tier_obj = None
        if not tier_obj:
            flash('Invalid subscription plan', 'error')
            return render_template('pages/auth/signup.html',
                         signup_source=signup_source,
                         referral_code=referral_code,
                         promo_code=promo_code,
                         available_tiers=available_tiers,
                         oauth_user_info=oauth_user_info)

        # Complete metadata for Stripe checkout - include all signup data
        metadata = {
            'tier_id': str(tier_obj.id),
            'tier_name': tier_obj.name,
            'signup_source': signup_source,
            'oauth_signup': str(oauth_signup)
        }
        
        # Add detected timezone from browser
        detected_timezone = request.form.get('detected_timezone')
        if detected_timezone:
            metadata['detected_timezone'] = detected_timezone
            logger.info(f"Auto-detected timezone: {detected_timezone}")

        # Add OAuth information if present
        if oauth_user_info:
            metadata['oauth_email'] = oauth_user_info.get('email', '')
            metadata['oauth_provider'] = oauth_user_info.get('oauth_provider', '')
            metadata['oauth_provider_id'] = oauth_user_info.get('oauth_provider_id', '')
            metadata['first_name'] = oauth_user_info.get('first_name', '')
            metadata['last_name'] = oauth_user_info.get('last_name', '')
            metadata['username'] = oauth_user_info.get('email', '').split('@')[0]
            metadata['email_verified'] = 'true'  # OAuth emails are pre-verified

        # Add referral/promo codes
        if referral_code:
            metadata['referral_code'] = referral_code
        if promo_code:
            metadata['promo_code'] = promo_code

        detected_timezone = request.form.get('detected_timezone')

        try:
            pending_signup = SignupService.create_pending_signup_record(
                tier=tier_obj,
                email=contact_email,
                phone=contact_phone or None,
                signup_source=signup_source,
                referral_code=referral_code,
                promo_code=promo_code,
                detected_timezone=detected_timezone,
                oauth_user_info=oauth_user_info,
                extra_metadata={'preselected_tier': selected_tier, **metadata}
            )
        except Exception as exc:
            logger.error("Failed to create pending signup: %s", exc)
            flash('Unable to start checkout right now. Please try again later.', 'error')
            return render_template('pages/auth/signup.html',
                         signup_source=signup_source,
                         referral_code=referral_code,
                         promo_code=promo_code,
                         available_tiers=available_tiers,
                         oauth_user_info=oauth_user_info,
                         contact_email=contact_email,
                         contact_phone=contact_phone)

        metadata['pending_signup_id'] = str(pending_signup.id)

        success_url = url_for('billing.complete_signup_from_stripe', _external=True) + '?session_id={CHECKOUT_SESSION_ID}'
        cancel_url = url_for('auth.signup', _external=True)

        stripe_session = BillingService.create_checkout_session_for_tier(
            tier_obj,
            customer_email=contact_email or None,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
            client_reference_id=str(pending_signup.id),
        )

        if stripe_session:
            pending_signup.stripe_checkout_session_id = stripe_session.id
            pending_signup.mark_status('checkout_created')
            db.session.commit()
            return redirect(stripe_session.url)
        else:
            pending_signup.mark_status('failed', error='session_creation_failed')
            db.session.commit()
            flash('Payment system temporarily unavailable. Please try again later.', 'error')

    # Choose a default tier id for UI selection (first available)
    default_tier_id = str(db_tiers[0].id) if db_tiers else ''

    return render_template('pages/auth/signup.html',
                         signup_source=signup_source,
                         referral_code=referral_code,
                         promo_code=promo_code,
                         available_tiers=available_tiers,
                         oauth_user_info=oauth_user_info,
                         oauth_available=OAuthService.is_oauth_configured(),
                         preselected_tier=preselected_tier,
                         default_tier_id=default_tier_id,
                         contact_email=prefill_email,
                         contact_phone=prefill_phone)

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
        SessionService.rotate_user_session(user)
        user.last_login = TimezoneUtils.utc_now()
        db.session.commit()
        flash('Successfully logged in with Whop license.', 'success')
        return redirect(url_for('app_routes.dashboard'))
    else:
        flash('Invalid license key or access denied.', 'error')
        return redirect(url_for('auth.login'))

# Permission and Role Management Routes have been moved to organization blueprint