from flask import Blueprint

# Import all route modules and their blueprints
from .routes import api_bp
from .stock_routes import stock_api_bp
from .container_routes import container_api_bp
from .reservation_routes import reservation_api_bp
from .fifo_routes import fifo_api_bp
from .ingredient_routes import ingredient_api_bp

# Function to register all API blueprints
def register_api_blueprints(app):
    """Register all API blueprints with the app"""
    app.register_blueprint(api_bp)
    app.register_blueprint(stock_api_bp)
    app.register_blueprint(container_api_bp)
    app.register_blueprint(reservation_api_bp)
    app.register_blueprint(fifo_api_bp)
    app.register_blueprint(ingredient_api_bp)