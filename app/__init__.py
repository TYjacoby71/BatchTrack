
from flask import Flask
from app.routes.ingredients import ingredients_bp
from app.routes.recipes import recipes_bp
from app.routes.batches import batches_bp

def create_app():
    app = Flask(__name__)
    app.register_blueprint(ingredients_bp)
    app.register_blueprint(recipes_bp)
    app.register_blueprint(batches_bp)
    return app
