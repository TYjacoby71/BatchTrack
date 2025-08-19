import logging
logger = logging.getLogger(__name__)

def register_blueprints(app):
    """Register all application blueprints"""

    # Public API that must be before auth
    try:
        from app.blueprints.api.public import public_api
        app.register_blueprint(public_api)
    except Exception as e:
        logger.warning(f"Public API registration failed: {e}")

    # Core blueprints
    _core_registrations = [
        ("app.blueprints.auth.routes", "auth_bp", "/auth"),
        ("app.blueprints.recipes.routes", "recipes_bp", "/recipes"),
        ("app.blueprints.inventory.routes", "inventory_bp", "/inventory"),
        ("app.blueprints.batches.routes", "batches_bp", "/batches"),
        ("app.blueprints.batches.finish_batch", "finish_batch_bp", "/batches"),
        ("app.blueprints.batches.cancel_batch", "cancel_batch_bp", "/batches"),
        ("app.blueprints.batches.start_batch", "start_batch_bp", "/start-batch"),
        ("app.blueprints.conversion.routes", "conversion_bp", "/conversion"),
        ("app.blueprints.expiration.routes", "expiration_bp", "/expiration"),
        ("app.blueprints.settings.routes", "settings_bp", "/settings"),
        ("app.blueprints.timers.routes", "timers_bp", "/timers"),
        ("app.blueprints.organization.routes", "organization_bp", "/organization"),
    ]

    for module_path, bp_name, prefix in _core_registrations:
        try:
            module = __import__(module_path, fromlist=[bp_name])
            bp = getattr(module, bp_name)
            app.register_blueprint(bp, url_prefix=prefix)
        except Exception as e:
            logger.warning(f"Failed to register {bp_name} from {module_path}: {e}")

    # Standalone blueprints
    _standalone_blueprints = [
        ("app.blueprints.developer.routes", "developer_bp"),
        ("app.routes.app_routes", "app_routes_bp"),
        ("app.blueprints.fifo", "fifo_bp"),
        ("app.blueprints.api.routes", "api_bp"),
        ("app.blueprints.admin.admin_routes", "admin_bp"),
        ("app.routes.waitlist_routes", "waitlist_bp"),
        ("app.routes.legal_routes", "legal_bp"),
    ]

    for module_path, bp_name in _standalone_blueprints:
        try:
            module = __import__(module_path, fromlist=[bp_name])
            bp = getattr(module, bp_name)
            app.register_blueprint(bp)
        except Exception as e:
            logger.warning(f"Failed to register {bp_name} from {module_path}: {e}")

    # Prefixed blueprints
    _prefixed_blueprints = [
        ("app.blueprints.batches.add_extra", "add_extra_bp", "/add-extra"),
        ("app.routes.bulk_stock_routes", "bulk_stock_bp", "/bulk_stock"),
        ("app.routes.fault_log_routes", "fault_log_bp", "/fault_log"),
        ("app.routes.tag_manager_routes", "tag_manager_bp", "/tag_manager"),
    ]

    for module_path, bp_name, prefix in _prefixed_blueprints:
        try:
            module = __import__(module_path, fromlist=[bp_name])
            bp = getattr(module, bp_name)
            app.register_blueprint(bp, url_prefix=prefix)
        except Exception as e:
            logger.warning(f"Failed to register {bp_name} from {module_path}: {e}")

    # Product blueprints
    try:
        from .blueprints.products.products import products_bp
        from .blueprints.products.api import products_api_bp
        from .blueprints.products.product_inventory_routes import product_inventory_bp
        from .blueprints.products.product_variants import product_variants_bp
        from .blueprints.products.sku import sku_bp
        from .blueprints.products.reservation_routes import reservation_bp
        from .blueprints.api.reservation_routes import reservation_api_bp

        app.register_blueprint(products_bp, url_prefix="/products")
        app.register_blueprint(products_api_bp)
        app.register_blueprint(product_inventory_bp, url_prefix="/products")
        app.register_blueprint(product_variants_bp, url_prefix="/products")
        app.register_blueprint(sku_bp, url_prefix="/products")
        app.register_blueprint(reservation_bp, url_prefix="/reservations")
        app.register_blueprint(reservation_api_bp)
    except Exception as e:
        logger.warning(f"Product blueprints failed: {e}")

    # API blueprints
    try:
        from .blueprints.api.stock_routes import stock_api_bp
        from .blueprints.api.ingredient_routes import ingredient_api_bp
        from .blueprints.api.container_routes import container_api_bp
        from .blueprints.api.dashboard_routes import dashboard_api_bp
        from .blueprints.api.unit_routes import unit_api_bp

        api_blueprints = [
            stock_api_bp, ingredient_api_bp, container_api_bp, 
            dashboard_api_bp, unit_api_bp
        ]

        for bp in api_blueprints:
            app.register_blueprint(bp)

        # Initialize API routes
        try:
            from .blueprints.api import init_api
            init_api(app)
        except ImportError:
            pass

    except Exception as e:
        logger.warning(f"API blueprints failed: {e}")

    # Billing blueprint
    try:
        from .blueprints.billing.routes import billing_bp
        app.register_blueprint(billing_bp)
        logger.info("Blueprint 'billing' registered successfully.")
    except ImportError as e:
        logger.error(f"Failed to import billing blueprint: {e}")
        # Continue without billing blueprint in case of import issues
    except Exception as e:
        logger.error(f"Failed to register billing blueprint: {e}")
        # Continue without billing blueprint in case of registration issues

    # CSRF exemptions
    try:
        from .extensions import csrf
        csrf.exempt(app.view_functions["inventory.adjust_inventory"])
        if "waitlist.join_waitlist" in app.view_functions:
            csrf.exempt(app.view_functions["waitlist.join_waitlist"])
    except Exception:
        pass