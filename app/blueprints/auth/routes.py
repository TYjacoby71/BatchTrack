from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired
from werkzeug.security import generate_password_hash
from . import auth_bp
from ...extensions import db
from ...models import User, Organization, Role
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

        # Handle login only (registration removed - use dedicated signup flow)
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
    """Public signup route - auth only, billing handled by subscription service"""
    if current_user.is_authenticated:
        return redirect(url_for('app_routes.dashboard'))

    # Get signup tracking parameters
    signup_source = request.args.get('source', 'direct')
    referral_code = request.args.get('ref')
    promo_code = request.args.get('promo')

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

        # Basic validation only
        required_fields = [org_name, username, email, password, confirm_password]
        if not all(required_fields):
            flash('Please fill in all required fields', 'error')
            return render_template('auth/signup.html', 
                         signup_source=signup_source,
                         referral_code=referral_code,
                         promo_code=promo_code,
                         form_data=request.form)

        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('auth/signup.html', 
                         signup_source=signup_source,
                         referral_code=referral_code,
                         promo_code=promo_code,
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
                         form_data=request.form)

        try:
            # Create organization (starts on free tier)
            org = Organization(
                name=org_name,
                subscription_tier='free',  # Start on free tier
                contact_email=email,
                is_active=True,
                signup_source=signup_source,
                promo_code=promo_code if promo_code else None,
                referral_code=referral_code
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
                user_type='customer',
                is_organization_owner=True,
                is_active=True
            )
            owner_user.set_password(password)
            db.session.add(owner_user)
            db.session.flush()  # Get the ID

            # Assign organization owner role
            org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
            if org_owner_role:
                owner_user.assign_role(org_owner_role)

            db.session.commit()

            flash('Account created successfully! You can upgrade to unlock more features.', 'success')
            return redirect(url_for('auth.login'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error creating account: {str(e)}', 'error')
            return render_template('auth/signup.html', 
                         signup_source=signup_source,
                         referral_code=referral_code,
                         promo_code=promo_code,
                         form_data=request.form)

    return render_template('auth/signup.html', 
                         signup_source=signup_source,
                         referral_code=referral_code,
                         promo_code=promo_code)





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