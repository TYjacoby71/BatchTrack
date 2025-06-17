from flask import Flask, render_template, redirect, url_for
from flask_login import current_user
import os

# Import configuration and extensions
from config import config
from extensions import init_extensions, db

def create_app(config_name='default'):
    """Application factory pattern"""
    app = Flask(__name__, static_folder='static', static_url_path='/static')

    # Load configuration
    app.config.from_object(config[config_name])
    app.add_url_rule('/data/<path:filename>', endpoint='data', view_func=app.send_static_file)

    # Initialize extensions
    init_extensions(app)

    # Import models after db initialization to avoid circular imports
    from models import User, Recipe, InventoryItem, Unit, IngredientCategory

    # Setup logging
    from utils.unit_utils import setup_logging
    setup_logging(app)

    # Register blueprints
    register_blueprints(app)

    # Register template context processors and filters
    register_template_helpers(app)

    # Register main routes
    register_main_routes(app)

    return app

def register_blueprints(app):
    """Register all application blueprints"""
    # Auth blueprint
    from auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    # Import and register other blueprints
    from blueprints.batches.start_batch import start_batch_bp
    from blueprints.batches.finish_batch import finish_batch_bp
    from blueprints.batches.cancel_batch import cancel_batch_bp
    from blueprints.batches.add_extra import add_extra_bp
    from blueprints.batches.routes import batches_bp
    from blueprints.inventory.routes import inventory_bp
    from blueprints.recipes.routes import recipes_bp
    from blueprints.conversion.routes import conversion_bp
    from blueprints.settings.routes import settings_bp
    from blueprints.quick_add.routes import quick_add_bp
    from routes.bulk_stock_routes import bulk_stock_bp
    from routes.fault_log_routes import faults_bp
    from routes.product_log_routes import product_log_bp
    from routes.tag_manager_routes import tag_bp
    from routes.products import products_bp
    from routes.product_variants import product_variants_bp
    from routes.product_inventory import product_inventory_bp
    from routes.product_api import product_api_bp
    from blueprints.fifo import fifo_bp
    from blueprints.expiration.routes import expiration_bp
    from routes.admin_routes import admin_bp
    from routes.app_routes import app_routes_bp
    from blueprints.timers import timers_bp

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
    from blueprints.api import init_api
    init_api(app)

    # Register product filters
    from filters.product_filters import register_product_filters
    register_product_filters(app)

def register_template_helpers(app):
    """Register template context processors and filters"""
    from models import Unit, IngredientCategory

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

    @app.context_processor
    def inject_units():
        units = Unit.query.order_by(Unit.type, Unit.name).all()
        categories = IngredientCategory.query.order_by(IngredientCategory.name).all()
        return dict(units=units, categories=categories)

    @app.context_processor
    def inject_permissions():
        from utils.permissions import has_permission, has_role
        return dict(has_permission=has_permission, has_role=has_role)

def register_main_routes(app):
    """Register main application routes"""
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.dashboard'))
        return redirect(url_for('homepage'))

    @app.route('/homepage')
    def homepage():
        return render_template('homepage.html')

# Create the application instance
app = create_app(os.environ.get('FLASK_ENV', 'development'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)