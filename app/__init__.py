from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from .extensions import db
from .models import User
import os
from flask import Flask, render_template, request, redirect, url_for, flash


def create_app():
    app = Flask(__name__, static_folder='static', static_url_path='/static')

    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'devkey-please-change-in-production') #os.environ.get('FLASK_SECRET_KEY', 'devkey-please-change-in-production')
    instance_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'instance')
    os.makedirs(instance_path, exist_ok=True)
    os.makedirs('static/product_images', exist_ok=True)
    os.chmod(instance_path, 0o777)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(instance_path, 'batchtrack.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = 'static/product_images'

    # Initialize extensions
    db.init_app(app)
    migrate = Migrate(app, db)

    # Initialize CSRF protection
    from .extensions import csrf
    csrf.init_app(app)

    # Login manager setup
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from .blueprints.auth import auth_bp
    from .blueprints.recipes import recipes_bp
    from .blueprints.inventory import inventory_bp
    from .blueprints.batches import batches_bp
    from .blueprints.batches.finish_batch import finish_batch_bp
    from .blueprints.batches.cancel_batch import cancel_batch_bp
    from .blueprints.batches.start_batch import start_batch_bp
    from .blueprints.products import products_bp
    from .blueprints.products.api import products_api_bp

    from .blueprints.api.stock_routes import stock_api_bp
    from .blueprints.api.ingredient_routes import ingredient_api_bp
    from .blueprints.conversion import conversion_bp
    from .blueprints.expiration import expiration_bp
    from .blueprints.settings import settings_bp
    from .blueprints.timers import timers_bp
    from .blueprints.quick_add import quick_add_bp
    from .blueprints.admin import admin_bp
    from .routes import app_routes
    from .blueprints.fifo import fifo_bp
    from .blueprints.batches.add_extra import add_extra_bp
    from .routes import bulk_stock_routes
    from .routes import fault_log_routes
    from .routes import tag_manager_routes
    # Register blueprints
    from .blueprints.admin import admin_bp
    from .blueprints.admin.reservation_routes import reservation_admin_bp
    app.register_blueprint(admin_bp,  url_prefix='/admin')
    app.register_blueprint(reservation_admin_bp, url_prefix='/admin/reservations')

    # Register all blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(recipes_bp, url_prefix='/recipes')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(batches_bp, url_prefix='/batches')
    app.register_blueprint(finish_batch_bp, url_prefix='/batches')
    app.register_blueprint(cancel_batch_bp, url_prefix='/batches')
    app.register_blueprint(start_batch_bp, url_prefix='/start-batch')
    # Import and register blueprints
    try:
        from .blueprints.products.products import products_bp
        from .blueprints.products.api import products_api_bp
        from .blueprints.products.product_inventory_routes import product_inventory_bp
        from .blueprints.products.product_variants import product_variants_bp
        from .blueprints.products.sku import sku_bp
        app.register_blueprint(products_bp, url_prefix='/products')
        app.register_blueprint(products_api_bp)
        app.register_blueprint(product_inventory_bp, url_prefix='/products')
        app.register_blueprint(product_variants_bp, url_prefix='/products')
        app.register_blueprint(sku_bp, url_prefix='/products')
    except ImportError:
        print("Could not register any product blueprints")
        pass

    app.register_blueprint(conversion_bp, url_prefix='/conversion')
    app.register_blueprint(expiration_bp, url_prefix='/expiration')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    app.register_blueprint(timers_bp, url_prefix='/timers')
    app.register_blueprint(quick_add_bp, url_prefix='/quick_add')
    app.register_blueprint(app_routes.app_routes_bp)
    app.register_blueprint(fifo_bp)
    app.register_blueprint(add_extra_bp, url_prefix='/add-extra')
    app.register_blueprint(bulk_stock_routes.bulk_stock_bp, url_prefix='/bulk_stock')
    app.register_blueprint(fault_log_routes.fault_log_bp, url_prefix='/fault_log')
    app.register_blueprint(tag_manager_routes.tag_manager_bp, url_prefix='/tag_manager')

    # Register API blueprints
    from .blueprints.api.routes import register_api_routes
    register_api_routes(app)

    # Load additional config if provided
    #if config_filename:
    #    app.config.from_pyfile(config_filename)

    # Import models to ensure they're registered
    from . import models
    from .models import Unit, IngredientCategory

    # Setup logging
    from .utils.unit_utils import setup_logging
    setup_logging(app)

    # Enable debug logging in development
    if app.debug:
        import logging
        app.logger.setLevel(logging.DEBUG)
        logging.getLogger('werkzeug').setLevel(logging.DEBUG)

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
            return dict(has_permission=lambda x: True, has_role=has_role)

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

    from .management import register_commands
    register_commands(app)

    return app