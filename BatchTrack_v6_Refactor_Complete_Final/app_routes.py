
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
    app.register_blueprint(batches_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(ingredients_bp)
    app.register_blueprint(recipes_bp)
    app.register_blueprint(bulk_stock_bp)
    app.register_blueprint(adjust_bp)
    app.register_blueprint(batch_view_bp)
    app.register_blueprint(faults_bp)
    app.register_blueprint(product_log_bp)
    app.register_blueprint(tag_bp)
