from flask import Flask
from app.routes.ingredients import ingredients_bp
from app.routes.recipes import recipes_bp
from app.routes.batches import batches_bp
import os

def create_app():
    app = Flask(__name__, template_folder='../templates')
    app.secret_key = 'supersecretkey'  # Replace with a secure key in production
    
    app.register_blueprint(ingredients_bp)
    app.register_blueprint(recipes_bp)
    app.register_blueprint(batches_bp)
    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp)

    @app.context_processor
    def inject_units():
        import json
        with open('units.json') as f:
            units = json.load(f)
        return dict(units=units)
    return app