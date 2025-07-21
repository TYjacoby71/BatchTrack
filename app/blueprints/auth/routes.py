from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired
from werkzeug.security import generate_password_hash
from . import auth_bp
from ...extensions import db
from ...models import User, Organization
from ...utils.timezone_utils import TimezoneUtils
from flask_login import login_required

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
        form_type = request.form.get('form_type')
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Please provide both username and password')
            return render_template('auth/login.html', form=form)

        if form_type == 'register':
            # Handle registration
            confirm_password = request.form.get('confirm_password')

            if password != confirm_password:
                flash('Passwords do not match')
                return render_template('auth/login.html', form=form)

            # Check if username already exists
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                flash('Username already exists')
                return render_template('auth/login.html', form=form)

            # Get email from form if provided
            email = request.form.get('email', '').strip()

            # Create organization for new user
            new_org = Organization(
                name=f"{username}'s Organization",
                contact_email=email if email else None  # Set organization email to user's email
            )
            db.session.add(new_org)
            db.session.flush()  # Get the ID

            # Create new user as organization owner
            new_user = User(
                username=username,
                email=email if email else None,  # Set user email
                organization_id=new_org.id,
                user_type='organization_owner',  # Use user_type instead of role
                is_active=True
            )
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()

            flash('Account created successfully! Please log in.')
            return render_template('auth/login.html', form=form)

        else:
            # Handle login
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
    """Public signup route with trial and billing support"""
    if current_user.is_authenticated:
        return redirect(url_for('app_routes.dashboard'))

    # Get signup source and offer details from query parameters
    signup_source = request.args.get('source', 'direct')
    referral_code = request.args.get('ref')
    promo_code = request.args.get('promo')

    # Determine trial offer based on source
    trial_offers = {
        'homepage_trial': {'days': 14, 'name': 'Free Trial', 'requires_billing': True},
        'webinar': {'days': 30, 'name': 'Webinar Special', 'requires_billing': True},
        'demo_request': {'days': 21, 'name': 'Demo Trial', 'requires_billing': True},
        'partner': {'days': 30, 'name': 'Partner Offer', 'requires_billing': True},
        'direct': {'days': 14, 'name': 'Free Trial', 'requires_billing': True}
    }
    
    current_offer = trial_offers.get(signup_source, trial_offers['direct'])

    if request.method == 'POST':
        # Organization details
        org_name = request.form.get('org_name')

        # User details
        username = request.form.get('username')
        email = request.form.get('email')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        phone = request.form.get('phone')
        
        # Billing details (required for trial)
        card_number = request.form.get('card_number', '').replace(' ', '').replace('-', '')
        card_exp_month = request.form.get('card_exp_month')
        card_exp_year = request.form.get('card_exp_year')
        card_cvc = request.form.get('card_cvc')
        billing_name = request.form.get('billing_name')
        billing_address = request.form.get('billing_address')
        billing_city = request.form.get('billing_city')
        billing_state = request.form.get('billing_state')
        billing_zip = request.form.get('billing_zip')
        billing_country = request.form.get('billing_country')
        
        # Promo code
        entered_promo = request.form.get('promo_code', '').strip().upper()

        # Basic validation
        required_fields = [org_name, username, email, password, confirm_password]
        if current_offer['requires_billing']:
            required_fields.extend([card_number, card_exp_month, card_exp_year, card_cvc, billing_name])

        if not all(required_fields):
            flash('Please fill in all required fields', 'error')
            return render_template('auth/signup.html', 
                         signup_source=signup_source,
                         referral_code=referral_code,
                         promo_code=promo_code,
                         current_offer=current_offer,
                         form_data=request.form)

        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('auth/signup.html', 
                         signup_source=signup_source,
                         referral_code=referral_code,
                         promo_code=promo_code,
                         current_offer=current_offer,
                         form_data=request.form)

        # Check if username/email already exists
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        if existing_user:
            flash('Username or email already exists', 'error')
            return render_template('auth/signup.html', 
                         signup_source=signup_source,
                         referral_code=referral_code,
                         promo_code=promo_code,
                         current_offer=current_offer,
                         form_data=request.form)

        # Validate card details (basic validation)
        if current_offer['requires_billing']:
            if not _validate_credit_card(card_number, card_exp_month, card_exp_year, card_cvc):
                flash('Please enter valid payment information', 'error')
                return render_template('auth/signup.html', 
                             signup_source=signup_source,
                             referral_code=referral_code,
                             promo_code=promo_code,
                             current_offer=current_offer,
                             form_data=request.form)

        # Validate and apply promo code
        promo_discount = _validate_promo_code(entered_promo, signup_source)
        if entered_promo and not promo_discount:
            flash('Invalid promo code', 'error')
            return render_template('auth/signup.html', 
                         signup_source=signup_source,
                         referral_code=referral_code,
                         promo_code=promo_code,
                         current_offer=current_offer,
                         form_data=request.form)

        try:
            from datetime import datetime, timedelta
            
            # Create organization with trial details
            trial_end_date = datetime.utcnow() + timedelta(days=current_offer['days'])
            
            org = Organization(
                name=org_name,
                subscription_tier='trial',  # Start with trial
                contact_email=email,
                is_active=True,
                trial_end_date=trial_end_date,
                signup_source=signup_source,
                promo_code=entered_promo if entered_promo else None,
                referral_code=referral_code,
                # Billing will be handled by Stripe - no local storage needed
            )
            db.session.add(org)
            db.session.flush()  # Get the ID

            # Create organization owner user
            owner_user = User(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                organization_id=org.id,
                user_type='organization_owner',
                is_active=True
            )
            owner_user.set_password(password)
            db.session.add(owner_user)
            
            # Create trial subscription
            from ...services.subscription_service import SubscriptionService
            SubscriptionService.create_trial_subscription(
                organization=org,
                trial_days=30,
                trial_tier='team'
            )
            
            db.session.commit()

            flash(f'Welcome! Your {current_offer["days"]}-day free trial has started. No charges until {trial_end_date.strftime("%B %d, %Y")}.', 'success')
            return redirect(url_for('auth.login'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error creating account: {str(e)}', 'error')
            return render_template('auth/signup.html', 
                         signup_source=signup_source,
                         referral_code=referral_code,
                         promo_code=promo_code,
                         current_offer=current_offer,
                         form_data=request.form)

    return render_template('auth/signup.html', 
                         signup_source=signup_source,
                         referral_code=referral_code,
                         promo_code=promo_code,
                         current_offer=current_offer)

def _validate_credit_card(card_number, exp_month, exp_year, cvc):
    """Basic credit card validation"""
    if not card_number or len(card_number) < 13 or len(card_number) > 19:
        return False
    if not card_number.isdigit():
        return False
    if not exp_month or not exp_year or not cvc:
        return False
    if not (1 <= int(exp_month) <= 12):
        return False
    if len(cvc) < 3 or len(cvc) > 4:
        return False
    
    # Luhn algorithm for card validation
    def luhn_checksum(card_num):
        def digits_of(n):
            return [int(d) for d in str(n)]
        digits = digits_of(card_num)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum(digits_of(d*2))
        return checksum % 10
    
    return luhn_checksum(card_number) == 0

def _validate_promo_code(promo_code, signup_source):
    """Validate promo codes and return discount info"""
    if not promo_code:
        return None
        
    # Define available promo codes
    promo_codes = {
        'WELCOME20': {'discount_percent': 20, 'valid_for_months': 3, 'description': '20% off for 3 months'},
        'TRIAL30': {'discount_percent': 30, 'valid_for_months': 1, 'description': '30% off first month'},
        'WEBINAR50': {'discount_percent': 50, 'valid_for_months': 2, 'description': '50% off first 2 months'},
        'PARTNER25': {'discount_percent': 25, 'valid_for_months': 6, 'description': '25% off for 6 months'}
    }
    
    # Source-specific promo validation
    source_promos = {
        'webinar': ['WEBINAR50', 'WELCOME20'],
        'partner': ['PARTNER25', 'WELCOME20'],
        'homepage_trial': ['WELCOME20', 'TRIAL30']
    }
    
    if promo_code in promo_codes:
        # Check if promo is valid for this signup source
        valid_promos = source_promos.get(signup_source, list(promo_codes.keys()))
        if promo_code in valid_promos:
            return promo_codes[promo_code]
    
    return None

# Multiple Signup Entry Points
@auth_bp.route('/free-trial')
def free_trial():
    """Homepage free trial signup entry point"""
    return redirect(url_for('auth.signup', source='homepage_trial'))

@auth_bp.route('/webinar-signup')
def webinar_signup():
    """Webinar signup entry point"""
    return redirect(url_for('auth.signup', source='webinar'))

@auth_bp.route('/partner-signup/<partner_code>')
def partner_signup(partner_code):
    """Partner/affiliate signup entry point"""
    return redirect(url_for('auth.signup', source='partner', ref=partner_code))

@auth_bp.route('/demo-signup')
def demo_signup():
    """Demo request signup entry point"""
    return redirect(url_for('auth.signup', source='demo_request'))

# Permission and Role Management Routes
from .permissions import manage_permissions, manage_roles, create_role, update_role

@auth_bp.route('/permissions')
def permissions():
    return manage_permissions()

@auth_bp.route('/roles')
def roles():
    return manage_roles()

@auth_bp.route('/roles', methods=['POST'])
def create_role_route():
    return create_role()

@auth_bp.route('/roles/<int:role_id>', methods=['PUT'])
def update_role_route(role_id):
    return update_role(role_id)

@auth_bp.route('/roles/<int:role_id>')
@login_required
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