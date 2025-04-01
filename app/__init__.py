from flask import Flask
from app.routes.ingredients import ingredients_bp
from app.routes.recipes import recipes_bp
from app.routes.batches import batches_bp
import os

def create_app():
    app = Flask(__name__, template_folder='../templates')
    app.secret_key = 'supersecretkey'  # Replace with a secure key in production
    
    app.register_blueprint(batches_bp)
    app.register_blueprint(ingredients_bp)
    app.register_blueprint(recipes_bp)
    from app.routes.auth import auth_bp
    from app.routes.export_missings import export_bp
    from app.routes.inventory_adjust import adjust_bp
    from app.routes.update_stock import update_stock_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(adjust_bp)
    app.register_blueprint(update_stock_bp)

    @app.context_processor
    def inject_globals():
        import json
        from app.routes.utils import load_categories
        with open('units.json') as f:
            units = json.load(f)
        return dict(units=units, category_options=load_categories())
    return app