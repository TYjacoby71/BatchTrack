from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ...services.dashboard_alerts import get_dashboard_alerts
from datetime import datetime

api_bp = Blueprint('api', __name__, url_prefix='/api')

# Import sub-blueprints to register their routes
from .stock_routes import stock_api_bp
from .ingredient_routes import ingredient_api_bp
from .container_routes import container_api_bp
from .fifo_routes import fifo_api_bp
from .reservation_routes import reservation_api_bp

# Register sub-blueprints
api_bp.register_blueprint(stock_api_bp)
api_bp.register_blueprint(ingredient_api_bp)
api_bp.register_blueprint(container_api_bp)
api_bp.register_blueprint(fifo_api_bp)
api_bp.register_blueprint(reservation_api_bp)

print(f"API Blueprint registered with routes:")
for rule in api_bp.url_map.iter_rules():
    print(f"  {rule.rule} -> {rule.endpoint}")