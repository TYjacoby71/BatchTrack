
from flask import flash
from batch_routes import batches_bp
from admin_routes import admin_bp
from ingredient_routes import ingredients_bp
from recipe_routes import recipes_bp
from bulk_stock_routes import bulk_stock_bp
from inventory_adjust_routes import adjust_bp
from batch_view_route import batch_view_bp
from fault_log_routes import faults_bp
from product_log_routes import product_log_bp
from tag_manager_routes import tag_bp

def register_blueprints(app):
    """Register all blueprints with proper URL prefixes"""
    blueprints = [
        (batches_bp, ''),  # Root routes for batches
        (admin_bp, '/admin'),
        (ingredients_bp, '/inventory'),
        (recipes_bp, '/recipes'),
        (bulk_stock_bp, '/stock'),
        (adjust_bp, '/inventory'),
        (batch_view_bp, ''),  # Root routes for batch views
        (faults_bp, '/logs'),
        (product_log_bp, ''),  # Root routes for products
        (tag_bp, '/tags')
    ]
    
    for blueprint, url_prefix in blueprints:
        try:
            app.register_blueprint(blueprint, url_prefix=url_prefix)
        except Exception as e:
            flash(f'Error registering blueprint: {str(e)}')
            app.logger.error(f'Failed to register blueprint: {str(e)}')

