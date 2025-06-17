
def register_blueprints(app):
    """Register all application blueprints"""
    # Auth blueprint
    from ..auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    # Import and register other blueprints
    from .batches.start_batch import start_batch_bp
    from .batches.finish_batch import finish_batch_bp
    from .batches.cancel_batch import cancel_batch_bp
    from .batches.add_extra import add_extra_bp
    from .batches.routes import batches_bp
    from .inventory.routes import inventory_bp
    from .recipes.routes import recipes_bp
    from .conversion.routes import conversion_bp
    from .settings.routes import settings_bp
    from .quick_add.routes import quick_add_bp
    from .bulk_stock import bulk_stock_bp
    from .faults import faults_bp
    from .tag_manager import tag_bp
    from .products import products_bp
    from .fifo import fifo_bp
    from .expiration.routes import expiration_bp
    from .admin import admin_bp
    from .app_routes import app_routes_bp
    from .timers import timers_bp

    # Register all blueprints
    app.register_blueprint(fifo_bp)
    app.register_blueprint(expiration_bp)
    app.register_blueprint(conversion_bp, url_prefix='/conversion')
    app.register_blueprint(quick_add_bp, url_prefix='/quick-add')
    app.register_blueprint(products_bp)
    app.register_blueprint(settings_bp, url_prefix='/settings')
    app.register_blueprint(app_routes_bp)
    app.register_blueprint(batches_bp, url_prefix='/batches')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(recipes_bp, url_prefix='/recipes')
    app.register_blueprint(bulk_stock_bp, url_prefix='/stock')
    app.register_blueprint(faults_bp, url_prefix='/logs')
    app.register_blueprint(tag_bp, url_prefix='/tags')
    app.register_blueprint(timers_bp, url_prefix='/timers')
    app.register_blueprint(start_batch_bp, url_prefix='/start-batch')
    app.register_blueprint(finish_batch_bp, url_prefix='/finish-batch')
    app.register_blueprint(cancel_batch_bp, url_prefix='/cancel')
    app.register_blueprint(add_extra_bp, url_prefix='/add-extra')

    # Initialize API routes
    from .api import init_api
    init_api(app)

    # Register product filters
    from ..filters.product_filters import register_product_filters
    register_product_filters(app)
