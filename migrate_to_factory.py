
#!/usr/bin/env python3
"""
Migration script to refactor BatchTrack to application factory pattern
This script will:
1. Create the new app/ package structure
2. Move and update all files with correct imports
3. Preserve all functionality while modernizing structure
"""

import os
import shutil
import re
from pathlib import Path

def create_directory_structure():
    """Create the new app package directory structure"""
    dirs_to_create = [
        'app',
        'app/models',
        'app/blueprints',
        'app/blueprints/auth',
        'app/services',
        'app/utils',
        'app/templates',
        'app/static'
    ]
    
    for dir_path in dirs_to_create:
        os.makedirs(dir_path, exist_ok=True)
        print(f"Created directory: {dir_path}")

def create_app_init():
    """Create the main app factory in app/__init__.py"""
    content = '''from flask import Flask
from flask_migrate import Migrate

def create_app(config_name='default'):
    """Application factory pattern"""
    app = Flask(__name__, 
                static_folder='static', 
                static_url_path='/static',
                template_folder='templates')
    
    # Load configuration
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'devkey-please-change-in-production')
    
    # Ensure directories exist with proper permissions
    instance_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'instance')
    os.makedirs(instance_path, exist_ok=True)
    os.makedirs('static/product_images', exist_ok=True)
    os.chmod(instance_path, 0o777)  # Ensure write permissions

    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(instance_path, 'new_batchtrack.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = 'static/product_images'
    
    # Add URL rule for data files
    app.add_url_rule('/data/<path:filename>', endpoint='data', view_func=app.send_static_file)
    
    # Initialize extensions
    from .extensions import db, login_manager, csrf, migrate
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    # Import models to ensure they're registered
    from . import models
    
    # Setup logging
    from .utils.unit_utils import setup_logging
    setup_logging(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Register context processors and filters
    register_context_processors(app)
    register_filters(app)
    
    return app

def register_blueprints(app):
    """Register all application blueprints"""
    # Auth blueprint
    from .blueprints.auth import auth_bp
    app.register_blueprint(auth_bp)
    
    # Existing blueprints - move to app/blueprints
    from .blueprints.batches import batches_bp, start_batch_bp, finish_batch_bp, cancel_batch_bp, add_extra_bp
    from .blueprints.inventory.routes import inventory_bp
    from .blueprints.recipes.routes import recipes_bp
    from .blueprints.conversion.routes import conversion_bp
    from .blueprints.settings.routes import settings_bp
    from .blueprints.quick_add.routes import quick_add_bp
    from .blueprints.fifo import fifo_bp
    from .blueprints.expiration.routes import expiration_bp
    from .blueprints.timers import timers_bp
    
    # Routes that will be moved to app/routes
    from .routes.bulk_stock_routes import bulk_stock_bp
    from .routes.fault_log_routes import faults_bp
    from .routes.product_log_routes import product_log_bp
    from .routes.tag_manager_routes import tag_bp
    from .routes.products import products_bp
    from .routes.product_variants import product_variants_bp
    from .routes.product_inventory import product_inventory_bp
    from .routes.product_api import product_api_bp
    from .routes.admin_routes import admin_bp
    from .routes.app_routes import app_routes_bp
    
    # Register all blueprints
    app.register_blueprint(fifo_bp)
    app.register_blueprint(expiration_bp)
    app.register_blueprint(conversion_bp, url_prefix='/conversion')
    app.register_blueprint(quick_add_bp, url_prefix='/quick-add')
    app.register_blueprint(products_bp)
    app.register_blueprint(product_variants_bp)
    app.register_blueprint(product_inventory_bp)
    app.register_blueprint(product_api_bp)
    app.register_blueprint(settings_bp, url_prefix='/settings')
    app.register_blueprint(app_routes_bp)
    app.register_blueprint(batches_bp, url_prefix='/batches')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(recipes_bp, url_prefix='/recipes')
    app.register_blueprint(bulk_stock_bp, url_prefix='/stock')
    app.register_blueprint(faults_bp, url_prefix='/logs')
    app.register_blueprint(product_log_bp, url_prefix='/product-logs')
    app.register_blueprint(tag_bp, url_prefix='/tags')
    app.register_blueprint(timers_bp, url_prefix='/timers')
    app.register_blueprint(start_batch_bp, url_prefix='/start-batch')
    app.register_blueprint(finish_batch_bp, url_prefix='/finish-batch')
    app.register_blueprint(cancel_batch_bp, url_prefix='/cancel')
    app.register_blueprint(add_extra_bp, url_prefix='/add-extra')
    
    # Initialize API routes
    from .blueprints.api import init_api
    init_api(app)

def register_context_processors(app):
    """Register template context processors"""
    from .models import Unit, IngredientCategory
    
    @app.context_processor
    def inject_units():
        units = Unit.query.order_by(Unit.type, Unit.name).all()
        categories = IngredientCategory.query.order_by(IngredientCategory.name).all()
        return dict(units=units, categories=categories)

    @app.context_processor
    def inject_permissions():
        from .utils.permissions import has_permission, has_role
        return dict(has_permission=has_permission, has_role=has_role)

def register_filters(app):
    """Register custom template filters"""
    from .filters.product_filters import register_product_filters
    register_product_filters(app)
    
    @app.template_filter('attr_multiply')
    def attr_multiply_filter(item, attr1, attr2):
        """Multiply two attributes of a single item"""
        if item is None:
            return 0

        val1 = getattr(item, attr1, 0)
        val2 = getattr(item, attr2, 0)

        if val1 is None:
            val1 = 0
        if val2 is None:
            val2 = 0

        return float(val1) * float(val2)

import os
'''
    
    with open('app/__init__.py', 'w') as f:
        f.write(content)
    print("Created app/__init__.py with factory pattern")

