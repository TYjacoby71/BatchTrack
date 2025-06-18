from flask import Flask, render_template, redirect, url_for
from flask_migrate import Migrate

def create_app(config_filename=None):
    app = Flask(__name__)

    # Set default configuration
    app.config.update(
        SECRET_KEY='dev-key-change-in-production',
        SQLALCHEMY_DATABASE_URI='sqlite:///batchtrack.db',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        WTF_CSRF_ENABLED=True
    )

    # Load additional config if provided
    if config_filename:
        app.config.from_pyfile(config_filename)

    # Initialize extensions
    from .extensions import db, login_manager, migrate, csrf, bcrypt
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    bcrypt.init_app(app)

    # Import models to ensure they're registered
    from . import models

    # Register blueprints
    from .blueprints.auth import auth_bp
    from .blueprints.batches import batches_bp
    from .blueprints.conversion import conversion_bp
    from .blueprints.expiration import expiration_bp
    from .blueprints.inventory import inventory_bp
    from .blueprints.products import products_bp
    from .blueprints.quick_add import quick_add_bp
    from .blueprints.recipes import recipes_bp
    from .blueprints.settings import settings_bp
    from .blueprints.timers import timers_bp
    from .blueprints.api import api_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(batches_bp, url_prefix='/batches')
    app.register_blueprint(conversion_bp, url_prefix='/conversion')
    app.register_blueprint(expiration_bp, url_prefix='/expiration')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(products_bp, url_prefix='/products')
    app.register_blueprint(quick_add_bp, url_prefix='/quick_add')
    app.register_blueprint(recipes_bp, url_prefix='/recipes')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    app.register_blueprint(timers_bp, url_prefix='/timers')
    app.register_blueprint(api_bp, url_prefix='/api')

    # Register remaining routes
    from .routes.app_routes import app_routes_bp
    from .routes.admin_routes import admin_bp
    from .routes.bulk_stock_routes import bulk_stock_bp
    from .routes.fault_log_routes import fault_log_bp
    from .routes.product_routes import product_bp
    from .routes.tag_manager_routes import tag_manager_bp

    app.register_blueprint(app_routes_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(bulk_stock_bp, url_prefix='/bulk_stock')
    app.register_blueprint(fault_log_bp, url_prefix='/fault_log')
    app.register_blueprint(product_bp, url_prefix='/product_routes')
    app.register_blueprint(tag_manager_bp, url_prefix='/tag_manager')

    # Register filters
    from .filters.product_filters import register_filters
    register_filters(app)

    # Add main routes
    @app.route('/')
    def index():
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for('app_routes_bp.dashboard'))
        return redirect(url_for('homepage'))

    @app.route('/homepage')
    def homepage():
        return render_template('homepage.html')

    return app