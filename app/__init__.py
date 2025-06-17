
from flask import Flask, render_template, redirect, url_for
from flask_login import current_user
import os

def create_app(config_name='default'):
    """Application factory pattern"""
    app = Flask(__name__, static_folder='../static', static_url_path='/static', template_folder='../templates')

    # Load configuration
    from .config import config
    app.config.from_object(config[config_name])
    app.add_url_rule('/data/<path:filename>', endpoint='data', view_func=app.send_static_file)

    # Initialize extensions
    from .extensions import init_extensions
    init_extensions(app)

    # Import models after db initialization to avoid circular imports
    from .models import *

    # Setup logging
    from .utils.template_helpers import setup_logging
    setup_logging(app)

    # Register blueprints
    from .blueprints import register_blueprints
    register_blueprints(app)

    # Register template helpers
    from .utils.template_helpers import register_template_helpers
    register_template_helpers(app)

    # Register main routes
    register_main_routes(app)

    return app

def register_main_routes(app):
    """Register main application routes"""
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.dashboard'))
        return redirect(url_for('homepage'))

    @app.route('/homepage')
    def homepage():
        return render_template('homepage.html')
