
from flask import Blueprint, jsonify
from flask_login import login_required
from ...utils.timezone_utils import TimezoneUtils

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/server-time')
@login_required
def get_server_time():
    """Get current server time in user's timezone for clock synchronization"""
    try:
        current_time = TimezoneUtils.now()
        return jsonify({
            'current_time': current_time.isoformat(),
            'timezone': str(TimezoneUtils.get_user_timezone())
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# This file has been deprecated.
# Routes have been moved to:
# - stock_routes.py (check-stock endpoint)
# - ingredient_routes.py (categories and density endpoints)
# - container_routes.py (available-containers endpoint)
# - fifo_routes.py (fifo endpoints)
# Please use those files instead.
from .stock_routes import stock_api_bp
from .ingredient_routes import ingredient_api_bp
from .container_routes import container_api_bp
from .fifo_routes import fifo_api_bp

def register_api_routes(app):
    app.register_blueprint(stock_api_bp)
    app.register_blueprint(ingredient_api_bp) 
    app.register_blueprint(container_api_bp)
    app.register_blueprint(fifo_api_bp)