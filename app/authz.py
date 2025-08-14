
from flask import jsonify, redirect, url_for
from .extensions import login_manager
from .utils.http import wants_json

def configure_login_manager(app):
    """Configure Flask-Login with JSON-aware unauthorized handler"""
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "info"

    @login_manager.unauthorized_handler
    def _unauthorized():
        if wants_json():
            return jsonify({"error": "unauthorized"}), 401
        return redirect(url_for("auth.login"))

    @login_manager.user_loader
    def load_user(user_id):
        from .models import User
        try:
            user = app.extensions['sqlalchemy'].session.get(User, int(user_id))
            if user and user.is_active:
                if user.user_type == 'developer':
                    return user
                elif user.organization and user.organization.is_active:
                    return user
            return None
        except (ValueError, TypeError):
            return None
