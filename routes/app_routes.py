
from flask import flash
from routes.batch_routes import batches_bp
from routes.admin_routes import admin_bp
from routes.ingredient_routes import ingredients_bp
from routes.recipe_routes import recipes_bp
from routes.bulk_stock_routes import bulk_stock_bp
from routes.inventory_adjust_routes import adjust_bp
from routes.batch_view_route import batch_view_bp
from routes.fault_log_routes import faults_bp
from routes.product_log_routes import product_log_bp
from routes.tag_manager_routes import tag_bp

def register_blueprints(app):
    """Register all blueprints with proper URL prefixes"""
    blueprints = [
        (batches_bp, '/batches'),
        (admin_bp, '/admin'),
        (ingredients_bp, '/ingredients'),
        (recipes_bp, '/recipes'),
        (bulk_stock_bp, '/stock'),
        (adjust_bp, '/adjust'),
        (batch_view_bp, '/batch-view'),
        (faults_bp, '/logs'),
        (product_log_bp, '/products'),
        (tag_bp, '')
    ]
    
    for blueprint, url_prefix in blueprints:
        try:
            app.register_blueprint(blueprint, url_prefix=url_prefix)
        except Exception as e:
            flash(f'Error registering blueprint: {str(e)}')
            app.logger.error(f'Failed to register blueprint: {str(e)}')

