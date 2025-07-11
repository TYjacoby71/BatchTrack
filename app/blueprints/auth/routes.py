
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

            # Create organization for new user
            new_org = Organization(name=f"{username}'s Organization")
            db.session.add(new_org)
            db.session.flush()  # Get the ID

            # Create new user as organization owner
            new_user = User(
                username=username,
                organization_id=new_org.id,
                role='organization_owner',
                is_owner=True  # First user in organization is always the owner
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
                
                # Update last login
                user.last_login = TimezoneUtils.utc_now()
                db.session.commit()
                
                login_user(user, remember=True)
                flash('Login successful!', 'success')
                
                # Check for next parameter or redirect to dashboard
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
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
        return redirect(url_for('app_routes.dashboard'))
    else:
        flash('Developer account not found. Please contact system administrator.', 'error')
        return redirect(url_for('auth.login'))
