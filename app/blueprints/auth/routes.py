from flask import render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_user, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired
from werkzeug.security import generate_password_hash
from . import auth_bp
from ...extensions import db
from ...models import User, Organization, Role
from ...utils.timezone_utils import TimezoneUtils
from ...utils.permissions import require_permission
from flask_login import login_required
import logging

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

    return render_template('auth/login.html', form=form)

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

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """Production signup flow - collect user info then redirect to Stripe payment"""
    if current_user.is_authenticated:
        return redirect(url_for('app_routes.dashboard'))

    # Get pricing data for customer-facing tiers only
    from ...services.pricing_service import PricingService
    from ...blueprints.developer.subscription_tiers import load_tiers_config
    
    pricing_data = PricingService.get_pricing_data()
    tiers_config = load_tiers_config()

    # Only show customer-facing tiers with proper Stripe configuration
    available_tiers = {}
    for tier_key, tier_data in pricing_data.items():
        tier_config = tiers_config.get(tier_key, {})
        if (tier_config.get('is_customer_facing', True) and 
            tier_config.get('is_available', True) and 
            tier_config.get('stripe_lookup_key')):
            
            price_str = tier_data.get('price', '$0').replace('$', '')
            try:
                price_monthly = float(price_str) if price_str.replace('.', '').isdigit() else 0
            except (ValueError, AttributeError):
                price_monthly = 0
            
            available_tiers[tier_key] = {
                'name': tier_data.get('name', tier_key.title()),
                'price_monthly': price_monthly,
                'price_display': tier_data.get('price', '$0'),
                'price_yearly': tier_data.get('price_yearly', '$0'),
                'features': tier_data.get('features', []),
                'user_limit': tier_data.get('user_limit', 1),
                'stripe_lookup_key': tier_config.get('stripe_lookup_key', '')
            }

    # Get signup tracking parameters
    signup_source = request.args.get('source', request.form.get('source', 'direct'))
    referral_code = request.args.get('ref', request.form.get('ref'))
    promo_code = request.args.get('promo', request.form.get('promo'))

    if request.method == 'POST':
        # Extract form data
        org_name = request.form.get('org_name')
        username = request.form.get('username')
        email = request.form.get('email')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        phone = request.form.get('phone')
        selected_tier = request.form.get('subscription_tier')

        # Validation
        required_fields = [org_name, username, email, password, confirm_password, selected_tier]
        if not all(required_fields):
            flash('Please fill in all required fields and select a subscription plan', 'error')
            return render_template('auth/signup.html', 
                         signup_source=signup_source,
                         referral_code=referral_code,
                         promo_code=promo_code,
                         available_tiers=available_tiers,
                         form_data=request.form)

        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('auth/signup.html', 
                         signup_source=signup_source,
                         referral_code=referral_code,
                         promo_code=promo_code,
                         available_tiers=available_tiers,
                         form_data=request.form)

        if selected_tier not in available_tiers:
            flash('Invalid subscription plan selected', 'error')
            return render_template('auth/signup.html', 
                         signup_source=signup_source,
                         referral_code=referral_code,
                         promo_code=promo_code,
                         available_tiers=available_tiers,
                         form_data=request.form)

        # Check for existing users
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        if existing_user:
            flash('Username or email already exists', 'error')
            return render_template('auth/signup.html', 
                         signup_source=signup_source,
                         referral_code=referral_code,
                         promo_code=promo_code,
                         available_tiers=available_tiers,
                         form_data=request.form)

        # Check if tier is Stripe-ready before proceeding
        from ...blueprints.developer.subscription_tiers import load_tiers_config
        tiers_config = load_tiers_config()
        tier_data = tiers_config.get(selected_tier, {})
        is_stripe_ready = tier_data.get('is_stripe_ready', False)

        # Store signup data for post-payment completion
        session['pending_signup'] = {
            'org_name': org_name,
            'username': username,
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'password': password,
            'phone': phone,
            'selected_tier': selected_tier,
            'signup_source': signup_source,
            'promo_code': promo_code,
            'referral_code': referral_code
        }

        # Check if we should use Stripe or development mode
        if is_stripe_ready and current_app.config.get('STRIPE_SECRET_KEY'):
            # Stripe is configured and tier is ready - use real payment
            return redirect(url_for('billing.checkout', tier=selected_tier))
        else:
            # Development mode or tier not Stripe-ready - simulate signup completion
            from ...blueprints.billing.routes import complete_signup_dev_mode
            return complete_signup_dev_mode(selected_tier, is_stripe_mode=False)

    return render_template('auth/signup.html', 
                         signup_source=signup_source,
                         referral_code=referral_code,
                         promo_code=promo_code,
                         available_tiers=available_tiers)

@auth_bp.route('/complete-signup')
@login_required
def complete_signup():
    """Complete signup after successful Stripe payment"""
    # This route will be called by the billing system after successful payment
    # The user should already be logged in with a temporary account
    # and the organization should be created with the proper tier

    # Clear any pending signup data
    session.pop('pending_signup', None)

    flash('Welcome! Your account has been successfully created.', 'success')
    return redirect(url_for('app_routes.dashboard'))

# Permission and Role Management Routes
from .permissions import manage_permissions, manage_roles, create_role, update_role, toggle_permission_status

@auth_bp.route('/permissions')
@require_permission('dev.system_admin')
def permissions():
    return manage_permissions()

@auth_bp.route('/permissions/toggle-status', methods=['POST'])
@require_permission('dev.system_admin')
def toggle_permission_status_route():
    return toggle_permission_status()

@auth_bp.route('/roles')
@require_permission('organization.manage_roles')
def roles():
    return manage_roles()

@auth_bp.route('/roles', methods=['POST'])
@require_permission('organization.manage_roles')
def create_role_route():
    return create_role()

@auth_bp.route('/roles/<int:role_id>', methods=['PUT'])
@require_permission('organization.manage_roles')
def update_role_route(role_id):
    return update_role(role_id)

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