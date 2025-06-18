
"""
Centralized Template Registry
Handles template route mappings and safe URL generation for templates
"""
from flask import url_for
import logging

logger = logging.getLogger(__name__)

class TemplateRegistry:
    """Centralized registry for managing template route mappings"""
    
    def __init__(self):
        # Map old endpoint names to new endpoint names
        self.endpoint_mappings = {
            # Products endpoints
            'products.product_list': 'legacy_products_main.product_list',
            'products.new_product': 'legacy_products_main.new_product',
            'products.view_product': 'legacy_products_main.view_product',
            'products.edit_product': 'legacy_products_main.edit_product',
            
            # Batches endpoints - map to the actual route function names
            'batches.batches_list': 'batches.list_batches',
            'batches.list_batches': 'batches.list_batches',
            'batches.view_batch_in_progress': 'batches.view_batch_in_progress',
            'batches.view_batch': 'batches.view_batch',
            
            # Other common endpoint mappings can be added here
            'inventory.list_inventory': 'inventory.list_inventory',
            'recipes.list_recipes': 'recipes.list_recipes',
            'recipes.new_recipe': 'recipes.new_recipe',
            
            # Admin endpoints
            'admin.cleanup_tools': 'admin.cleanup_tools',
            'admin.archive_zeroed_inventory': 'admin.archive_zeroed_inventory',
            
            # API endpoints
            'api.get_recipe_ingredients': 'api.get_recipe_ingredients',
            'api.check_stock': 'api.check_stock',
            
            # Missing common endpoints
            'settings.index': 'settings.index',
            'logout': 'auth.logout',
            'login': 'auth.login',
        }
        
        # Cache for verified endpoints
        self.verified_endpoints = set()
        self.failed_endpoints = set()
    
    def safe_url_for(self, endpoint, **values):
        """
        Safely generate URL for endpoint with fallback mapping
        
        Args:
            endpoint: The endpoint name
            **values: URL parameter values
            
        Returns:
            URL string or fallback URL
        """
        # Check if we've already verified this endpoint works
        if endpoint in self.verified_endpoints:
            try:
                return url_for(endpoint, **values)
            except Exception:
                # Endpoint might have become invalid
                self.verified_endpoints.discard(endpoint)
        
        # Check if we know this endpoint fails
        if endpoint in self.failed_endpoints:
            mapped_endpoint = self.endpoint_mappings.get(endpoint)
            if mapped_endpoint:
                try:
                    result = url_for(mapped_endpoint, **values)
                    logger.info(f"Successfully mapped {endpoint} -> {mapped_endpoint}")
                    return result
                except Exception as e:
                    logger.warning(f"Mapped endpoint {mapped_endpoint} also failed: {e}")
                    return "#"
            return "#"
        
        # Try the original endpoint first
        try:
            result = url_for(endpoint, **values)
            self.verified_endpoints.add(endpoint)
            return result
        except Exception as e:
            logger.warning(f"Original endpoint {endpoint} failed: {e}")
            self.failed_endpoints.add(endpoint)
            
            # Try mapped endpoint if available
            mapped_endpoint = self.endpoint_mappings.get(endpoint)
            if mapped_endpoint:
                try:
                    result = url_for(mapped_endpoint, **values)
                    logger.info(f"Successfully mapped {endpoint} -> {mapped_endpoint}")
                    return result
                except Exception as e:
                    logger.warning(f"Mapped endpoint {mapped_endpoint} also failed: {e}")
            
            # Return safe fallback
            logger.warning(f"No working endpoint found for {endpoint}, returning #")
            return "#"
    
    def check_endpoint_exists(self, endpoint):
        """Check if an endpoint exists without generating URL"""
        if endpoint in self.verified_endpoints:
            return True
        if endpoint in self.failed_endpoints:
            return False
            
        try:
            # Try to build URL with no parameters to test existence
            url_for(endpoint)
            self.verified_endpoints.add(endpoint)
            return True
        except Exception:
            self.failed_endpoints.add(endpoint)
            return False
    
    def register_template_functions(self, app):
        """Register template functions with Flask app"""
        
        @app.template_global('safe_url_for')
        def template_safe_url_for(endpoint, **values):
            return self.safe_url_for(endpoint, **values)
        
        @app.template_global('endpoint_exists')
        def template_endpoint_exists(endpoint):
            return self.check_endpoint_exists(endpoint)
        
        @app.template_filter('safe_url')
        def safe_url_filter(endpoint, **values):
            return self.safe_url_for(endpoint, **values)
        
        logger.info("✅ Registered template registry functions")

# Create global registry instance
template_registry = TemplateRegistry()
