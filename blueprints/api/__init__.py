
from flask import Blueprint
from .stock_routes import stock_api_bp
from .ingredient_routes import ingredient_api_bp
from .container_routes import container_api_bp

def init_api(app):
    app.register_blueprint(stock_api_bp)
    app.register_blueprint(ingredient_api_bp)
    app.register_blueprint(container_api_bp)
