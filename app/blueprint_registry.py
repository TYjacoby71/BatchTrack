
"""
Centralized Blueprint Registry
Acts as a traffic controller for all blueprint imports and registrations
"""
from flask import Flask

class BlueprintRegistry:
    """Centralized registry for managing blueprint imports and registrations"""
    
    def __init__(self):
        self.registered_blueprints = set()
    
    def register_blueprint(self, app: Flask, module_path: str, blueprint_name: str, url_prefix: str = None, **kwargs):
        """
        Safely import and register a blueprint
        
        Args:
            app: Flask app instance
            module_path: Path to the module containing the blueprint
            blueprint_name: Name of the blueprint variable
            url_prefix: URL prefix for the blueprint
            **kwargs: Additional arguments for blueprint registration
        """
        blueprint_id = f"{module_path}.{blueprint_name}"
        
        if blueprint_id in self.registered_blueprints:
            print(f"Blueprint {blueprint_id} already registered, skipping...")
            return False
            
        try:
            # Import the module
            module = __import__(module_path, fromlist=[blueprint_name])
            blueprint = getattr(module, blueprint_name)
            
            # Register the blueprint
            registration_kwargs = {}
            if url_prefix:
                registration_kwargs['url_prefix'] = url_prefix
            registration_kwargs.update(kwargs)
            
            app.register_blueprint(blueprint, **registration_kwargs)
            self.registered_blueprints.add(blueprint_id)
            print(f"✅ Registered blueprint: {blueprint_id}")
            return True
            
        except (ImportError, AttributeError) as e:
            print(f"❌ Failed to register blueprint {blueprint_id}: {e}")
            return False
    
    def register_all_blueprints(self, app: Flask):
        """Register all application blueprints in the correct order"""
        
        # Core blueprints - these should be registered first
        core_blueprints = [
            ('app.blueprints.auth', 'auth_bp', '/auth'),
            ('app.blueprints.inventory', 'inventory_bp', '/inventory'),
            ('app.blueprints.recipes', 'recipes_bp', '/recipes'),
            ('app.blueprints.batches', 'batches_bp', '/batches'),
            ('app.blueprints.products', 'products_bp', None),  # No prefix for products
            ('app.blueprints.conversion', 'conversion_bp', '/conversion'),
            ('app.blueprints.expiration', 'expiration_bp', '/expiration'),
            ('app.blueprints.quick_add', 'quick_add_bp', '/quick_add'),
            ('app.blueprints.settings', 'settings_bp', '/settings'),
            ('app.blueprints.timers', 'timers_bp', '/timers'),
            ('app.blueprints.api', 'api_bp', '/api'),
        ]
        
        # Legacy blueprints and routes
        legacy_blueprints = [
            ('app.routes.app_routes', 'app_routes_bp', None),
            ('app.blueprints.admin.admin_routes', 'admin_bp', '/admin'),
            ('app.routes.bulk_stock_routes', 'bulk_stock_bp', '/bulk_stock'),
            ('app.routes.fault_log_routes', 'fault_log_bp', '/fault_log'),
            ('app.routes.tag_manager_routes', 'tag_manager_bp', '/tag_manager'),
        ]
        
        # Special blueprints that need custom handling
        special_blueprints = [
            ('app.blueprints.batches.add_extra', 'add_extra_bp', '/add-extra'),
            ('app.blueprints.fifo', 'fifo_bp', None),
        ]
        
        print("🚀 Starting blueprint registration...")
        
        # Register core blueprints
        for module_path, blueprint_name, url_prefix in core_blueprints:
            self.register_blueprint(app, module_path, blueprint_name, url_prefix)
        
        # Register legacy blueprints
        for module_path, blueprint_name, url_prefix in legacy_blueprints:
            self.register_blueprint(app, module_path, blueprint_name, url_prefix)
        
        # Register special blueprints
        for module_path, blueprint_name, url_prefix in special_blueprints:
            self.register_blueprint(app, module_path, blueprint_name, url_prefix)
        
        # Handle products blueprints specially
        self._register_product_blueprints(app)
        
        print(f"✅ Blueprint registration complete. Registered {len(self.registered_blueprints)} blueprints.")
    
    def _register_product_blueprints(self, app: Flask):
        """Handle product blueprints registration"""
        try:
            from app.blueprints.products import register_product_blueprints
            register_product_blueprints(app)
            print("✅ Registered product blueprints")
        except ImportError as e:
            print(f"❌ Failed to register product blueprints: {e}")

# Create global registry instance
blueprint_registry = BlueprintRegistry()
