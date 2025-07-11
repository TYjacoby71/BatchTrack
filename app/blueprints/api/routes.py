from flask import Blueprint, jsonify
from flask_login import login_required
from ...utils.timezone_utils import TimezoneUtils

# Create the API blueprint
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

# Note: This file was previously deprecated, but we're now using it for the server-time endpoint
# Other routes have been moved to their respective modules:
# - stock_routes.py (check-stock endpoint)
# - reservation_routes.py (reservation endpoints)
# - Other API endpoints are in their respective blueprint modules
from .stock_routes import stock_api_bp
from .reservation_routes import reservation_api_bp

def register_api_routes(app):
    app.register_blueprint(stock_api_bp)
    app.register_blueprint(reservation_api_bp)