def create_extensions():
    """Create extensions.py to prevent circular imports"""
    content = '''"""
Flask extensions initialization
Prevents circular imports by centralizing extension definitions
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

# Create extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

@login_manager.user_loader
def load_user(user_id):
    from .models.user import User
    return db.session.get(User, int(user_id))
'''
    
    with open('app/extensions.py', 'w') as f:
        f.write(content)
    print("Created app/extensions.py")

def create_auth_blueprint():
    """Create the new auth blueprint"""
    # Create auth blueprint __init__.py
    auth_init = '''from flask import Blueprint

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

from . import routes
'''
    
    with open('app/blueprints/auth/__init__.py', 'w') as f:
        f.write(auth_init)
    
    # Create auth routes
    auth_routes = '''from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from flask_wtf import FlaskForm
from werkzeug.security import generate_password_hash
from . import auth_bp
from ..extensions import db
from ..models.user import User

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
        
    form = FlaskForm()
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

            # Create new user
            new_user = User(
                username=username,
                password_hash=generate_password_hash(password),
                role='user'
            )
            db.session.add(new_user)
            db.session.commit()

            flash('Account created successfully! Please log in.')
            return render_template('auth/login.html', form=form)

        else:
            # Handle login
            u = User.query.filter_by(username=username).first()
            if u and u.check_password(password):
                login_user(u)
                return redirect(url_for('dashboard.dashboard'))
            flash('Invalid credentials')

    return render_template('auth/login.html', form=form)

@auth_bp.route('/dev-login')
def dev_login():
    # Placeholder for future dev login page
    flash('Developer login coming soon!')
    return redirect(url_for('auth.login'))

@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
'''
    
    with open('app/blueprints/auth/routes.py', 'w') as f:
        f.write(auth_routes)
    
    print("Created auth blueprint")

def move_models():
    """Split models.py into modular files in app/models/"""
    # For now, copy the existing models.py and create an __init__.py that imports everything
    shutil.copy('models.py', 'app/models/models.py')
    
    models_init = '''"""
Models package - imports all models for the application
"""
from .models import *
'''
    
    with open('app/models/__init__.py', 'w') as f:
        f.write(models_init)
    
    print("Moved models to app/models/")

def move_existing_blueprints():
    """Move existing blueprints to app/blueprints/"""
    blueprint_dirs = ['batches', 'conversion', 'expiration', 'fifo', 'inventory', 
                     'products', 'quick_add', 'recipes', 'settings', 'timers', 'api']
    
    for bp_dir in blueprint_dirs:
        src_path = f'blueprints/{bp_dir}'
        dest_path = f'app/blueprints/{bp_dir}'
        
        if os.path.exists(src_path):
            shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
            print(f"Moved {src_path} to {dest_path}")

def move_other_modules():
    """Move services, utils, filters, routes to app/"""
    modules_to_move = [
        ('services', 'app/services'),
        ('utils', 'app/utils'),
        ('filters', 'app/filters'),
        ('routes', 'app/routes'),
        ('templates', 'app/templates'),
        ('static', 'app/static')
    ]
    
    for src, dest in modules_to_move:
        if os.path.exists(src):
            shutil.copytree(src, dest, dirs_exist_ok=True)
            print(f"Moved {src} to {dest}")

def create_run_file():
    """Create run.py at root level"""
    content = '''#!/usr/bin/env python3
"""
Application entry point using factory pattern
"""
import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
'''
    
    with open('run.py', 'w') as f:
        f.write(content)
    print("Created run.py entry point")

def update_imports_in_app():
    """Update all imports within the app package to use relative imports"""
    # This is a placeholder - in practice you'd want to recursively update imports
    print("Import updates will need manual review - check for:")
    print("- Change 'from models import' to 'from ..models import' or 'from .models import'")
    print("- Change 'from services.' to 'from ..services.' or 'from .services.'")
    print("- Update any absolute imports to relative imports within app package")

def create_auth_template_dir():
    """Create auth template directory and move login template"""
    os.makedirs('app/templates/auth', exist_ok=True)
    if os.path.exists('templates/login.html'):
        shutil.copy('templates/login.html', 'app/templates/auth/login.html')
        print("Moved login template to auth directory")

def main():
    """Run the migration"""
    print("🚀 Starting BatchTrack factory pattern migration...")
    
    print("\n1. Creating directory structure...")
    create_directory_structure()
    
    print("\n2. Creating app factory...")
    create_app_init()
    
    print("\n3. Creating extensions module...")
    create_extensions()
    
    print("\n4. Creating auth blueprint...")
    create_auth_blueprint()
    
    print("\n5. Moving models...")
    move_models()
    
    print("\n6. Moving existing blueprints...")
    move_existing_blueprints()
    
    print("\n7. Moving other modules...")
    move_other_modules()
    
    print("\n8. Creating run.py...")
    create_run_file()
    
    print("\n9. Creating auth templates...")
    create_auth_template_dir()
    
    print("\n10. Import updates needed...")
    update_imports_in_app()
    
    print("\n✅ Migration complete!")
    print("\n📋 Manual steps needed:")
    print("1. Update Flask-Login imports in moved files")
    print("2. Update all 'from models import' to relative imports")
    print("3. Update blueprint registrations to use new auth.login")
    print("4. Test with: python run.py")
    print("5. Update workflow to use 'python run.py' instead of 'flask run'")

if __name__ == '__main__':
    main()
