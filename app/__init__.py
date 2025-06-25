from flask import Flask, render_template, request, redirect, url_for, flash
from flask_migrate import Migrate
import os

def register_blueprints(app):
    """Register all application blueprints directly"""
    # Core blueprints
    from .blueprints.auth import auth_bp
    from .blueprints.inventory.routes import inventory_bp
    from .blueprints.recipes.routes import recipes_bp
    from .blueprints.batches import batches_bp
    from .blueprints.conversion.routes import conversion_bp
    from .blueprints.expiration.routes import expiration_bp
    from .blueprints.quick_add.routes import quick_add_bp
    from .blueprints.settings.routes import settings_bp
    from .blueprints.timers import timers_bp
    from .blueprints.fifo import fifo_bp

    # Route blueprints
    from .routes.app_routes import app_routes_bp
    from .blueprints.admin.admin_routes import admin_bp
    from .routes.bulk_stock_routes import bulk_stock_bp
    from .routes.fault_log_routes import fault_log_bp
    from .routes.tag_manager_routes import tag_manager_bp

    # Special blueprints
    from .blueprints.batches.add_extra import add_extra_bp

    # Register all blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(recipes_bp, url_prefix='/recipes')
    app.register_blueprint(batches_bp, url_prefix='/batches')
    app.register_blueprint(conversion_bp, url_prefix='/conversion')
    app.register_blueprint(expiration_bp, url_prefix='/expiration')
    app.register_blueprint(quick_add_bp, url_prefix='/quick_add')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    app.register_blueprint(timers_bp, url_prefix='/timers')
    app.register_blueprint(fifo_bp)
    app.register_blueprint(app_routes_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(bulk_stock_bp, url_prefix='/bulk_stock')
    app.register_blueprint(fault_log_bp, url_prefix='/fault_log')
    app.register_blueprint(tag_manager_bp, url_prefix='/tag_manager')
    app.register_blueprint(add_extra_bp, url_prefix='/add-extra')

    # Register product blueprints
    from .blueprints.products import register_product_blueprints
    register_product_blueprints(app)

    # Register API blueprints
    from .blueprints.api.routes import register_api_routes
    register_api_routes(app)

def create_app(config_filename=None):
    app = Flask(__name__, static_folder='static', static_url_path='/static')

    # Add custom URL rule for data files
    app.add_url_rule('/data/<path:filename>', endpoint='data', view_func=app.send_static_file)

    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'devkey-please-change-in-production')

    # Ensure directories exist with proper permissions
    instance_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'instance')
    os.makedirs(instance_path, exist_ok=True)
    os.makedirs('static/product_images', exist_ok=True)
    os.chmod(instance_path, 0o777)

    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(instance_path, 'new_batchtrack.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = 'static/product_images'

    # Load additional config if provided
    if config_filename:
        app.config.from_pyfile(config_filename)

    # Initialize extensions
    from .extensions import db, login_manager, migrate, csrf, bcrypt
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    migrate.init_app(app, db)
    csrf.init_app(app)
    bcrypt.init_app(app)

    # Import models to ensure they're registered
    from . import models
    from .models import User, Unit, IngredientCategory

    # Setup logging
    from .utils.unit_utils import setup_logging
    setup_logging(app)

    # Register blueprints
    register_blueprints(app)

    # Register legacy blueprints that still exist (excluding products which are handled above)
    legacy_blueprints = [
        # add_extra_bp is now handled by blueprint_registry
        # ('.blueprints.batches.add_extra', 'add_extra_bp', '/add-extra'),
        # fifo_bp is now handled by blueprint_registry
        # ('.blueprints.fifo', 'fifo_bp', None),
    ]

    # Legacy blueprints are now all handled by blueprint_registry
    if legacy_blueprints:  # Only run if there are actually legacy blueprints to register
        for module_path, bp_name, url_prefix in legacy_blueprints:
            try:
                module = __import__(f'app{module_path}', fromlist=[bp_name])
                blueprint = getattr(module, bp_name)
                if url_prefix:
                    app.register_blueprint(blueprint, url_prefix=url_prefix)
                else:
                    app.register_blueprint(blueprint)
            except (ImportError, AttributeError) as e:
                print(f"Warning: Could not import {module_path}.{bp_name}: {e}")

    # Initialize API routes
    try:
        from .blueprints.api import init_api
        init_api(app)
    except ImportError:
        pass

    # Register filters
    from .filters.product_filters import register_filters
    register_filters(app)

    # Using standard Flask url_for - no custom template registry needed

    # Add custom template filters
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

    # Context processors
    @app.context_processor
    def inject_units():
        units = Unit.query.order_by(Unit.type, Unit.name).all()
        categories = IngredientCategory.query.order_by(IngredientCategory.name).all()
        return dict(units=units, categories=categories)

    @app.context_processor
    def inject_permissions():
        try:
            from .utils.permissions import has_permission, has_role
            return dict(has_permission=has_permission, has_role=has_role)
        except ImportError:
            return dict(has_permission=lambda x: True, has_role=lambda x: True)

    # User loader
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Add main routes
    @app.route('/')
    def index():
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for('app_routes.dashboard'))
        return redirect(url_for('homepage'))

    @app.route('/homepage')
    def homepage():
        return render_template('homepage.html')

    # Seeders are available via CLI commands: flask seed-all, flask init-db
    # No automatic seeding on startup to improve performance

    # Register permission template functions
    from .utils.permissions import has_permission, has_role, has_subscription_feature, is_organization_owner, is_developer
    app.jinja_env.globals.update(
        has_permission=has_permission,
        has_role=has_role,
        has_subscription_feature=has_subscription_feature,
        is_organization_owner=is_organization_owner,
        is_developer=is_developer
    )

    # Add units to global context for dropdowns
    @app.context_processor
    def inject_units():
        from .models import Unit
        try:
            # Get all units, filtering by is_active if the column exists
            units = Unit.query.filter(
                db.or_(Unit.is_active == True, Unit.is_active.is_(None))
            ).order_by(Unit.type, Unit.name).all()
            return dict(global_units=units)
        except:
            # Fallback to all units if filtering fails
            try:
                units = Unit.query.order_by(Unit.type, Unit.name).all()
                return dict(global_units=units)
            except:
                return dict(global_units=[])

    # Register CLI commands
    from .management import register_commands
    register_commands(app)

    return app