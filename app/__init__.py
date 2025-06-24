from flask import Flask, render_template, request, redirect, url_for, flash
from flask_migrate import Migrate
import os

def register_blueprints(app):
    """Register all application blueprints using centralized registry"""
    from .blueprint_registry import blueprint_registry
    blueprint_registry.register_all_blueprints(app)

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

    # Register template registry for safe URL generation
    from .template_registry import template_registry
    template_registry.register_template_functions(app)

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

    # Run all seeders
    try:
        from .seeders import seed_units, seed_categories, seed_users

        seed_units()
        seed_categories()
        seed_users()

        app.logger.info("✅ All seeders completed successfully")
    except Exception as e:
        app.logger.error(f"❌ Seeder error: {e}")
        # Don't fail startup, just log the error

    return app