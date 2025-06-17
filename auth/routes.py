
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from werkzeug.security import generate_password_hash
from extensions import db
from models import User
from . import auth_bp

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = FlaskForm()
    if request.method == 'POST' and form.validate_on_submit():
        form_type = request.form.get('form_type')
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Please provide both username and password')
            return render_template('login.html', form=form)

        if form_type == 'register':
            # Handle registration
            confirm_password = request.form.get('confirm_password')

            if password != confirm_password:
                flash('Passwords do not match')
                return render_template('login.html', form=form)

            # Check if username already exists
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                flash('Username already exists')
                return render_template('login.html', form=form)

            # Create new user
            new_user = User(
                username=username,
                password_hash=generate_password_hash(password),
                role='user'
            )
            db.session.add(new_user)
            db.session.commit()

            flash('Account created successfully! Please log in.')
            return render_template('login.html', form=form)

        else:
            # Handle login
            u = User.query.filter_by(username=username).first()
            if u and u.check_password(password):
                login_user(u)
                return redirect(url_for('dashboard.dashboard'))
            flash('Invalid credentials')

    return render_template('login.html', form=form)

@auth_bp.route('/dev-login')
def dev_login():
    flash('Developer login coming soon!')
    return redirect(url_for('auth.login'))

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
