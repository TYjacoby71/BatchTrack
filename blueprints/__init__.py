def register_blueprints(app):
    from .dashboard import dashboard_bp
    from .inventory.routes import inventory_bp
    from .recipes.routes import recipes_bp
    from .batches.start_batch import start_batch_bp
    from .batches.finish_batch import finish_batch_bp
    from .batches.cancel_batch import cancel_batch_bp
    from .conversion.routes import conversion_bp
    from .fifo.routes import fifo_bp
    from .timers.routes import timers_bp
    from .quick_add.routes import quick_add_bp
    from .expiration import expiration_bp
    from .faults import faults_bp
    from .admin import admin_bp
    from .settings.routes import settings_bp
    from .marketplace.routes import marketplace_bp
    from .products.routes import products_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(recipes_bp)
    app.register_blueprint(start_batch_bp)
    app.register_blueprint(finish_batch_bp)
    app.register_blueprint(cancel_batch_bp)
    app.register_blueprint(conversion_bp)
    app.register_blueprint(fifo_bp)
    app.register_blueprint(timers_bp)
    app.register_blueprint(quick_add_bp)
    app.register_blueprint(expiration_bp)
    app.register_blueprint(faults_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(marketplace_bp)
    app.register_blueprint(products_bp)