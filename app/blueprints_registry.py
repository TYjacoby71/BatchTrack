import logging
logger = logging.getLogger(__name__)

def register_blueprints(app):
    """Register all blueprints with the Flask app."""

    # Track successful registrations
    successful_registrations = []
    failed_registrations = []

    def safe_register_blueprint(import_path, blueprint_name, url_prefix=None, description=None):
        """Safely register a blueprint with error handling"""
        try:
            module_path, bp_name = import_path.rsplit('.', 1)
            module = __import__(module_path, fromlist=[bp_name])
            blueprint = getattr(module, bp_name)

            if url_prefix:
                app.register_blueprint(blueprint, url_prefix=url_prefix)
            else:
                app.register_blueprint(blueprint)

            successful_registrations.append(description or blueprint_name)
            return True
        except Exception as e:
            failed_registrations.append(f"{description or blueprint_name}: {e}")
            return False

    # Core blueprints - these should always work
    safe_register_blueprint('app.blueprints.auth.auth_bp', 'auth_bp', '/auth', 'Authentication')
    safe_register_blueprint('app.blueprints.admin.admin_bp', 'admin_bp', '/admin', 'Admin')
    safe_register_blueprint('app.blueprints.developer.developer_bp', 'developer_bp', '/developer', 'Developer')
    safe_register_blueprint('app.blueprints.inventory.inventory_bp', 'inventory_bp', '/inventory', 'Inventory')
    safe_register_blueprint('app.blueprints.recipes.recipes_bp', 'recipes_bp', '/recipes', 'Recipes')
    safe_register_blueprint('app.blueprints.batches.batches_bp', 'batches_bp', '/batches', 'Batches')
    safe_register_blueprint('app.blueprints.organization.routes.organization_bp', 'organization_bp', '/organization', 'Organization')
    safe_register_blueprint('app.blueprints.billing.billing_bp', 'billing_bp', '/billing', 'Billing')
    safe_register_blueprint('app.blueprints.settings.settings_bp', 'settings_bp', '/settings', 'Settings')
    safe_register_blueprint('app.blueprints.timers.timers_bp', 'timers_bp', '/timers', 'Timers')
    safe_register_blueprint('app.blueprints.expiration.expiration_bp', 'expiration_bp', '/expiration', 'Expiration')
    safe_register_blueprint('app.blueprints.conversion.conversion_bp', 'conversion_bp', '/conversion', 'Conversion')

    # Product blueprints - use the register function
    try:
        from app.blueprints.products import register_product_blueprints
        register_product_blueprints(app)
        successful_registrations.append("Products Main")
    except Exception as e:
        failed_registrations.append(f"Products Main: {e}")
        # Fallback - try to register just the main products blueprint
        try:
            from app.blueprints.products.products import products_bp
            app.register_blueprint(products_bp)
            successful_registrations.append("Products Fallback")
        except Exception as e2:
            failed_registrations.append(f"Products Fallback: {e2}")

    # Product blueprints are now registered via register_product_blueprints() above
    # Remove individual registrations to avoid conflicts

    # API blueprints - these are often problematic
    safe_register_blueprint('app.blueprints.api.public.public_api_bp', 'public_api_bp', '/api/public', 'Public API')
    safe_register_blueprint('app.blueprints.api.routes.api_bp', 'api_bp', '/api', 'Main API')
    safe_register_blueprint('app.blueprints.api.drawer_actions.drawer_actions_bp', 'drawer_actions_bp', None, 'Drawer Actions')
    safe_register_blueprint('app.blueprints.api.density_reference.density_reference_bp', 'density_reference_bp', '/api', 'Density Reference')
    safe_register_blueprint('app.blueprints.api.retention_drawer.retention_bp', 'retention_bp', None, 'Retention Drawer API')
    safe_register_blueprint('app.blueprints.api.global_link_drawer.global_link_bp', 'global_link_bp', None, 'Global Link Drawer API')

    # Note: FIFO blueprint removed - functionality moved to inventory_adjustment service

    # Register standalone route modules
    route_modules = [
        ('app.routes.app_routes.app_routes_bp', 'app_routes_bp', None, 'App Routes'),
        ('app.routes.legal_routes.legal_bp', 'legal_bp', '/legal', 'Legal Routes'),
        ('app.routes.bulk_stock_routes.bulk_stock_bp', 'bulk_stock_bp', '/bulk-stock', 'Bulk Stock'),
        ('app.routes.fault_log_routes.faults_bp', 'faults_bp', '/faults', 'Fault Log'),
        ('app.routes.tag_manager_routes.tag_manager_bp', 'tag_manager_bp', '/tag-manager', 'Tag Manager'),
        ('app.routes.global_library_routes.global_library_bp', 'global_library_bp', None, 'Global Library Public'),
        ('app.routes.waitlist_routes.waitlist_bp', 'waitlist_bp', '/waitlist', 'Waitlist')
    ]

    for import_path, bp_name, url_prefix, description in route_modules:
        safe_register_blueprint(import_path, bp_name, url_prefix, description)

    # Register production planning blueprint
    safe_register_blueprint('app.blueprints.production_planning.production_planning_bp', 'production_planning_bp', '/production-planning', 'Production Planning')


    # Print summary
    print(f"\n=== Blueprint Registration Summary ===")
    print(f"✅ Successful: {len(successful_registrations)}")
    for success in successful_registrations:
        print(f"   - {success}")

    if failed_registrations:
        print(f"\n❌ Failed: {len(failed_registrations)}")
        for failure in failed_registrations:
            print(f"   - {failure}")
        print("\n⚠️  App will continue running with available blueprints")
    else:
        print("\n🎉 All blueprints registered successfully!")

    # CSRF exemptions
    try:
        from .extensions import csrf
        csrf.exempt(app.view_functions["inventory.adjust_inventory"])
        if "waitlist.join_waitlist" in app.view_functions:
            csrf.exempt(app.view_functions["waitlist.join_waitlist"])
    except Exception:
        pass