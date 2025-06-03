from flask import Blueprint
from .stock_routes import stock_api_bp
from .ingredient_routes import ingredient_api_bp
from .container_routes import container_api_bp
from .routes import register_api_routes

def init_api(app):
    register_api_routes(app)